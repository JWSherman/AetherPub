import uuid
from datetime import datetime, date
from pathlib import Path
from ebooklib import epub
from backend.app.core.config import settings
from backend.app.services.epub.stylesheet import EINK_STYLESHEET
from backend.app.services.epub.cover_generator import generate_cover_image

class EPUBGenerator:
    @staticmethod
    def build_daily_edition(
        date_str: str,
        articles: list[dict],
        output_path: Path,
        cover_output_path: Path | None = None
    ) -> tuple[Path, int]:
        """
        Builds a compliant EPUB 3 document from curated articles.
        Returns: (output_path, file_size_bytes)
        """
        book = epub.EpubBook()

        # Metadata
        edition_id = f"aetherpub-{date_str}-{uuid.uuid4().hex[:6]}"
        book.set_identifier(edition_id)
        book.set_title(f"AetherPub Daily – {date_str}")
        book.set_language("en")
        book.add_author("AetherPub Engine")

        # Procedural Cover
        cover_bytes = generate_cover_image(
            date_str=date_str,
            article_count=len(articles),
            topics_summary=f"{len(articles)} Articles • Curated Feed"
        )
        book.set_cover("images/cover.jpg", cover_bytes)

        if cover_output_path:
            cover_output_path.write_bytes(cover_bytes)

        # Ingest CSS
        style_item = epub.EpubItem(
            uid="style_eink",
            file_name="style/eink.css",
            media_type="text/css",
            content=EINK_STYLESHEET.encode("utf-8")
        )
        book.add_item(style_item)

        chapters = []
        spine = ["cover", "nav"]

        for idx, art in enumerate(articles, 1):
            ch = epub.EpubHtml(
                title=art["title"],
                file_name=f"chapter_{idx}.xhtml",
                lang="en"
            )
            ch.add_item(style_item)

            author_line = f"<strong>Author:</strong> {art['author']}<br />" if art.get("author") else ""
            reading_time = max(1, art.get("word_count", 0) // 220)
            source_line = f"<strong>Source:</strong> {art.get('source_name', 'Web')}<br />"

            pub_val = art.get("published_at") or art.get("created_at") or datetime.now()
            formatted_pub = None
            if isinstance(pub_val, datetime):
                formatted_pub = pub_val.strftime("%Y-%m-%d %H:%M")
            elif isinstance(pub_val, date):
                formatted_pub = pub_val.strftime("%Y-%m-%d")
            elif isinstance(pub_val, str) and pub_val.strip():
                try:
                    from dateutil import parser
                    parsed_dt = parser.parse(pub_val)
                    formatted_pub = parsed_dt.strftime("%Y-%m-%d %H:%M")
                except Exception:
                    formatted_pub = pub_val.strip()
            published_line = f"<strong>Published:</strong> {formatted_pub}<br />" if formatted_pub else ""

            meta_html = f"""
            <div class="article-meta">
                {source_line}
                {author_line}
                {published_line}
                <strong>Reading Time:</strong> ~{reading_time} min ({art.get('word_count', 0)} words)<br />
                <a href="nav.xhtml">&larr; Table of Contents</a>
            </div>
            """

            ch.content = f"""<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">
    <head>
        <title>{art['title']}</title>
        <link rel="stylesheet" type="text/css" href="style/eink.css" />
    </head>
    <body>
        <h1 class="chapter-title">{art['title']}</h1>
        {meta_html}
        <div class="article-body">
            {art['clean_html']}
        </div>
    </body>
</html>
""".encode("utf-8")

            book.add_item(ch)
            chapters.append(ch)
            spine.append(ch)

            # Embed color images attached to this article
            for img_item in art.get("images", []):
                item = epub.EpubItem(
                    uid=img_item["id"],
                    file_name=img_item["file_name"],
                    media_type=img_item["media_type"],
                    content=img_item["content"]
                )
                book.add_item(item)

        # Table of contents (both EPUB 2 NCX and EPUB 3 Nav)
        book.toc = tuple(chapters)
        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = spine

        # Write to disk
        epub.write_epub(str(output_path), book, {})
        file_size = output_path.stat().st_size
        return output_path, file_size
