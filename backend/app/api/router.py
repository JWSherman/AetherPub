from fastapi import APIRouter
from backend.app.api.endpoints.sources import router as sources_router
from backend.app.api.endpoints.keywords import router as keywords_router
from backend.app.api.endpoints.articles import router as articles_router
from backend.app.api.endpoints.editions import router as editions_router
from backend.app.api.endpoints.settings import router as settings_router
from backend.app.api.endpoints.events import router as events_router
from backend.app.api.endpoints.curation import router as curation_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(sources_router)
api_router.include_router(keywords_router)
api_router.include_router(articles_router)
api_router.include_router(editions_router)
api_router.include_router(settings_router)
api_router.include_router(events_router)
api_router.include_router(curation_router)
