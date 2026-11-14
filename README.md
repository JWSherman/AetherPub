<div align="center">

# ⚡ AetherPub

### **The Automated Daily E-Reader EPUB 3 Periodical Engine**

Turn the websites, blogs, and RSS feeds you love into a daily, distraction-free omnibus EPUB ready for your Kindle, Kobo, Boox, or reMarkable e-reader.

[![Python 3.12+](https://img.shields.io/badge/python-3.12%20%7C%203.14-38bdf8.svg?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-06b6d4.svg?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![EPUB 3](https://img.shields.io/badge/EPUB-3.2%20Standard-8b5cf6.svg?style=flat-square&logo=bookstack&logoColor=white)](https://www.w3.org/publishing/epub3/)
[![Tests](https://img.shields.io/badge/tests-13%20passed-10b981.svg?style=flat-square)](tests/)
[![Theme](https://img.shields.io/badge/theme-Cyberpunk%20Obsidian-09090b.svg?style=flat-square)](UI_DESIGN_SYSTEM.md)
[![License: MIT](https://img.shields.io/badge/license-MIT-amber.svg?style=flat-square)](LICENSE)

</div>

---

## 📖 Overview

Reading long-form technical articles, newsletters, and blogs on computer monitors or smartphone screens causes eye fatigue and cognitive distraction. Most "send to e-reader" extensions only bundle one article at a time or convert images to muddy grayscale.

**AetherPub** is an all-in-one, self-hosted web platform that continuously tracks your favorite websites and RSS feeds, filters and scores incoming articles based on your personal keyword interests, and automatically compiles them each morning into a single consolidated, beautifully typeset **EPUB 3 daily digest** complete with procedural cover art, table of contents, full RGB color diagrams, and 1-click Amazon Send-to-Kindle delivery.

---

## ✨ Key Features

### 🌐 Hybrid Source Discovery & Direct RSS Feed Input
- **Direct Feed Links**: Paste direct RSS, Atom, or XML feed URLs (e.g. `https://gameinformer.com/reviews.xml`) to target specific categories and sections.
- **Auto-Discovery**: Enter standard website homepages (e.g. `https://blog.cloudflare.com`) and AetherPub automatically locates hidden feed tags, probes standard paths, or falls back to shallow HTML crawling.
- **Multi-Feed Domain Support**: Track multiple distinct feeds from the same root domain without duplicate collisions.

### 🎨 Color E-Ink & Modern Reader Optimization
- **Full RGB Color Preservation**: Extracted photos, diagrams, and infographics retain their original RGB color channels for modern color e-ink devices (**Kindle Colorsoft, Kobo Clara Colour, reMarkable Paper Pro, Boox Palma/Tab**) and tablets.
- **Adaptive Downscaling**: High-resolution imagery is gracefully resized to max 1600px JPEG (quality 85) to ensure rapid e-reader page turns and compact file sizes.

### 🎯 Multi-Dimensional Curation & Scoring Weights
- **Source-Level Priority Weights**: Assign a custom positive or negative score bias directly to individual feeds and sources to prioritize trusted publications.
- **Informational Keyword Matrix**: Easily view and adjust multipliers inline on active keyword rules, required anchors, and exclusion filters.
- **Interactive Article Age Curve**: Graphically shape article recency decay using interactive SVG control points ($X = \text{Age in Days}, Y = \text{Score Bias}$).
- **Interactive Article Length Curve**: Shape preferred reading lengths with interactive points ($X = \text{Word Count}, Y = \text{Score Bias}$) to favor sweet-spot longform essays over stubs or excessive tomes.
- **SimHash 64-bit Deduplication**: Prevents cross-posted or syndicated articles across aggregators from appearing twice.
- **Interactive Scoring Sandbox**: Test your keyword rules, source weights, and dynamic curves against sample URLs or text before activating them.
- **One-Click Recalculate**: Instantly re-score all unbundled articles when rules or curve control points are updated.

### 📚 IDPF EPUB 3.2 Standard Compliance
- **Procedural Cover Art**: Pillow procedurally generates a bespoke, high-resolution ($1600 \times 2400$) cover image for every daily edition with date emblems and topic summaries.
- **Dual Table of Contents**: Generates modern EPUB 3 `nav.xhtml` alongside legacy EPUB 2 `toc.ncx` for 100% navigation compatibility with both older and newer Kindle/Kobo firmware.
- **E-Ink Typography**: Serif body typography, relative fluid spacing, styled blockquotes, high-contrast code blocks, and strict chapter page-break controls.

### 📧 Built-in Send-to-Kindle (SMTP)
- Send compiled editions directly to your `@kindle.com` or personal e-reader address with 1 click.
- Automatic daily dispatch option upon scheduled compilation.
- Interactive SMTP connection testing tool.

### ⚡ Cyberpunk Reactive Dark WebUI
- Zero-node runtime: served directly by FastAPI from static assets—starts in under 2 seconds.
- Live Server-Sent Events (SSE) telemetry terminal streaming background crawler discoveries and compilation progress in real time.
- Integrated modal reader to preview compiled chapters and color illustrations directly in your browser.

---

## 🚀 Quickstart

### Prerequisites
- **Python 3.12+** (tested and verified on Python 3.14 on Windows & Linux)
- Git

### 1. Clone & Install Dependencies
```powershell
git clone https://github.com/your-username/aetherpub.git
cd aetherpub
python -m pip install -r requirements.txt
```

### 2. Start AetherPub
```powershell
python run.py
```

### 3. Open the Dashboard
Navigate to: **[http://127.0.0.1:8000](http://127.0.0.1:8000)**  
Interactive Swagger API docs are available at: **[http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)**

---

## 🖥️ WebUI Walkthrough

```text
┌────────────────────────────────────────────────────────────────────────┐
│ ⚡ AETHERPUB                      ● System Active (Idle)   [Compile]   │
├────────────────────────────────────────────────────────────────────────┤
│ [Overview]  [Curation & Weights]  [Daily Digests]  [Ingested] [Settings] │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  Tracked Sources   Active Keywords   Ready to Bundle   Total Digests   │
│       [ 12 ]            [ 8 ]            [ 34 ]            [ 5 ]       │
│                                                                        │
│  ┌─ LATEST DIGEST ──────────────────────────────────────────────────┐  │
│  │ AetherPub Daily – 2026-11-13  •  10 Articles  •  ~25 min read    │  │
│  │ [⬇ Download EPUB]  [📧 Send to Device]  [👁 Read in Browser]     │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ┌─ LIVE PIPELINE TELEMETRY (SSE STREAM) ───────────────────────────┐  │
│  │ [14:02:10] 🔍 Crawling source: Cloudflare Blog                   │  │
│  │ [14:02:11] 📄 Ingested "Choosing QuePaxa" (Score: 8.5)          │  │
│  │ [14:02:15] 📚 Compiling Daily EPUB (10 articles)...             │  │
│  │ [14:02:17] 🎉 Generated EPUB "aetherpub_2026-11-13.epub" (0.2 MB)│  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

1. **Website Sources**: Add websites or direct feeds. Inspect links with live article preview before confirming.
2. **Keyword Matrix**: Add tags, adjust weight sliders (-5 to +10), mark rules as `[+] Required` or `[-] Excluded`, and dry-run test scores in the sandbox.
3. **Daily Digests**: Browse compiled editions, view procedural cover thumbnails, download `.epub` files, or read chapters directly in the web browser.
4. **Settings & SMTP**: Set your daily cron schedule hour/minute, daily article quota, and SMTP credentials.

---

## 📨 Amazon Send-to-Kindle Setup Guide

To deliver daily editions directly to your Kindle wirelessly:

1. Open your **Amazon Account** $\rightarrow$ Navigate to **Manage Your Content and Devices** $\rightarrow$ **Preferences**.
2. Scroll to **Personal Document Settings**.
3. Copy your Kindle email address (e.g., `yourname_123@kindle.com`).
4. Under **Approved Personal Document E-mail List**, click **Add a new approved e-mail address** and enter the email address you will use in AetherPub's `From Email` field.
5. In AetherPub:
   - Go to **Settings & SMTP**.
   - Enter your Kindle email in **Target E-Reader Email**.
   - Fill in your SMTP host (e.g. `smtp.gmail.com`, port `587`), username, and password / app password.
   - Click **Test SMTP Connection** to verify.
   - (Optional) Toggle **Auto-send upon daily build** to dispatch digests automatically every morning!

---

## 🛠️ Architecture & Developer Documentation

For contributors and autonomous AI agents:

- 🤖 **[AGENTS.md](AGENTS.md)** – Mandatory AI entry point, hard constraints, and verification checklist.
- 📄 **[ARCHITECTURE.md](ARCHITECTURE.md)** – Detailed subsystem specifications, data flow diagrams, SimHash algorithms, and extension recipes.
- 🎨 **[UI_DESIGN_SYSTEM.md](UI_DESIGN_SYSTEM.md)** – Strict visual language, cyberpunk dark tokens, component anatomy, and typography hierarchy.

### Repository Map

```
aetherpub/
├── backend/
│   ├── app/
│   │   ├── api/endpoints/     # REST & SSE route handlers
│   │   ├── core/              # Config, async SQLite engine, SSE event bus
│   │   ├── models/            # SQLAlchemy 2.0 async ORM entities
│   │   ├── schemas/           # Pydantic v2 validation models
│   │   ├── services/
│   │   │   ├── crawler/       # Direct RSS & heuristic auto-discovery
│   │   │   ├── extractor/     # Trafilatura parser & Pillow RGB downscaler
│   │   │   ├── curator/       # Keyword scoring & 64-bit SimHash deduplicator
│   │   │   ├── epub/          # EbookLib EPUB 3 builder & procedural cover artist
│   │   │   ├── delivery/      # aiosmtplib Send-to-Kindle dispatcher
│   │   │   └── scheduler/     # APScheduler background runner
│   │   └── main.py            # FastAPI initialization & static asset mounting
│   └── tests/                 # Automated test suite (13 unit & integration tests)
├── frontend/static/           # Zero-Node vanilla reactive SPA
│   ├── css/custom.css         # Glassmorphism & e-reader serif typography
│   ├── js/app.js              # Reactive SSE client & view router
│   └── index.html             # Cyberpunk dark dashboard
├── storage/                   # Local SQLite DB & generated EPUB/cover vault
├── requirements.txt           # Python package requirements
├── run.py                     # Top-level application launcher
└── README.md                  # This file
```

---

## 🧪 Automated Testing

AetherPub includes a comprehensive automated test suite with an isolated SQLite test database fixture.

Run tests with pytest:
```powershell
python -m pytest tests/ -v
```

```text
tests/test_api.py::test_api_health PASSED
tests/test_api.py::test_keyword_crud_and_evaluate PASSED
tests/test_api.py::test_direct_feed_probe_and_multiple_feeds_same_domain PASSED
tests/test_curator.py::test_simhash_identical_and_similar_texts PASSED
tests/test_curator.py::test_simhash_malformed_hashes_resilience PASSED
tests/test_curator.py::test_keyword_scorer_weighted_interest PASSED
tests/test_curator.py::test_keyword_scorer_exclusion PASSED
tests/test_curator.py::test_keyword_scorer_required_missing PASSED
tests/test_epub.py::test_cover_image_generation PASSED
tests/test_epub.py::test_epub3_generation_and_zip_structure PASSED
tests/test_extractor.py::test_readability_extraction PASSED
tests/test_extractor.py::test_image_processor_color_preservation PASSED
tests/test_pipeline_e2e.py::test_full_compilation_pipeline PASSED

======================= 13 passed, 1 warning in 44.49s =======================
```

---

## 📄 License

Distributed under the **MIT License**. See `LICENSE` for details.
