from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from backend.app.core.database import get_db
from backend.app.models.entities import Setting
from backend.app.schemas.api_models import SettingItem, SMTPTestRequest
from backend.app.services.delivery.smtp_client import SMTPDeliveryService
from backend.app.services.scheduler.runner import run_full_pipeline

router = APIRouter(prefix="/settings", tags=["Settings"])

DEFAULT_SETTINGS = {
    "DAILY_CRON_HOUR": "6",
    "DAILY_CRON_MINUTE": "0",
    "DAILY_ARTICLE_LIMIT": "10",
    "AUTO_SEND_SMTP": "false",
    "DEFAULT_KINDLE_EMAIL": "",
    "SMTP_HOST": "",
    "SMTP_PORT": "587",
    "SMTP_USER": "",
    "SMTP_PASS": "",
    "SMTP_FROM": "",
    "SMTP_USE_TLS": "true"
}

@router.get("", response_model=dict[str, str])
async def get_settings(db: AsyncSession = Depends(get_db)):
    res = await db.execute(select(Setting))
    db_settings = {s.key: s.value for s in res.scalars().all()}
    merged = {**DEFAULT_SETTINGS, **db_settings}
    # Obfuscate password in GET
    if merged.get("SMTP_PASS"):
        merged["SMTP_PASS"] = "••••••••"
    return merged

@router.post("", response_model=dict[str, str])
async def save_settings(settings_map: dict[str, str], db: AsyncSession = Depends(get_db)):
    for k, v in settings_map.items():
        if k == "SMTP_PASS" and v == "••••••••":
            continue  # do not overwrite with mask
        res = await db.execute(select(Setting).where(Setting.key == k))
        existing = res.scalar_one_or_none()
        if existing:
            existing.value = str(v)
        else:
            db.add(Setting(key=k, value=str(v)))
    await db.commit()
    return {"status": "saved"}

@router.post("/test-smtp")
async def test_smtp(payload: SMTPTestRequest):
    try:
        await SMTPDeliveryService.test_connection({
            "host": payload.host,
            "port": payload.port,
            "username": payload.username,
            "password": payload.password,
            "use_tls": payload.use_tls
        })
        return {"status": "success", "message": "SMTP handshake and authentication successful!"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"SMTP Connection Failed: {str(e)}")

@router.post("/run-pipeline")
async def trigger_full_pipeline(bg: BackgroundTasks):
    bg.add_task(run_full_pipeline)
    return {"status": "queued", "message": "Full ingestion & curation pipeline running"}
