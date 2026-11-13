from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.app.core.database import get_db
from backend.app.models.entities import Keyword
from backend.app.schemas.api_models import (
    KeywordCreate, KeywordResponse, KeywordEvaluateRequest, KeywordEvaluateResponse
)
from backend.app.services.curator.scorer import KeywordScorer
from backend.app.services.crawler.fetcher import create_http_client
from backend.app.services.extractor.readability import ReadabilityService

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
    Evaluates a sample text or fetches an article URL to dry-run score against current keywords.
    """
    title = payload.title
    content = payload.content

    if payload.url:
        client = create_http_client()
        try:
            resp = await client.get(payload.url, timeout=10.0)
            extracted = ReadabilityService.extract_article(resp.text, payload.url)
            if extracted:
                title = extracted["title"]
                content = extracted["plain_text"]
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to fetch test URL: {str(e)}")
        finally:
            await client.aclose()

    res = await db.execute(select(Keyword))
    keywords = res.scalars().all()

    score, breakdown, is_excluded, is_required_missing = KeywordScorer.evaluate(title, content, keywords)
    return KeywordEvaluateResponse(
        score=score,
        breakdown=breakdown,
        is_excluded_match=is_excluded,
        is_required_missing=is_required_missing
    )
