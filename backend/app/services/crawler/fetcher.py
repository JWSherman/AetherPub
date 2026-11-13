import httpx
import asyncio
import random

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 AetherPub/1.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}

def create_http_client() -> httpx.AsyncClient:
    """Creates a configured resilient AsyncClient."""
    limits = httpx.Limits(max_keepalive_connections=10, max_connections=20)
    timeout = httpx.Timeout(connect=6.0, read=14.0, write=6.0, pool=10.0)
    return httpx.AsyncClient(headers=DEFAULT_HEADERS, limits=limits, timeout=timeout, follow_redirects=True)

async def polite_delay(min_ms: int = 200, max_ms: int = 600):
    """Adds a small polite delay between outgoing requests to prevent rate limiting."""
    delay = random.uniform(min_ms, max_ms) / 1000.0
    await asyncio.sleep(delay)
