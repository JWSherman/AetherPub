import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

def get_system_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Finds available system fonts on Windows/Linux or falls back to Pillow default."""
    candidates = [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()

def generate_cover_image(date_str: str, article_count: int, topics_summary: str = "Curated Web Edition") -> bytes:
    """
    Renders a high-resolution 1600x2400 cover image for the daily edition.
    """
    width, height = 1600, 2400
    # Deep slate / twilight background (RGB)
    img = Image.new("RGB", (width, height), (15, 23, 42))
    draw = ImageDraw.Draw(img)

    # Outer geometric border
    draw.rectangle([60, 60, width - 60, height - 60], outline=(6, 182, 212), width=6)
    draw.rectangle([80, 80, width - 80, height - 80], outline=(71, 85, 105), width=2)
    draw.rectangle([100, 100, width - 100, height - 100], outline=(30, 41, 59), width=1)

    # Fonts
    font_masthead = get_system_font(110)
    font_sub = get_system_font(52)
    font_date = get_system_font(60)
    font_meta = get_system_font(44)
    font_small = get_system_font(34)

    # Masthead
    draw.text((width // 2, 420), "AETHERPUB", fill=(255, 255, 255), font=font_masthead, anchor="mm")
    draw.line([(width // 2 - 280, 510), (width // 2 + 280, 510)], fill=(6, 182, 212), width=5)

    # Subtitle
    draw.text((width // 2, 590), "DAILY OMNIBUS DIGEST", fill=(148, 163, 184), font=font_sub, anchor="mm")

    # Center Date Box
    box_top, box_bottom = 1000, 1220
    box_left, box_right = width // 2 - 420, width // 2 + 420
    draw.rectangle([box_left, box_top, box_right, box_bottom], fill=(30, 41, 59), outline=(6, 182, 212), width=3)
    draw.text((width // 2, 1110), date_str.upper(), fill=(255, 255, 255), font=font_date, anchor="mm")

    # Topic summary card
    summary_box_top = 1450
    draw.rectangle([width // 2 - 500, summary_box_top, width // 2 + 500, summary_box_top + 160], fill=(15, 23, 42), outline=(51, 65, 85), width=2)
    draw.text((width // 2, summary_box_top + 80), topics_summary[:50], fill=(56, 189, 248), font=font_meta, anchor="mm")

    # Bottom Metadata
    meta_text = f"{article_count} Curated Articles  •  E-Reader Edition"
    draw.text((width // 2, 2060), meta_text, fill=(203, 213, 225), font=font_meta, anchor="mm")
    draw.text((width // 2, 2160), "Automated Ingestion & EPUB 3 Compilation", fill=(100, 116, 139), font=font_small, anchor="mm")

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90, optimize=True)
    return buf.getvalue()
