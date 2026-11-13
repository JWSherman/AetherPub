import re
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
import feedparser

COMMON_FEED_PATHS = [
    "/feed", "/rss", "/rss.xml", "/atom.xml", "/feed.xml", "/index.xml",
    "/feeds/posts/default", "/blog/feed", "/news/feed", "/feed/"
]

class DiscoveryService:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def probe_source(self, base_url: str) -> dict:
        """
        Probes a website to discover title, RSS/Atom feeds, and latest articles for preview.
        """
        base_url = base_url.strip()
        if not base_url.startswith("http://") and not base_url.startswith("https://"):
            base_url = "https://" + base_url

        parsed = urlparse(base_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"

        # 1. Fetch homepage
        resp = await self.client.get(base_url, timeout=10.0)
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")
        site_name = soup.title.string.strip() if soup.title and soup.title.string else parsed.netloc

        # 2. Check for <link rel="alternate"> feeds
        feed_url = None
        for link in soup.find_all("link", rel=lambda r: r and any("alternate" in rel_item for rel_item in (r if isinstance(r, list) else [r]))):
            t = link.get("type", "")
            if "rss" in t or "atom" in t or "xml" in t:
                feed_url = urljoin(base_url, link.get("href", ""))
                break

        # 3. If no link tag, probe common paths
        if not feed_url:
            for path in COMMON_FEED_PATHS:
                candidate = urljoin(origin, path)
                try:
                    probe = await self.client.head(candidate, timeout=3.5)
                    ct = probe.headers.get("content-type", "").lower()
                    if probe.status_code == 200 and any(kw in ct for kw in ["xml", "rss", "atom"]):
                        feed_url = candidate
                        break
                except Exception:
                    continue

        # 4. Preview recent items
        preview_articles = []
        crawl_mode = "html"

        if feed_url:
            crawl_mode = "rss"
            try:
                feed_resp = await self.client.get(feed_url, timeout=8.0)
                parsed_feed = feedparser.parse(feed_resp.text)
                for entry in parsed_feed.entries[:5]:
                    link = entry.get("link", "")
                    title = entry.get("title", "Untitled")
                    if link:
                        preview_articles.append({"title": title, "url": link})
            except Exception:
                pass

        if not preview_articles:
            # Fall back to heuristic HTML link extraction
            seen_urls = set()
            for a in soup.find_all("a", href=True):
                href = urljoin(base_url, a["href"])
                p = urlparse(href)
                # Same domain and has subpath
                if p.netloc == parsed.netloc and len(p.path) > 3:
                    text = a.get_text(strip=True)
                    if len(text) > 20 and href not in seen_urls and not href.endswith((".png", ".jpg", ".pdf", ".css", ".js")):
                        seen_urls.add(href)
                        preview_articles.append({"title": text, "url": href})
                if len(preview_articles) >= 5:
                    break

        return {
            "name": site_name,
            "base_url": base_url,
            "feed_url": feed_url,
            "crawl_mode": crawl_mode,
            "preview": preview_articles
        }

    async def fetch_candidate_urls(self, source_base_url: str, source_feed_url: str | None) -> list[dict]:
        """
        Fetches fresh candidate articles from either RSS feed or shallow HTML crawl.
        """
        candidates = []
        if source_feed_url:
            try:
                resp = await self.client.get(source_feed_url, timeout=12.0)
                parsed = feedparser.parse(resp.text)
                for entry in parsed.entries:
                    link = entry.get("link")
                    title = entry.get("title", "")
                    if link:
                        candidates.append({
                            "url": link,
                            "title": title
                        })
                return candidates
            except Exception:
                pass

        # Fallback shallow HTML crawl
        try:
            resp = await self.client.get(source_base_url, timeout=10.0)
            soup = BeautifulSoup(resp.text, "html.parser")
            parsed_base = urlparse(source_base_url)
            seen = set()
            for a in soup.find_all("a", href=True):
                href = urljoin(source_base_url, a["href"])
                p = urlparse(href)
                if p.netloc == parsed_base.netloc and len(p.path) > 4:
                    text = a.get_text(strip=True)
                    if len(text) > 15 and href not in seen and not href.endswith((".png", ".jpg", ".zip", ".pdf")):
                        seen.add(href)
                        candidates.append({"url": href, "title": text})
                if len(candidates) >= 20:
                    break
        except Exception:
            pass

        return candidates
