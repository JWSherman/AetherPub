import asyncio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from backend.app.core.database import get_db
from backend.app.models.entities import Source, Article
from backend.app.schemas.api_models import SourceCreate, SourceResponse, SourceProbeResponse
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

    # Check for existing
    exist_check = await db.execute(select(Source).where(Source.base_url == probe_data["base_url"]))
    if exist_check.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="A source with this base URL is already registered.")

    source = Source(
        name=probe_data["name"] or payload.url,
        base_url=probe_data["base_url"],
        feed_url=probe_data["feed_url"],
        crawl_mode=probe_data["crawl_mode"],
        is_active=True,
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
