import pytest
from backend.app.services.extractor.readability import ReadabilityService
from backend.app.services.extractor.image_processor import ImageProcessor
from PIL import Image
import io
import httpx

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>The Evolution of Modern Web Browsers</title>
    <meta name="author" content="Ada Lovelace">
</head>
<body>
    <nav><a href="/">Home</a><a href="/news">News</a></nav>
    <article>
        <h1>The Evolution of Modern Web Browsers</h1>
        <p>Web browsers have evolved from rudimentary document viewers into full-fledged operating environments capable of running complex applications.</p>
        <p>With rendering engines like Blink and Gecko, performance has reached unprecedented levels of responsiveness and web standard compliance.</p>
        <figure>
            <img src="https://example.com/assets/diagram.png" alt="Architecture Diagram">
            <figcaption>Figure 1: Rendering Pipeline</figcaption>
        </figure>
    </article>
    <script>alert('track');</script>
</body>
</html>
"""

def test_readability_extraction():
    result = ReadabilityService.extract_article(SAMPLE_HTML, url="https://example.com/browsers")
    assert result is not None
    assert "Modern Web Browsers" in result["title"]
    assert result["author"] == "Ada Lovelace" or result["author"] is None
    assert result["word_count"] > 25
    assert "track" not in result["clean_html"]  # <script> tag stripped
    assert result["content_hash"] is not None

@pytest.mark.asyncio
async def test_image_processor_color_preservation():
    # Create a small RGB test image with vivid red, green, and blue pixels
    test_img = Image.new("RGB", (200, 200), color=(255, 0, 128))
    img_buf = io.BytesIO()
    test_img.save(img_buf, format="PNG")
    raw_bytes = img_buf.getvalue()

    # Mock transport returning this image
    transport = httpx.MockTransport(lambda req: httpx.Response(200, content=raw_bytes))
    async with httpx.AsyncClient(transport=transport) as client:
        processor = ImageProcessor(client)
        html_input = '<p>Illustration: <img src="https://test.com/vivid.png" /></p>'
        clean_html, manifest = await processor.process_article_images(html_input, article_id="art123")

        assert len(manifest) == 1
        assert manifest[0]["media_type"] == "image/jpeg"
        assert "images/art_art123_0.jpg" in clean_html

        # Verify output image bytes is RGB JPEG (not grayscale)
        out_img = Image.open(io.BytesIO(manifest[0]["content"]))
        assert out_img.mode == "RGB"
        # Check pixel color preserves chromaticity
        r, g, b = out_img.getpixel((10, 10))
        assert r > 200 and b > 100  # vivid pinkish red preserved!

def test_readability_transforms_tei_graphic_and_headings():
    # Verify that extracted HTML contains <img>, <h1>, and <a> rather than <graphic>, <head>, <ref>
    result = ReadabilityService.extract_article(SAMPLE_HTML, url="https://example.com/browsers")
    assert result is not None
    clean_html = result["clean_html"]
    assert "<graphic" not in clean_html
    assert "<img" in clean_html
    assert "https://example.com/assets/diagram.png" in clean_html
    assert "<head" not in clean_html
    assert "<doc" not in clean_html
    assert "<?xml" not in clean_html

@pytest.mark.asyncio
async def test_image_processor_handles_graphic_tags_and_caching():
    test_img = Image.new("RGB", (100, 100), color=(0, 200, 255))
    buf = io.BytesIO()
    test_img.save(buf, format="JPEG")
    raw_bytes = buf.getvalue()

    transport = httpx.MockTransport(lambda req: httpx.Response(200, content=raw_bytes))
    async with httpx.AsyncClient(transport=transport) as client:
        processor = ImageProcessor(client)
        # Test input with both <graphic> and <img>
        input_html = '<p><graphic alt="Screenshot" src="https://example.com/shot.jpg" /></p>'
        epub_html, manifest = await processor.process_article_images(input_html, article_id="gi_999", base_url="https://example.com")

        assert len(manifest) == 1
        assert "images/art_gi_999_0.jpg" in epub_html
        assert "<graphic" not in epub_html
        assert "<img" in epub_html
        assert manifest[0]["file_name"] == "images/art_gi_999_0.jpg"

        # Two-stage re-compilation test: ensure images are not decomposed on second pass
        epub_html2, manifest2 = await processor.process_article_images(epub_html, article_id="gi_999", base_url="https://example.com")
        assert len(manifest2) == 1
        assert "images/art_gi_999_0.jpg" in epub_html2
        assert "<img" in epub_html2
