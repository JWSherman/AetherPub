from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, asc, func
from sqlalchemy.orm import defer
from backend.app.core.database import get_db
from backend.app.core.event_bus import event_bus
from backend.app.models.entities import Article, Source
from backend.app.schemas.api_models import ArticleResponse

router = APIRouter(prefix="/articles", tags=["Articles"])

@router.post("/reset-bundled")
async def reset_bundled_articles(db: AsyncSession = Depends(get_db)):
    """Clears the 'is_bundled' flag on all articles so a new edition can be compiled from a clean slate."""
    res = await db.execute(select(Article).where(Article.is_bundled == True))
    bundled_articles = res.scalars().all()
    reset_count = len(bundled_articles)
    for art in bundled_articles:
        art.is_bundled = False

    await db.commit()

    await event_bus.emit("articles:bundled_reset", {
        "reset_count": reset_count
    })

    return {
        "status": "success",
        "reset_count": reset_count,
        "message": f"Cleared 'bundled' status on {reset_count} article{'s' if reset_count != 1 else ''}. Ready to compile from a clean slate."
    }

@router.get("", response_model=list[ArticleResponse])
async def list_articles(
    source_id: str | None = None,
    unbundled_only: bool = False,
    sort_by: str = Query(default="date_desc"),
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db)
):
    effective_date = func.coalesce(Article.published_at, Article.created_at)
    order_clauses = {
        "date_desc": (desc(effective_date), desc(Article.created_at)),
        "date_asc": (asc(effective_date), asc(Article.created_at)),
        "ingested_desc": (desc(Article.created_at),),
        "ingested_asc": (asc(Article.created_at),),
        "score_desc": (desc(Article.relevance_score), desc(effective_date)),
        "score_asc": (asc(Article.relevance_score), desc(effective_date)),
        "words_desc": (desc(Article.word_count), desc(effective_date)),
        "words_asc": (asc(Article.word_count), desc(effective_date)),
        "title_asc": (asc(func.lower(Article.title)), desc(effective_date)),
        "title_desc": (desc(func.lower(Article.title)), desc(effective_date)),
        "source_asc": (asc(func.lower(Source.name)), desc(effective_date)),
        "source_desc": (desc(func.lower(Source.name)), desc(effective_date)),
        "status_ready": (asc(Article.is_bundled), desc(Article.relevance_score), desc(effective_date)),
    }.get(sort_by, (desc(effective_date), desc(Article.created_at)))

    stmt = (
        select(Article, Source.name.label("source_name"))
        .options(defer(Article.clean_html), defer(Article.plain_text))
        .join(Source, Source.id == Article.source_id)
        .order_by(*order_clauses)
    )
    if source_id:
        stmt = stmt.where(Article.source_id == source_id)
    if unbundled_only:
        stmt = stmt.where(Article.is_bundled == False)
    stmt = stmt.limit(limit)

    result = await db.execute(stmt)
    items = []
    for art, s_name in result.all():
        resp = ArticleResponse.model_validate(art)
        resp.source_name = s_name
        if not resp.published_at:
            resp.published_at = art.created_at
        items.append(resp)
    return items

@router.get("/{article_id}")
async def get_article_detail(article_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Article).where(Article.id == article_id))
    art = res.scalar_one_or_none()
    if not art:
        raise HTTPException(status_code=404, detail="Article not found")
    return {
        "id": art.id,
        "title": art.title,
        "author": art.author,
        "url": art.url,
        "published_at": art.published_at or art.created_at,
        "clean_html": art.clean_html,
        "excerpt": art.excerpt,
        "word_count": art.word_count,
        "relevance_score": art.relevance_score,
        "is_bundled": art.is_bundled,
        "created_at": art.created_at
    }
