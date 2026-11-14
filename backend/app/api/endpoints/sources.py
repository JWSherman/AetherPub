import asyncio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from backend.app.core.database import get_db
from backend.app.models.entities import Source, Article
from backend.app.schemas.api_models import SourceCreate, SourceUpdate, SourceResponse, SourceProbeResponse
from backend.app.services.crawler.fetcher import create_http_client
from backend.app.services.crawler.discovery import DiscoveryService
from backend.app.services.scheduler.runner import ingest_source

router = APIRouter(prefix="/sources", tags=["Sources"])

@router.get("", response_model=list[SourceResponse])
async def list_sources(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(
            Source,
            func.count(Article.id).label("article_count")
        )
        .outerjoin(Article, Article.source_id == Source.id)
        .group_by(Source.id)
        .order_by(desc(Source.created_at))
    )
    result = await db.execute(stmt)
    items = []
    for source, count in result.all():
        resp = SourceResponse.model_validate(source)
        resp.article_count = count
        items.append(resp)
    return items

@router.post("/probe", response_model=SourceProbeResponse)
async def probe_source(payload: SourceCreate):
    client = create_http_client()
    try:
        discovery = DiscoveryService(client)
        data = await discovery.probe_source(payload.url)
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to probe website: {str(e)}")
    finally:
        await client.aclose()

@router.post("", response_model=SourceResponse)
async def add_source(payload: SourceCreate, bg: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    client = create_http_client()
    try:
        discovery = DiscoveryService(client)
        probe_data = await discovery.probe_source(payload.url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Unable to reach website: {str(e)}")
    finally:
        await client.aclose()

    final_name = (payload.name.strip() if payload.name else None) or probe_data.get("name") or payload.url
    final_base_url = probe_data.get("base_url") or payload.url
    final_feed_url = payload.feed_url or probe_data.get("feed_url")
    final_crawl_mode = probe_data.get("crawl_mode", "auto")

    # Check for existing source
    if final_feed_url:
        exist_check = await db.execute(select(Source).where(Source.feed_url == final_feed_url))
    else:
        exist_check = await db.execute(select(Source).where(Source.base_url == final_base_url))

    if exist_check.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="This source or feed is already registered.")

    source = Source(
        name=final_name,
        base_url=final_base_url,
        feed_url=final_feed_url,
        crawl_mode=final_crawl_mode,
        is_active=True,
        weight=payload.weight,
        last_status="idle"
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)

    # Trigger initial crawl in background
    bg.add_task(ingest_source, source.id)

    resp = SourceResponse.model_validate(source)
    resp.article_count = 0
    return resp

@router.patch("/{source_id}", response_model=SourceResponse)
async def update_source(source_id: str, payload: SourceUpdate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Source).where(Source.id == source_id))
    source = res.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")

    if payload.name is not None:
        source.name = payload.name.strip()
    if payload.feed_url is not None:
        source.feed_url = payload.feed_url.strip() or None
    if payload.crawl_mode is not None:
        source.crawl_mode = payload.crawl_mode
    if payload.is_active is not None:
        source.is_active = payload.is_active
    if payload.weight is not None:
        source.weight = payload.weight

    await db.commit()
    await db.refresh(source)

    count_res = await db.execute(select(func.count(Article.id)).where(Article.source_id == source.id))
    resp = SourceResponse.model_validate(source)
    resp.article_count = count_res.scalar() or 0
    return resp

@router.post("/{source_id}/crawl")
async def trigger_source_crawl(source_id: str, bg: BackgroundTasks, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Source).where(Source.id == source_id))
    source = res.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    bg.add_task(ingest_source, source_id)
    return {"status": "queued", "source_id": source_id}

@router.delete("/{source_id}")
async def delete_source(source_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Source).where(Source.id == source_id))
    source = res.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    await db.delete(source)
    await db.commit()
    return {"status": "deleted", "source_id": source_id}
