from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "AetherPub"
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent
    STORAGE_DIR: Path = BASE_DIR / "storage"
    EPUBS_DIR: Path = STORAGE_DIR / "epubs"
    COVERS_DIR: Path = STORAGE_DIR / "covers"
    MEDIA_DIR: Path = STORAGE_DIR / "media"
    
    DATABASE_URL: str = f"sqlite+aiosqlite:///{STORAGE_DIR.as_posix()}/aetherpub.db"
    
    # Scheduling defaults
    DAILY_CRON_HOUR: int = 6
    DAILY_CRON_MINUTE: int = 0
    DAILY_ARTICLE_LIMIT: int = 10
    
    # Extraction & Images (Color Preservation)
    PRESERVE_COLOR: bool = True
    MAX_IMAGE_WIDTH: int = 1600
    MAX_IMAGE_HEIGHT: int = 1600
    JPEG_QUALITY: int = 85
    
    # SMTP Defaults (Configurable via UI / DB)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASS: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_FROM: str = ""
    DEFAULT_KINDLE_EMAIL: str = ""

settings = Settings()
settings.STORAGE_DIR.mkdir(parents=True, exist_ok=True)
settings.EPUBS_DIR.mkdir(parents=True, exist_ok=True)
settings.COVERS_DIR.mkdir(parents=True, exist_ok=True)
settings.MEDIA_DIR.mkdir(parents=True, exist_ok=True)
