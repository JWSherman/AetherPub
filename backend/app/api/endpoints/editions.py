import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from pathlib import Path
from backend.app.core.database import get_db
from backend.app.core.event_bus import event_bus
from backend.app.models.entities import DailyEdition, Article, Setting, edition_articles
from backend.app.schemas.api_models import EditionResponse, EditionBulkDeleteRequest
from backend.app.services.scheduler.runner import compile_daily_edition
from backend.app.services.delivery.smtp_client import SMTPDeliveryService

router = APIRouter(prefix="/editions", tags=["Editions"])

@router.get("", response_model=list[EditionResponse])
async def list_editions(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(DailyEdition).order_by(desc(DailyEdition.created_at)))
    return res.scalars().all()

@router.post("/build-now")
async def trigger_build_now(bg: BackgroundTasks):
    """Triggers immediate compilation of available unbundled articles."""
    bg.add_task(compile_daily_edition)
    return {"status": "queued", "message": "Compilation pipeline started in background"}

@router.post("/bulk-delete")
async def bulk_delete_editions(payload: EditionBulkDeleteRequest, db: AsyncSession = Depends(get_db)):
    """Deletes multiple editions and their associated EPUB/cover files from disk."""
    if not payload.edition_ids:
        return {"status": "deleted", "deleted_count": 0, "deleted_ids": []}

    res = await db.execute(select(DailyEdition).where(DailyEdition.id.in_(payload.edition_ids)))
    editions = res.scalars().all()

    deleted_ids = []
    for edition in editions:
        file_name = Path(edition.file_path).name if edition.file_path else edition.title
        for path_str in (edition.file_path, edition.cover_path):
            if path_str:
                try:
                    p = Path(path_str)
                    if p.exists() and p.is_file():
                        p.unlink(missing_ok=True)
                except OSError:
                    pass

        await db.execute(edition_articles.delete().where(edition_articles.c.edition_id == edition.id))
        deleted_ids.append(edition.id)
        await db.delete(edition)

        await event_bus.emit("edition:deleted", {
            "edition_id": edition.id,
            "title": edition.title,
            "file_name": file_name
        })

    await db.commit()
    return {"status": "deleted", "deleted_count": len(deleted_ids), "deleted_ids": deleted_ids}

@router.get("/{edition_id}")
async def get_edition_details(edition_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(DailyEdition).where(DailyEdition.id == edition_id))
    edition = res.scalar_one_or_none()
    if not edition:
        raise HTTPException(status_code=404, detail="Edition not found")

    art_res = await db.execute(
        select(Article, edition_articles.c.chapter_order)
        .join(edition_articles, edition_articles.c.article_id == Article.id)
        .where(edition_articles.c.edition_id == edition.id)
        .order_by(edition_articles.c.chapter_order)
    )
    articles_list = []
    for art, ch_num in art_res.all():
        articles_list.append({
            "id": art.id,
            "chapter_order": ch_num,
            "title": art.title,
            "author": art.author,
            "url": art.url,
            "published_at": art.published_at.isoformat() if art.published_at else None,
            "word_count": art.word_count,
            "excerpt": art.excerpt
        })

    return {
        "id": edition.id,
        "title": edition.title,
        "edition_date": edition.edition_date,
        "article_count": edition.article_count,
        "total_word_count": edition.total_word_count,
        "file_path": edition.file_path,
        "file_size_bytes": edition.file_size_bytes,
        "sent_via_smtp": edition.sent_via_smtp,
        "download_count": edition.download_count or 0,
        "last_downloaded_at": edition.last_downloaded_at,
        "download_timestamps": edition.download_timestamps,
        "created_at": edition.created_at,
        "articles": articles_list
    }

@router.delete("/{edition_id}")
async def delete_edition(edition_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(DailyEdition).where(DailyEdition.id == edition_id))
    edition = res.scalar_one_or_none()
    if not edition:
        raise HTTPException(status_code=404, detail="Edition not found")

    edition_title = edition.title
    file_name = Path(edition.file_path).name if edition.file_path else edition.title

    for path_str in (edition.file_path, edition.cover_path):
        if path_str:
            try:
                p = Path(path_str)
                if p.exists() and p.is_file():
                    p.unlink(missing_ok=True)
            except OSError:
                pass

    await db.execute(edition_articles.delete().where(edition_articles.c.edition_id == edition.id))
    await db.delete(edition)
    await db.commit()

    await event_bus.emit("edition:deleted", {
        "edition_id": edition_id,
        "title": edition_title,
        "file_name": file_name
    })

    return {"status": "deleted", "id": edition_id, "title": edition_title}

@router.get("/{edition_id}/download")
async def download_edition(edition_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(DailyEdition).where(DailyEdition.id == edition_id))
    edition = res.scalar_one_or_none()
    if not edition:
        raise HTTPException(status_code=404, detail="Edition not found")

    p = Path(edition.file_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="EPUB file not found on disk")

    now_dt = datetime.now(timezone.utc)
    now_iso = now_dt.isoformat()
    edition.last_downloaded_at = now_dt
    edition.download_count = (edition.download_count or 0) + 1
    history = edition.download_timestamps
    history.insert(0, now_iso)
    edition.download_history = json.dumps(history[:50])
    await db.commit()

    await event_bus.emit("edition:downloaded", {
        "edition_id": edition.id,
        "title": edition.title,
        "file_name": p.name,
        "download_count": edition.download_count,
        "last_downloaded_at": now_iso
    })

    return FileResponse(
        path=p,
        media_type="application/epub+zip",
        filename=p.name
    )

@router.get("/{edition_id}/cover")
async def get_edition_cover(edition_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(DailyEdition).where(DailyEdition.id == edition_id))
    edition = res.scalar_one_or_none()
    if not edition or not edition.cover_path:
        raise HTTPException(status_code=404, detail="Cover not found")

    p = Path(edition.cover_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="Cover file not found on disk")

    return FileResponse(path=p, media_type="image/jpeg")

@router.post("/{edition_id}/send-email")
async def send_edition_email(edition_id: str, recipient: str | None = None, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(DailyEdition).where(DailyEdition.id == edition_id))
    edition = res.scalar_one_or_none()
    if not edition:
        raise HTTPException(status_code=404, detail="Edition not found")

    p = Path(edition.file_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail="EPUB file missing")

    # Load SMTP settings from DB
    settings_res = await db.execute(select(Setting))
    cfg_map = {s.key: s.value for s in settings_res.scalars().all()}

    target_email = recipient or cfg_map.get("DEFAULT_KINDLE_EMAIL")
    if not target_email:
        raise HTTPException(status_code=400, detail="No recipient email provided or configured in Settings")

    try:
        await SMTPDeliveryService.send_epub_email(
            recipient_email=target_email,
            epub_path=p,
            edition_title=edition.title,
            custom_config=cfg_map
        )
        edition.sent_via_smtp = True
        await db.commit()
        return {"status": "success", "message": f"Successfully sent to {target_email}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SMTP Send Failed: {str(e)}")
