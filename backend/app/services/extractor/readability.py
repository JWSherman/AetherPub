import trafilatura
from bs4 import BeautifulSoup
import re
from backend.app.services.curator.simhash import compute_simhash

class ReadabilityService:
    @staticmethod
    def extract_article(raw_html: str, url: str) -> dict | None:
        """
        Extracts clean article content using trafilatura with BeautifulSoup fallback.
        Returns strict XHTML content, clean text, metadata, and SimHash.
        """
        metadata = trafilatura.extract_metadata(raw_html, default_url=url)
        title = metadata.title if metadata and metadata.title else None
        author = metadata.author if metadata and metadata.author else None
        date_str = metadata.date if metadata and metadata.date else None

        # Try Trafilatura XML extraction
        xml_output = trafilatura.extract(
            raw_html,
            url=url,
            include_images=True,
            include_links=True,
            include_tables=True,
            output_format="xml"
        )

        clean_soup: BeautifulSoup | None = None

        if xml_output:
            clean_soup = BeautifulSoup(xml_output, "xml")
        else:
            # Fallback to BeautifulSoup heuristic extraction
            raw_soup = BeautifulSoup(raw_html, "html.parser")
            if not title:
                title = raw_soup.title.string.strip() if raw_soup.title and raw_soup.title.string else "Untitled Article"

            # Remove unwanted tags
            for bad in raw_soup.find_all(["script", "style", "nav", "footer", "header", "aside", "iframe", "form", "noscript"]):
                bad.decompose()

            # Find main article element
            article_elem = raw_soup.find("article") or raw_soup.find("main") or raw_soup.find(id=re.compile(r"content|post|article", re.I)) or raw_soup.find(class_=re.compile(r"content|post|article", re.I)) or raw_soup.body
            if article_elem:
                clean_soup = BeautifulSoup(str(article_elem), "html.parser")

        if not clean_soup:
            return None

        # Clean up any leftover scripts or tracking pixels
        for tag in clean_soup.find_all(["script", "style", "iframe", "form", "button"]):
            tag.decompose()

        plain_text = clean_soup.get_text(separator=" ", strip=True)
        words = plain_text.split()
        word_count = len(words)
        if word_count < 30:
            return None  # Discard navigation fragments or 404s

        if not title:
            h1 = clean_soup.find("h1")
            title = h1.get_text(strip=True) if h1 else "Untitled Article"

        excerpt = plain_text[:280] + "..." if len(plain_text) > 280 else plain_text
        content_hash = compute_simhash(plain_text)

        # Ensure valid XHTML: wrap in body div
        clean_html = f'<div class="article-content">{clean_soup.decode_contents()}</div>'

        return {
            "title": title,
            "author": author,
            "published_at": date_str,
            "clean_html": clean_html,
            "plain_text": plain_text,
            "excerpt": excerpt,
            "word_count": word_count,
            "content_hash": content_hash
        }
