from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.app.core.database import get_db
from backend.app.models.entities import Keyword, Source
from backend.app.schemas.api_models import (
    KeywordCreate, KeywordUpdate, KeywordResponse, KeywordEvaluateRequest, KeywordEvaluateResponse
)
from backend.app.services.curator.scorer import KeywordScorer
from backend.app.services.crawler.fetcher import create_http_client
from backend.app.services.extractor.readability import ReadabilityService
from backend.app.api.endpoints.curation import get_stored_curves

router = APIRouter(prefix="/keywords", tags=["Keywords"])

@router.get("", response_model=list[KeywordResponse])
async def list_keywords(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Keyword).order_by(desc(Keyword.created_at)))
    return result.scalars().all()

@router.post("", response_model=KeywordResponse)
async def create_or_update_keyword(payload: KeywordCreate, db: AsyncSession = Depends(get_db)):
    term_clean = payload.term.strip()
    if not term_clean:
        raise HTTPException(status_code=400, detail="Keyword term cannot be empty")

    # Check if keyword already exists
    res = await db.execute(select(Keyword).where(Keyword.term == term_clean))
    existing = res.scalar_one_or_none()
    if existing:
        existing.weight = payload.weight
        existing.is_required = payload.is_required
        existing.is_excluded = payload.is_excluded
        existing.match_type = payload.match_type
        await db.commit()
        await db.refresh(existing)
        return existing

    kw = Keyword(
        term=term_clean,
        weight=payload.weight,
        is_required=payload.is_required,
        is_excluded=payload.is_excluded,
        match_type=payload.match_type
    )
    db.add(kw)
    await db.commit()
    await db.refresh(kw)
    return kw

@router.patch("/{keyword_id}", response_model=KeywordResponse)
async def update_keyword(keyword_id: str, payload: KeywordUpdate, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Keyword).where(Keyword.id == keyword_id))
    kw = res.scalar_one_or_none()
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")

    if payload.weight is not None:
        kw.weight = payload.weight
    if payload.term is not None:
        kw.term = payload.term.strip()
    if payload.is_required is not None:
        kw.is_required = payload.is_required
    if payload.is_excluded is not None:
        kw.is_excluded = payload.is_excluded
    if payload.match_type is not None:
        kw.match_type = payload.match_type

    await db.commit()
    await db.refresh(kw)
    return kw

@router.delete("/{keyword_id}")
async def delete_keyword(keyword_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Keyword).where(Keyword.id == keyword_id))
    kw = res.scalar_one_or_none()
    if not kw:
        raise HTTPException(status_code=404, detail="Keyword not found")
    await db.delete(kw)
    await db.commit()
    return {"status": "deleted", "id": keyword_id}

@router.post("/evaluate", response_model=KeywordEvaluateResponse)
async def evaluate_text_sandbox(payload: KeywordEvaluateRequest, db: AsyncSession = Depends(get_db)):
    """
    Evaluates a sample text or fetches an article URL to dry-run score against current keywords,
    source bias, and curation curves.
    """
    title = payload.title
    content = payload.content
    word_count = payload.word_count
    published_at = payload.published_at

    if payload.url:
        client = create_http_client()
        try:
            resp = await client.get(payload.url, timeout=10.0)
            extracted = ReadabilityService.extract_article(resp.text, payload.url)
            if extracted:
                title = extracted["title"]
                content = extracted["plain_text"]
                word_count = extracted.get("word_count", len(content.split()))
                if extracted.get("published_at"):
                    published_at = extracted["published_at"]
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to fetch test URL: {str(e)}")
        finally:
            await client.aclose()

    source_weight = 0.0
    if payload.source_id:
        src_res = await db.execute(select(Source).where(Source.id == payload.source_id))
        src = src_res.scalar_one_or_none()
        if src:
            source_weight = src.weight

    res = await db.execute(select(Keyword))
    keywords = res.scalars().all()

    age_curve, len_curve = await get_stored_curves(db)

    score, breakdown, is_excluded, is_required_missing = KeywordScorer.evaluate(
        title=title,
        text=content,
        keywords=keywords,
        source_weight=source_weight,
        published_at=published_at,
        word_count=word_count,
        age_curve=age_curve,
        length_curve=len_curve
    )
    return KeywordEvaluateResponse(
        score=score,
        breakdown=breakdown,
        is_excluded_match=is_excluded,
        is_required_missing=is_required_missing
    )
