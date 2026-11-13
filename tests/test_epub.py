import zipfile
from pathlib import Path
from backend.app.services.epub.cover_generator import generate_cover_image
from backend.app.services.epub.generator import EPUBGenerator
from PIL import Image
import io

def test_cover_image_generation():
    cover_bytes = generate_cover_image(
        date_str="2026-11-13",
        article_count=8,
        topics_summary="AI, Rust, Hardware"
    )
    assert len(cover_bytes) > 5000
    img = Image.open(io.BytesIO(cover_bytes))
    assert img.size == (1600, 2400)
    assert img.mode == "RGB"

def test_epub3_generation_and_zip_structure(tmp_path: Path):
    test_articles = [
        {
            "id": "art_1",
            "title": "Deep Dive into Modern E-Ink Displays",
            "author": "Nikola Tesla",
            "published_at": "2026-11-13 14:30:00",
            "url": "https://example.com/eink",
            "source_name": "Display Tech Review",
            "word_count": 450,
            "clean_html": "<p>E-ink displays reflect ambient light just like physical paper, resulting in drastically reduced eye fatigue.</p>",
            "images": [
                {
                    "id": "img_art_1_0",
                    "file_name": "images/art_art_1_0.jpg",
                    "media_type": "image/jpeg",
                    "content": generate_cover_image("2026-11-13", 1, "test")[:1000] # small mock jpeg bytes
                }
            ]
        },
        {
            "id": "art_2",
            "title": "Asynchronous Architectures in 2026",
            "author": "Grace Hopper",
            "url": "https://example.com/async",
            "source_name": "Systems Weekly",
            "word_count": 620,
            "clean_html": "<p>Concurrency models have transitioned toward structured concurrency with async/await primitives.</p>",
            "images": []
        }
    ]

    epub_out = tmp_path / "test_digest.epub"
    cover_out = tmp_path / "test_cover.jpg"

    file_path, file_size = EPUBGenerator.build_daily_edition(
        date_str="2026-11-13",
        articles=test_articles,
        output_path=epub_out,
        cover_output_path=cover_out
    )

    assert epub_out.exists()
    assert file_size > 0
    assert cover_out.exists()

    # Validate EPUB Zip Container structure
    with zipfile.ZipFile(epub_out, "r") as z:
        namelist = z.namelist()

        # EPUB mandatory files
        assert "mimetype" in namelist
        assert z.read("mimetype").decode("utf-8").strip() == "application/epub+zip"
        assert "META-INF/container.xml" in namelist

        # EPUB 3 Navigation & EPUB 2 NCX Fallback
        assert any("nav.xhtml" in name for name in namelist)
        assert any("toc.ncx" in name for name in namelist)
        assert any("content.opf" in name for name in namelist)

        # Chapters
        assert any("chapter_1.xhtml" in name for name in namelist)
        assert any("chapter_2.xhtml" in name for name in namelist)
        ch1_name = next(name for name in namelist if "chapter_1.xhtml" in name)
        ch1_content = z.read(ch1_name).decode("utf-8")
        assert 'href="nav.xhtml"' in ch1_content
        assert "Table of Contents" in ch1_content
        assert "Read original article" not in ch1_content
        assert "Published:" in ch1_content
        assert "2026-11-13 14:30" in ch1_content

        # Stylesheet
        assert any("eink.css" in name for name in namelist)

        # Embedded Cover
        assert any("cover" in name.lower() for name in namelist)

        # Embedded Article Images
        assert any("art_art_1_0.jpg" in name for name in namelist)
