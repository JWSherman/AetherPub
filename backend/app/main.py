from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from backend.app.core.config import settings
from backend.app.core.database import init_db
from backend.app.services.scheduler.runner import init_scheduler
from backend.app.api.router import api_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    init_scheduler()
    yield
    # Shutdown

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Automated Daily E-Reader EPUB Digest Platform",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
app.include_router(api_router)

# Mount Static Frontend
frontend_dir = settings.BASE_DIR / "frontend" / "static"
if frontend_dir.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_dir)), name="static")

# Mount Media Vault
if settings.MEDIA_DIR.exists():
    app.mount("/media", StaticFiles(directory=str(settings.MEDIA_DIR)), name="media")

@app.get("/", include_in_schema=False)
async def serve_index():
    index_file = frontend_dir / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": f"{settings.PROJECT_NAME} Backend Online. Visit /docs for API documentation."}

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": settings.PROJECT_NAME}
