"""
Article normalizer for the News Intelligence Agent.

Converts raw articles from any source (RSS, NewsAPI) into
the common Article schema. Also handles filtering.
"""

import re
from typing import List, Dict, Optional
from datetime import datetime, timezone

from database.models import Article
from config.settings import ASCII_RATIO_THRESHOLD, MAX_AGE_HOURS
from utils.logger import get_logger
from utils.timezone_utils import parse_to_utc, now_utc_iso, hours_since, now_utc

logger = get_logger(__name__)

# HTML tag removal pattern
HTML_TAG_PATTERN = re.compile(r"<[^>]+>")

# HTML entity patterns
HTML_ENTITIES = {
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&#39;": "'",
    "&apos;": "'",
    "&nbsp;": " ",
    "&#8230;": "...",
    "&#8217;": "'",
    "&#8220;": '"',
    "&#8221;": '"',
}


class ArticleNormalizer:
    """Converts raw article dicts into Article objects."""

    def normalize_all(self, raw_items: List[Dict]) -> List[Article]:
        """Normalize all raw items to Article objects.

        Args:
            raw_items: List of raw dicts from collectors.

        Returns:
            List of Article objects with cleaned data.
        """
        articles = []

        for item in raw_items:
            try:
                article = self._normalize_item(item)
                if article:
                    articles.append(article)
            except Exception as e:
                logger.debug(f"Failed to normalize article: {e}")

        return articles

    def _normalize_item(self, item: Dict) -> Optional[Article]:
        """Normalize a single raw item to an Article.

        Args:
            item: Raw article dict from RSS or NewsAPI collector.

        Returns:
            Article object, or None if item is invalid.
        """
        # Required fields
        title = self._clean_text(item.get("title", ""))
        url = item.get("url", "").strip()

        if not title or not url:
            return None

        # Clean text fields
        description = self._clean_text(item.get("description", ""))
        content = self._clean_text(item.get("content", ""))

        # Parse publication date to UTC
        published_raw = item.get("published_at_raw", "")
        published_dt = parse_to_utc(published_raw)
        published_at = published_dt.isoformat()

        # Collected timestamp
        collected_at = item.get("collected_at", now_utc_iso())

        # Source metadata
        source_name = item.get("source_name", "Unknown")
        source_quality = item.get("source_quality", 5)
        category = item.get("source_category", "GENERAL").upper()

        # Optional fields
        author = item.get("author")
        if author:
            author = self._clean_text(author)

        image_url = item.get("image_url")

        return Article(
            title=title,
            url=url,
            description=description,
            content=content,
            source_name=source_name,
            source_quality=min(max(source_quality, 1), 10),  # Clamp 1-10
            category=category,
            published_at=published_at,
            collected_at=collected_at,
            author=author,
            image_url=image_url,
            language="en",
        )

    def filter_articles(self, articles: List[Article]) -> List[Article]:
        """Filter out low-quality or irrelevant articles.

        Removes:
        - Non-English articles
        - Articles older than MAX_AGE_HOURS
        - Articles with empty/meaningless titles
        - Articles with [Removed] title (NewsAPI placeholder)

        Args:
            articles: List of normalized Article objects.

        Returns:
            Filtered list.
        """
        before = len(articles)
        filtered = []

        for article in articles:
            # Skip non-English
            if not self._is_english(article.title):
                continue

            # Skip old articles
            try:
                pub_dt = datetime.fromisoformat(article.published_at)
                if pub_dt.tzinfo is None:
                    pub_dt = pub_dt.replace(tzinfo=timezone.utc)
                if hours_since(pub_dt) > MAX_AGE_HOURS:
                    continue
            except (ValueError, TypeError):
                pass  # Keep articles with unparseable dates

            # Skip placeholder/removed articles
            lower_title = article.title.lower().strip()
            if lower_title in ("[removed]", "removed", "", "null", "undefined"):
                continue

            # Skip very short titles (likely garbage)
            if len(article.title) < 10:
                continue

            filtered.append(article)

        removed = before - len(filtered)
        if removed > 0:
            logger.debug(f"Filtered out {removed} articles ({before} → {len(filtered)})")

        return filtered

    def _clean_text(self, text: str) -> str:
        """Clean text by removing HTML tags, entities, and extra whitespace.

        Args:
            text: Raw text that may contain HTML.

        Returns:
            Clean plain text.
        """
        if not text:
            return ""

        # Remove HTML tags
        text = HTML_TAG_PATTERN.sub("", text)

        # Decode HTML entities
        for entity, replacement in HTML_ENTITIES.items():
            text = text.replace(entity, replacement)

        # Remove CDATA markers
        text = text.replace("<![CDATA[", "").replace("]]>", "")

        # Normalize whitespace
        text = re.sub(r"\s+", " ", text).strip()

        return text

    def _is_english(self, text: str) -> bool:
        """Check if text is likely English using ASCII character ratio.

        Args:
            text: Text to check.

        Returns:
            True if text is likely English.
        """
        if not text:
            return False

        ascii_chars = sum(1 for c in text if ord(c) < 128)
        ratio = ascii_chars / len(text)
        return ratio >= ASCII_RATIO_THRESHOLD
