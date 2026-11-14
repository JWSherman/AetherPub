from pydantic import BaseModel, ConfigDict
from datetime import datetime

class SourceCreate(BaseModel):
    url: str
    name: str | None = None
    feed_url: str | None = None
    weight: float = 0.0

class SourceUpdate(BaseModel):
    name: str | None = None
    feed_url: str | None = None
    crawl_mode: str | None = None
    is_active: bool | None = None
    weight: float | None = None

class SourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    base_url: str
    feed_url: str | None
    crawl_mode: str
    is_active: bool
    weight: float = 0.0
    last_crawled_at: datetime | None
    last_status: str
    error_message: str | None
    article_count: int = 0
    created_at: datetime

class SourceProbeResponse(BaseModel):
    name: str
    base_url: str
    feed_url: str | None
    crawl_mode: str
    preview: list[dict]

class KeywordCreate(BaseModel):
    term: str
    weight: float = 1.0
    is_required: bool = False
    is_excluded: bool = False
    match_type: str = "contains"

class KeywordUpdate(BaseModel):
    term: str | None = None
    weight: float | None = None
    is_required: bool | None = None
    is_excluded: bool | None = None
    match_type: str | None = None

class KeywordResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    term: str
    weight: float
    is_required: bool
    is_excluded: bool
    match_type: str
    created_at: datetime

class CurvePoint(BaseModel):
    x: float
    y: float

class CurationCurves(BaseModel):
    age_curve: list[CurvePoint]
    length_curve: list[CurvePoint]

class KeywordEvaluateRequest(BaseModel):
    title: str = ""
    content: str = ""
    url: str = ""
    source_id: str | None = None
    published_at: datetime | None = None
    word_count: int | None = None

class KeywordEvaluateResponse(BaseModel):
    score: float
    breakdown: list[dict]
    is_excluded_match: bool
    is_required_missing: bool

class ArticleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    source_id: str
    url: str
    title: str
    author: str | None
    published_at: datetime | None
    excerpt: str | None
    word_count: int
    relevance_score: float
    is_bundled: bool
    source_name: str | None = None
    created_at: datetime

class EditionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    edition_date: str
    article_count: int
    total_word_count: int
    file_path: str
    cover_path: str | None
    file_size_bytes: int
    sent_via_smtp: bool
    created_at: datetime

class SettingItem(BaseModel):
    key: str
    value: str

class SMTPTestRequest(BaseModel):
    host: str
    port: int = 587
    username: str = ""
    password: str = ""
    use_tls: bool = True
    recipient_email: str | None = None
