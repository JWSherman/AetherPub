# AetherPub ⚡
### Automated Daily E-Reader EPUB 3 Periodical Engine

AetherPub is a self-hosted platform designed for avid readers and e-reader owners (Kindle, Kobo, Boox, reMarkable). It monitors designated websites, blogs, and RSS feeds, cleans and extracts articles with full RGB color image preservation, evaluates them against user-defined interest keywords, and compiles a daily omnibus EPUB 3 periodical with procedural cover art and wireless e-reader delivery.

---

## Key Features

- **Cyberpunk Reactive Dark WebUI**:
  - Deep OLED dark theme with glowing cyan/violet accents and glassmorphic panels.
  - Live Server-Sent Events (SSE) telemetry console streaming real-time crawler logs and compilation milestones.
  - Interactive Keyword Sandbox for dry-run testing article scoring formulas.
  - In-browser reading modal with chapter navigation and formatted typography.
- **Hybrid Source Ingestion**:
  - Auto-discovery of RSS, Atom feeds, Sitemaps, or polite shallow HTML crawling.
  - Concurrency limiter and random polite jitter (200ms–600ms) to respect target web servers.
- **Color E-Ink & Tablet Optimization**:
  - Preserves full RGB color channels for color e-ink displays (Kaleido 3, Gallery 3, reMarkable Paper Pro) and tablets.
  - Downscales oversized photos to $\le 1600\text{px}$ JPEG (quality 85) for snappy e-reader page turns.
- **Intelligent Keyword Curation**:
  - Support for `+required` keywords, `-excluded` keywords, and positive/negative interest weights.
  - Title matches carry $3\times$ weight boost over body text.
  - 64-bit SimHash deduplication prevents syndication duplicates across aggregators.
  - Configurable daily article quotas.
- **IDPF EPUB 3.2 Standard Compliance**:
  - Procedural cover generator (Pillow) with date, article count, and topic banners.
  - Dual Table of Contents: EPUB 3 `nav.xhtml` and legacy EPUB 2 `toc.ncx` for older Kindles.
  - E-ink typography stylesheet with relative units, styled blockquotes, high-contrast code blocks, and page-break controls.
- **Out-of-the-Box Send-to-Kindle (SMTP)**:
  - 1-click email dispatch directly to `@kindle.com` or personal e-reader email address.
  - Built-in SMTP connection tester.

---

## Quickstart

### 1. Requirements
- Python 3.12+ (tested and verified on Python 3.14 on Windows)

### 2. Install Dependencies
```powershell
python -m pip install -r requirements.txt
```

### 3. Launch the Server
```powershell
python run.py
```
Open your browser to: **`http://127.0.0.1:8000`**

---

## Architecture Overview

```
agyplayground/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── endpoints/          # REST & SSE routers
│   │   │   └── router.py           # /api/v1 aggregation
│   │   ├── core/
│   │   │   ├── config.py           # Pydantic settings & directories
│   │   │   ├── database.py         # SQLAlchemy 2.0 async engine
│   │   │   └── event_bus.py        # Async in-memory SSE broker
│   │   ├── models/
│   │   │   └── entities.py         # Source, Keyword, Article, DailyEdition
│   │   ├── schemas/
│   │   │   └── api_models.py       # Pydantic v2 schemas
│   │   ├── services/
│   │   │   ├── crawler/            # Discovery & polite fetcher
│   │   │   ├── extractor/          # Trafilatura & color image downscaler
│   │   │   ├── curator/            # Keyword scoring & SimHash deduplication
│   │   │   ├── epub/               # EPUB 3 compiler & procedural covers
│   │   │   ├── delivery/           # aiosmtplib Send-to-Kindle
│   │   │   └── scheduler/          # APScheduler cron runner
│   │   └── main.py                 # FastAPI application
│   └── tests/                      # Automated test suite (11 unit & e2e tests)
├── frontend/
│   └── static/
│       ├── css/custom.css          # Glassmorphism & reader styling
│       ├── js/app.js               # Reactive SSE client & UI logic
│       └── index.html              # Cyberpunk dark dashboard SPA
├── storage/
│   ├── aetherpub.db                # SQLite database
│   ├── epubs/                      # Generated .epub files
│   ├── covers/                     # Generated cover images
│   └── media/                      # Cached media assets
├── requirements.txt
├── run.py
└── README.md
```

---

## Automated Verification

Run the test suite with pytest:
```powershell
python -m pytest tests/ -v
```

All 11 automated tests verify:
- SimHash text deduplication and Hamming distance calculation
- Keyword scoring logic (title $3\times$ weighting, exclusion triggers, required checks)
- Trafilatura readability extraction and HTML cleanup
- Image downscaling and full RGB color preservation
- Procedural cover image creation
- EPUB 3 packaging, ZIP integrity, and table of contents
- FastAPI REST endpoints and SSE event streaming
- End-to-end source ingestion and compilation pipeline
