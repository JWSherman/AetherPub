from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from backend.app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False, future=True)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

async def sanitize_legacy_articles():
    from backend.app.models.entities import Article
    from sqlalchemy import select
    from bs4 import BeautifulSoup
    from urllib.parse import urljoin

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Article).where(
                (Article.clean_html.contains("<graphic")) | (Article.clean_html.contains("<doc"))
            )
        )
        articles = result.scalars().all()
        if not articles:
            return

        for art in articles:
            html = art.clean_html
            soup = BeautifulSoup(html, "xml" if "<doc" in html or "<?xml" in html else "html.parser")
            for bad in soup.find_all(["comments", "script", "style", "iframe", "form", "button"]):
                bad.decompose()
            for g in soup.find_all("graphic"):
                g.name = "img"
                src = g.get("src") or g.get("url") or ""
                if src:
                    g["src"] = urljoin(art.url, src) if art.url else src
                if "url" in g.attrs and g.attrs["url"] != g.attrs.get("src"):
                    del g.attrs["url"]
            for r in soup.find_all("ref"):
                r.name = "a"
                target = r.get("target") or r.get("href") or ""
                if target:
                    r["href"] = urljoin(art.url, target) if art.url else target
                if "target" in r.attrs:
                    del r.attrs["target"]
            for h in soup.find_all("head"):
                rend = h.get("rend", "")
                h.name = rend if rend in ("h1", "h2", "h3", "h4", "h5", "h6") else "h2"
                if "rend" in h.attrs:
                    del h.attrs["rend"]
            for hi in soup.find_all("hi"):
                rend = hi.get("rend", "")
                if rend == "bold":
                    hi.name = "strong"
                elif rend == "italic":
                    hi.name = "em"
                if "rend" in hi.attrs:
                    del hi.attrs["rend"]

            main_elem = soup.find("main") or soup.find("body") or soup.find("doc") or soup.find(class_="article-content")
            content = main_elem.decode_contents() if main_elem else soup.decode_contents()
            clean_soup = BeautifulSoup(content, "html.parser")
            art.clean_html = f'<div class="article-content">{clean_soup.decode_contents()}</div>'

        await session.commit()

from sqlalchemy import text

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        def migrate_schema(sync_conn):
            try:
                res = sync_conn.execute(text("PRAGMA table_info(sources)"))
                columns = [row[1] for row in res.fetchall()]
                if columns and "weight" not in columns:
                    sync_conn.execute(text("ALTER TABLE sources ADD COLUMN weight FLOAT DEFAULT 0.0"))
            except Exception:
                pass

        await conn.run_sync(migrate_schema)

    try:
        await sanitize_legacy_articles()
    except Exception:
        pass
