from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from backend.app.core.database import get_db
from backend.app.models.entities import Article, Source
from backend.app.schemas.api_models import ArticleResponse

router = APIRouter(prefix="/articles", tags=["Articles"])

@router.get("", response_model=list[ArticleResponse])
async def list_articles(
    source_id: str | None = None,
    unbundled_only: bool = False,
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Article, Source.name.label("source_name"))
        .join(Source, Source.id == Article.source_id)
        .order_by(desc(Article.created_at))
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
