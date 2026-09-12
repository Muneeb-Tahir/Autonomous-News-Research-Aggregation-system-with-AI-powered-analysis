"""
RSS feed collector for the News Intelligence Agent.

Fetches and parses RSS/Atom feeds from configured sources.
Uses feedparser for robust XML parsing across feed formats.
"""

from typing import List, Dict, Optional
import feedparser
import requests
from requests.exceptions import RequestException, Timeout

from config.rss_sources import RSS_SOURCES
from utils.logger import get_logger
from utils.timezone_utils import now_utc_iso

logger = get_logger(__name__)

# Request timeout in seconds
REQUEST_TIMEOUT = 15


class RSSCollector:
    """Fetches and parses RSS feeds from all configured sources."""

    def __init__(self, sources: List[Dict] = None):
        """Initialize with RSS source list.

        Args:
            sources: List of source dicts. Defaults to RSS_SOURCES from config.
        """
        self.sources = sources or RSS_SOURCES
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "NewsIntelligenceAgent/1.0 (RSS Reader)",
            "Accept": "application/rss+xml, application/xml, text/xml, */*",
        })

    def fetch_all(self) -> tuple[List[Dict], List[str]]:
        """Fetch all RSS feeds, return raw items and failed sources.

        Processes each feed independently. If one feed fails,
        the rest continue normally.

        Returns:
            Tuple of (raw_items, failed_source_names).
            raw_items: List of dicts with article data + source metadata.
            failed_source_names: List of source names that failed.
        """
        all_items = []
        failed_sources = []

        logger.info(f"Fetching {len(self.sources)} RSS feeds...")

        for source in self.sources:
            try:
                items = self._fetch_single(source)
                all_items.extend(items)
                logger.debug(f"  ✓ {source['name']}: {len(items)} items")
            except Exception as e:
                failed_sources.append(source["name"])
                logger.warning(f"  ✗ {source['name']}: {e}")

        logger.info(
            f"RSS collection complete: {len(all_items)} items from "
            f"{len(self.sources) - len(failed_sources)}/{len(self.sources)} sources"
        )

        return all_items, failed_sources

    def _fetch_single(self, source: Dict) -> List[Dict]:
        """Fetch and parse a single RSS feed.

        Args:
            source: Source dict with name, url, category, quality.

        Returns:
            List of raw article dicts with source metadata attached.

        Raises:
            Exception: If feed cannot be fetched or parsed.
        """
        try:
            # Fetch the raw XML
            response = self.session.get(
                source["url"],
                timeout=REQUEST_TIMEOUT,
                allow_redirects=True,
            )
            response.raise_for_status()
        except Timeout:
            raise Exception(f"Timeout after {REQUEST_TIMEOUT}s")
        except RequestException as e:
            raise Exception(f"HTTP error: {e}")

        # Parse the feed
        feed = feedparser.parse(response.content)

        if feed.bozo and not feed.entries:
            raise Exception(f"Feed parse error: {feed.bozo_exception}")

        items = []
        collected_at = now_utc_iso()

        for entry in feed.entries:
            item = self._parse_entry(entry, source, collected_at)
            if item:
                items.append(item)

        return items

    def _parse_entry(
        self, entry: feedparser.FeedParserDict, source: Dict, collected_at: str
    ) -> Optional[Dict]:
        """Parse a single RSS entry into a raw article dict.

        Args:
            entry: feedparser entry object.
            source: Source metadata dict.
            collected_at: Collection timestamp (ISO 8601).

        Returns:
            Raw article dict, or None if entry is invalid.
        """
        # Title is required
        title = entry.get("title", "").strip()
        if not title:
            return None

        # URL is required
        url = entry.get("link", "").strip()
        if not url:
            return None

        # Description / summary
        description = ""
        if entry.get("summary"):
            description = entry["summary"]
        elif entry.get("description"):
            description = entry["description"]

        # Full content (some feeds provide it)
        content = ""
        if entry.get("content"):
            # content is usually a list of dicts
            for c in entry.get("content", []):
                if isinstance(c, dict) and c.get("value"):
                    content = c["value"]
                    break
        elif entry.get("content:encoded"):
            content = entry["content:encoded"]

        # Published date
        published = (
            entry.get("published")
            or entry.get("updated")
            or entry.get("created")
            or ""
        )

        # Author
        author = entry.get("author") or entry.get("dc:creator")

        # Image
        image_url = self._extract_image(entry)

        return {
            "title": title,
            "url": url,
            "description": description,
            "content": content,
            "published_at_raw": published,
            "author": author,
            "image_url": image_url,
            "collected_at": collected_at,
            # Source metadata
            "source_name": source["name"],
            "source_quality": source["quality"],
            "source_category": source["category"],
            "source_type": "rss",
        }

    def _extract_image(self, entry: feedparser.FeedParserDict) -> Optional[str]:
        """Extract image URL from an RSS entry.

        RSS feeds store images in various locations. This tries all common ones.

        Args:
            entry: feedparser entry object.

        Returns:
            Image URL string, or None if no image found.
        """
        # 1. media:content
        media_content = entry.get("media_content", [])
        if media_content:
            for media in media_content:
                if isinstance(media, dict):
                    url = media.get("url", "")
                    media_type = media.get("type", "")
                    if url and ("image" in media_type or not media_type):
                        return url

        # 2. media:thumbnail
        media_thumb = entry.get("media_thumbnail", [])
        if media_thumb:
            for thumb in media_thumb:
                if isinstance(thumb, dict) and thumb.get("url"):
                    return thumb["url"]

        # 3. enclosure
        enclosures = entry.get("enclosures", [])
        for enc in enclosures:
            if isinstance(enc, dict):
                enc_type = enc.get("type", "")
                if "image" in enc_type and enc.get("href"):
                    return enc["href"]
                elif enc.get("url") and "image" in enc.get("type", ""):
                    return enc["url"]

        # 4. links with image type
        links = entry.get("links", [])
        for link in links:
            if isinstance(link, dict) and "image" in link.get("type", ""):
                return link.get("href", "")

        return None
