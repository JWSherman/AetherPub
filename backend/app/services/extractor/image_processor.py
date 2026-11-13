import io
import re
from PIL import Image
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from backend.app.core.config import settings

class ImageProcessor:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def process_article_images(self, html_content: str, article_id: str, base_url: str = "") -> tuple[str, list[dict]]:
        """
        Parses <img> tags, downloads images, keeps RGB colors,
        downscales to max 1600px, and rewrites paths for EPUB.
        Returns: (updated_xhtml, list_of_image_manifest_items)
        """
        soup = BeautifulSoup(html_content, "html.parser")
        images_manifest = []

        for idx, img in enumerate(soup.find_all("img")):
            src = img.get("src")
            if not src:
                img.decompose()
                continue

            if not src.startswith("http://") and not src.startswith("https://"):
                if base_url:
                    src = urljoin(base_url, src)
                else:
                    img.decompose()
                    continue

            try:
                resp = await self.client.get(src, timeout=8.0, follow_redirects=True)
                if resp.status_code != 200 or len(resp.content) < 400:
                    img.decompose()
                    continue

                pil_img = Image.open(io.BytesIO(resp.content))

                # Color Preservation: Handle RGBA / transparency
                if pil_img.mode in ("RGBA", "LA") or (pil_img.mode == "P" and "transparency" in pil_img.info):
                    background = Image.new("RGB", pil_img.size, (255, 255, 255))
                    alpha = pil_img.convert("RGBA").split()[-1]
                    background.paste(pil_img.convert("RGB"), mask=alpha)
                    pil_img = background
                elif pil_img.mode != "RGB":
                    pil_img = pil_img.convert("RGB")

                # Downsample if oversized
                pil_img.thumbnail((settings.MAX_IMAGE_WIDTH, settings.MAX_IMAGE_HEIGHT), Image.Resampling.LANCZOS)

                # Save as compressed RGB JPEG
                buffer = io.BytesIO()
                pil_img.save(buffer, format="JPEG", quality=settings.JPEG_QUALITY, optimize=True)
                img_bytes = buffer.getvalue()

                # Internal EPUB relative path
                img_filename = f"art_{article_id}_{idx}.jpg"
                epub_rel_path = f"images/{img_filename}"

                # Update img tag in HTML
                img["src"] = epub_rel_path
                img["alt"] = img.get("alt", "Illustration")
                if "loading" in img.attrs:
                    del img["loading"]

                images_manifest.append({
                    "id": f"img_{article_id}_{idx}",
                    "file_name": epub_rel_path,
                    "media_type": "image/jpeg",
                    "content": img_bytes
                })
            except Exception:
                # If image fails to load or parse, cleanly remove it so it doesn't break EPUB rendering
                img.decompose()

        return str(soup), images_manifest
