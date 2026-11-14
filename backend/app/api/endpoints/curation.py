import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.core.database import get_db
from backend.app.core.event_bus import event_bus
from backend.app.models.entities import Setting, Article, Source, Keyword
from backend.app.schemas.api_models import CurationCurves, CurvePoint
from backend.app.services.curator.scorer import DEFAULT_AGE_CURVE, DEFAULT_LENGTH_CURVE, KeywordScorer

router = APIRouter(prefix="/curation", tags=["Curation"])

async def get_stored_curves(db: AsyncSession) -> tuple[list[dict], list[dict]]:
    age_res = await db.execute(select(Setting).where(Setting.key == "WEIGHT_CURVE_AGE"))
    age_row = age_res.scalar_one_or_none()
    try:
        age_curve = json.loads(age_row.value) if age_row else DEFAULT_AGE_CURVE
    except Exception:
        age_curve = DEFAULT_AGE_CURVE

    len_res = await db.execute(select(Setting).where(Setting.key == "WEIGHT_CURVE_LENGTH"))
    len_row = len_res.scalar_one_or_none()
    try:
        len_curve = json.loads(len_row.value) if len_row else DEFAULT_LENGTH_CURVE
    except Exception:
        len_curve = DEFAULT_LENGTH_CURVE

    return age_curve, len_curve

@router.get("/curves", response_model=CurationCurves)
async def get_curves(db: AsyncSession = Depends(get_db)):
    age_curve, len_curve = await get_stored_curves(db)
    return CurationCurves(
        age_curve=[CurvePoint(x=p["x"], y=p["y"]) for p in age_curve],
        length_curve=[CurvePoint(x=p["x"], y=p["y"]) for p in len_curve]
    )

@router.put("/curves", response_model=CurationCurves)
async def update_curves(payload: CurationCurves, db: AsyncSession = Depends(get_db)):
    age_data = [{"x": float(p.x), "y": float(p.y)} for p in payload.age_curve]
    len_data = [{"x": float(p.x), "y": float(p.y)} for p in payload.length_curve]

    # Save to Settings
    for key, val in [("WEIGHT_CURVE_AGE", json.dumps(age_data)), ("WEIGHT_CURVE_LENGTH", json.dumps(len_data))]:
        res = await db.execute(select(Setting).where(Setting.key == key))
        row = res.scalar_one_or_none()
        if row:
            row.value = val
        else:
            db.add(Setting(key=key, value=val))

    await db.commit()
    await event_bus.emit("curation:curves_updated", {"message": "Scoring curves updated"})

    return payload

@router.post("/recalculate-scores")
async def recalculate_article_scores(db: AsyncSession = Depends(get_db)):
    """
    Recalculates relevance scores for unbundled articles using active keywords,
    source weights, age curve, and length curve.
    """
    age_curve, len_curve = await get_stored_curves(db)

    # Fetch active keywords
    kw_res = await db.execute(select(Keyword))
    keywords = kw_res.scalars().all()

    # Fetch sources map
    src_res = await db.execute(select(Source))
    sources_map = {s.id: s.weight for s in src_res.scalars().all()}

    # Fetch unbundled articles
    art_res = await db.execute(select(Article).where(Article.is_bundled == False))
    articles = art_res.scalars().all()

    updated_count = 0
    for art in articles:
        src_weight = sources_map.get(art.source_id, 0.0)
        score = KeywordScorer.score_article(
            title=art.title,
            text=art.plain_text,
            keywords=keywords,
            source_weight=src_weight,
            published_at=art.published_at or art.created_at,
            word_count=art.word_count,
            age_curve=age_curve,
            length_curve=len_curve
        )
        art.relevance_score = score
        updated_count += 1

    await db.commit()
    await event_bus.emit("curation:scores_recalculated", {"updated_articles": updated_count})

    return {
        "status": "success",
        "updated_articles": updated_count,
        "message": f"Successfully recalculated relevance scores for {updated_count} unbundled articles."
    }
