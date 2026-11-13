# AGENTS.md: AI Engineering & Navigation Guide for AetherPub

Welcome, AI Agent. This document is your mandatory entry point for navigating, modifying, and contributing to **AetherPub**.

---

## 1. Quick Orientation: What You Must Read First

Before planning or making any changes, you **must** read the specialized documents corresponding to your task:

1. **Working on Backend, Database, Crawler, Extraction, or EPUB Compilation?**
   👉 **Read [ARCHITECTURE.md](ARCHITECTURE.md)**  
   *Covers:* Data flow, hybrid discovery engine, SimHash 64-bit deduplication rules, EbookLib EPUB 3 dual-TOC requirements, Amazon Send-to-Kindle specifications, and extension recipes.
2. **Working on Frontend, UI, Styling, Modals, or Interactions?**
   👉 **Read [UI_DESIGN_SYSTEM.md](UI_DESIGN_SYSTEM.md)**  
   *Covers:* Cyberpunk Obsidian dark theme (`#09090b`), glassmorphism specs (`.glass-panel`), strict semantic neon color assignments, tri-font typography rules, and modal geometry.
3. **General Overview & User Context?**
   👉 **Read [README.md](README.md)**

---

## 2. Mandatory Architectural Constraints (Never Break These)

1. **Zero-Node Runtime Invariant**:
   - The frontend is served directly by FastAPI as a modular Single Page Application from `frontend/static/`.
   - **DO NOT** create a `package.json`, install npm packages, or introduce Vite/Webpack/Rollup build steps. The server must start with a single command: `python run.py`.
2. **RGB Color Preservation for E-Ink**:
   - Extracted images **must remain full-color RGB**. Do **not** convert images to 8-bit grayscale. Color e-ink readers (Kaleido 3, Gallery 3, reMarkable Paper Pro) require RGB. Oversized images are downscaled to max 1600px JPEG (quality 85).
3. **OLED Black Only (No Light Mode)**:
   - AetherPub has no light mode. All surfaces must remain dark (`bg-zinc-950` / `bg-zinc-900`) with glassmorphic hairlines (`border-white/10`).
4. **Hexadecimal SimHash Integrity**:
   - `Article.content_hash` must always be a 16-character hexadecimal string. Never insert plain text or non-hex characters into this column.
5. **EPUB 3 IDPF Compliance**:
   - Every generated book must bundle both EPUB 3 `nav.xhtml` and legacy EPUB 2 `toc.ncx` for cross-reader compatibility.
6. **Lucide Icons Rule**:
   - After injecting dynamic HTML containing `<i data-lucide="...">`, always call `lucide.createIcons()`.

---

## 3. Essential Commands

### Run Dev Server
```powershell
python run.py
```
- Web Dashboard: `http://127.0.0.1:8000`
- API Interactive Docs: `http://127.0.0.1:8000/docs`

### Run Automated Test Suite
Always run the full test suite before claiming a task is complete:
```powershell
python -m pytest tests/ -v
```

---

## 4. Key Directory & Code Map

| Directory / File | What It Does |
| :--- | :--- |
| `run.py` | Top-level application launcher (Uvicorn on port 8000). |
| `backend/app/main.py` | FastAPI application initialization, lifespan, static file mounting. |
| `backend/app/api/endpoints/` | REST API routes (`sources.py`, `keywords.py`, `articles.py`, `editions.py`, `settings.py`, `events.py`). |
| `backend/app/core/event_bus.py` | In-memory async pub-sub broker powering the Server-Sent Events (SSE) telemetry stream. |
| `backend/app/models/entities.py` | SQLAlchemy 2.0 relational models (`Source`, `Keyword`, `Article`, `DailyEdition`, `Setting`). |
| `backend/app/services/crawler/` | Hybrid discovery (`discovery.py`) for direct RSS/XML feeds or HTML link heuristics, and resilient fetcher (`fetcher.py`). |
| `backend/app/services/extractor/` | Trafilatura article parser (`readability.py`) and Pillow RGB image downscaler (`image_processor.py`). |
| `backend/app/services/curator/` | Keyword weighted scoring matrix (`scorer.py`) and 64-bit SimHash deduplicator (`simhash.py`). |
| `backend/app/services/epub/` | Pillow $1600 \times 2400$ procedural cover generator (`cover_generator.py`) and EbookLib EPUB 3 builder (`generator.py`). |
| `backend/app/services/delivery/` | Amazon Send-to-Kindle compliant email dispatcher (`smtp_client.py`). |
| `backend/app/services/scheduler/` | APScheduler background worker and manual trigger runner (`runner.py`). |
| `frontend/static/` | UI static assets (`index.html`, `css/custom.css`, `js/app.js`). |
| `storage/` | Local SQLite database (`aetherpub.db`) and file vaults (`epubs/`, `covers/`, `media/`). |
| `tests/` | Automated test suite (`test_api.py`, `test_curator.py`, `test_epub.py`, `test_extractor.py`, `test_pipeline_e2e.py`). |

---

## 5. Verification Checklist for Any Agent Making Changes

- [ ] Does `python -m pytest tests/ -v` pass with 100% success?
- [ ] Are all new database fields properly typed in SQLAlchemy and mapped in Pydantic v2 schemas?
- [ ] If changing the UI, was `UI_DESIGN_SYSTEM.md` followed (colors, `.glass-panel`, `font-mono` for metadata)?
- [ ] If changing extraction, did you verify that color images remain RGB and are not converted to grayscale?
- [ ] Did you avoid introducing `node_modules` or a `package.json`?
