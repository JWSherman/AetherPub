import io
import re
import hashlib
from pathlib import Path
from PIL import Image
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from backend.app.core.config import settings

class ImageProcessor:
    def __init__(
        self,
        client: httpx.AsyncClient,
        jpeg_quality: int | None = None,
        max_dimension: int | None = None
    ):
        self.client = client
        raw_q = jpeg_quality if jpeg_quality is not None else settings.JPEG_QUALITY
        raw_dim = max_dimension if max_dimension is not None else settings.MAX_IMAGE_WIDTH
        self.jpeg_quality = max(10, min(95, int(raw_q)))
        self.max_dimension = max(300, min(2400, int(raw_dim)))

    def _encode_rgb_jpeg(self, raw_bytes: bytes, quality: int | None = None, max_dim: int | None = None) -> bytes:
        """
        Converts raw image bytes into an RGB JPEG (preserving full color for Color E-Ink)
        at the configured quality and maximum dimension.
        """
        q = quality if quality is not None else self.jpeg_quality
        dim = max_dim if max_dim is not None else self.max_dimension

        pil_img = Image.open(io.BytesIO(raw_bytes))

        # Color Preservation: Handle RGBA / transparency
        if pil_img.mode in ("RGBA", "LA") or (pil_img.mode == "P" and "transparency" in pil_img.info):
            background = Image.new("RGB", pil_img.size, (255, 255, 255))
            alpha = pil_img.convert("RGBA").split()[-1]
            background.paste(pil_img.convert("RGB"), mask=alpha)
            pil_img = background
        elif pil_img.mode != "RGB":
            pil_img = pil_img.convert("RGB")

        # Downsample if oversized
        pil_img.thumbnail((dim, dim), Image.Resampling.LANCZOS)

        # Save as compressed RGB JPEG
        buffer = io.BytesIO()
        pil_img.save(buffer, format="JPEG", quality=q, optimize=True)
        return buffer.getvalue()

    async def process_article_images(self, html_content: str, article_id: str, base_url: str = "") -> tuple[str, list[dict]]:
        """
        Parses <img> and <graphic> tags, downloads images, keeps RGB colors,
        downscales to configured max dimension, encodes at configured JPEG quality,
        caches locally, and rewrites paths for EPUB.
        Returns: (updated_xhtml, list_of_image_manifest_items)
        """
        soup = BeautifulSoup(html_content, "html.parser")

        # Cleanup leftover XML/TEI artifacts if present
        for bad in soup.find_all(["comments", "script", "style", "iframe", "form", "button"]):
            bad.decompose()

        for h in soup.find_all("head"):
            rend = h.get("rend", "")
            h.name = rend if rend in ("h1", "h2", "h3", "h4", "h5", "h6") else "h2"
            if "rend" in h.attrs:
                del h.attrs["rend"]

        for r in soup.find_all("ref"):
            r.name = "a"
            target = r.get("target") or r.get("href") or ""
            if target:
                r["href"] = urljoin(base_url, target) if base_url else target
            if "target" in r.attrs:
                del r.attrs["target"]

        images_manifest = []

        # Find both <img> and <graphic> tags
        image_tags = soup.find_all(["img", "graphic"])

        for idx, img in enumerate(image_tags):
            if img.name == "graphic":
                img.name = "img"

            src = (
                img.get("src")
                or img.get("url")
                or img.get("data-src")
                or img.get("data-original-src")
            )
            if not src:
                img.decompose()
                continue

            # Internal EPUB relative path for this article
            img_filename = f"art_{article_id}_{idx}.jpg"
            epub_rel_path = f"images/{img_filename}"
            target_cache_path = settings.MEDIA_DIR / img_filename

            # 1. Check if src is ALREADY an internal EPUB path (e.g. from prior processing)
            if src.startswith("images/") or src.startswith("images/art_"):
                existing_file = settings.MEDIA_DIR / Path(src).name
                if existing_file.exists():
                    raw_cached = existing_file.read_bytes()
                    try:
                        img_bytes = self._encode_rgb_jpeg(raw_cached)
                    except Exception:
                        img_bytes = raw_cached
                    img["src"] = epub_rel_path
                    img["alt"] = img.get("alt") or "Illustration"
                    images_manifest.append({
                        "id": f"img_{article_id}_{idx}",
                        "file_name": epub_rel_path,
                        "media_type": "image/jpeg",
                        "content": img_bytes
                    })
                    continue
                elif target_cache_path.exists():
                    raw_cached = target_cache_path.read_bytes()
                    try:
                        img_bytes = self._encode_rgb_jpeg(raw_cached)
                    except Exception:
                        img_bytes = raw_cached
                    img["src"] = epub_rel_path
                    img["alt"] = img.get("alt") or "Illustration"
                    images_manifest.append({
                        "id": f"img_{article_id}_{idx}",
                        "file_name": epub_rel_path,
                        "media_type": "image/jpeg",
                        "content": img_bytes
                    })
                    continue
                elif img.get("data-original-src"):
                    src = img["data-original-src"]
                else:
                    img.decompose()
                    continue

            # 2. Check if URL is relative; resolve against base_url
            if not src.startswith("http://") and not src.startswith("https://"):
                if base_url:
                    src = urljoin(base_url, src)
                else:
                    img.decompose()
                    continue

            # 3. Check persistent media cache by URL hash
            url_hash = hashlib.sha256(src.encode("utf-8")).hexdigest()[:16]
            url_cache_path = settings.MEDIA_DIR / f"cache_{url_hash}.jpg"

            img_bytes: bytes | None = None
            if url_cache_path.exists():
                try:
                    raw_cached = url_cache_path.read_bytes()
                    img_bytes = self._encode_rgb_jpeg(raw_cached)
                except Exception:
                    img_bytes = None

            if not img_bytes:
                try:
                    resp = await self.client.get(src, timeout=10.0, follow_redirects=True)
                    if resp.status_code != 200 or len(resp.content) < 400:
                        img.decompose()
                        continue

                    # Save master copy to persistent cache by URL hash
                    master_bytes = self._encode_rgb_jpeg(
                        resp.content,
                        quality=max(self.jpeg_quality, settings.JPEG_QUALITY),
                        max_dim=max(self.max_dimension, settings.MAX_IMAGE_WIDTH)
                    )
                    url_cache_path.write_bytes(master_bytes)

                    # Encode at configured quality/dimension for the EPUB
                    img_bytes = self._encode_rgb_jpeg(resp.content)
                except Exception:
                    # If image fails to load or parse, cleanly remove it so it doesn't break EPUB rendering
                    img.decompose()
                    continue

            # Save under article-specific name as well
            if img_bytes:
                try:
                    target_cache_path.write_bytes(img_bytes)
                except Exception:
                    pass

                # Update img tag in HTML
                img["src"] = epub_rel_path
                img["alt"] = img.get("alt") or "Illustration"
                img["data-original-src"] = src

                # Clean up noisy/disruptive attributes for EPUB
                for attr in ["loading", "srcset", "sizes", "fetchpriority", "typeof", "rend", "url"]:
                    if attr in img.attrs:
                        del img.attrs[attr]

                images_manifest.append({
                    "id": f"img_{article_id}_{idx}",
                    "file_name": epub_rel_path,
                    "media_type": "image/jpeg",
                    "content": img_bytes
                })

        # If inside <main> or <doc>, unwrap so clean HTML is returned
        main_elem = soup.find("main") or soup.find("doc")
        if main_elem:
            content = main_elem.decode_contents()
            clean_soup = BeautifulSoup(content, "html.parser")
            return str(clean_soup), images_manifest

        return str(soup), images_manifest
