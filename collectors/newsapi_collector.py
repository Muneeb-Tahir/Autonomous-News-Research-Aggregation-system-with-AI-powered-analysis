"""
NewsAPI collector for the News Intelligence Agent.

Fetches news from NewsAPI.org with strict rate limiting.
Free tier: 100 requests/day.

Budget strategy:
- Scheduled category calls: ~25 req/day
- Scheduled keyword calls: ~15 req/day
- Reserved for on-demand: ~60 req/day
"""

from typing import List, Dict, Optional
from datetime import datetime, timezone
import requests
from requests.exceptions import RequestException

from config.settings import NEWSAPI_KEY, NEWSAPI_DAILY_LIMIT
from config.newsapi_config import (
    NEWSAPI_CATEGORIES,
    NEWSAPI_KEYWORDS,
    NEWSAPI_PAGE_SIZE,
    NEWSAPI_BASE_URL,
    NEWSAPI_SOURCE_QUALITY,
)
from utils.logger import get_logger
from utils.timezone_utils import now_utc_iso

logger = get_logger(__name__)

# Request timeout
REQUEST_TIMEOUT = 15


class NewsAPICollector:
    """Fetches from NewsAPI with daily rate limiting.

    Tracks requests in-memory and via database to stay within 100/day.
    """

    def __init__(self, db=None):
        """Initialize the NewsAPI collector.

        Args:
            db: NewsDatabase instance for tracking request counts.
        """
        self.api_key = NEWSAPI_KEY
        self.db = db
        self.session = requests.Session()
        self.session.headers.update({
            "X-Api-Key": self.api_key,
            "User-Agent": "NewsIntelligenceAgent/1.0",
        })

        # In-memory tracking (also persisted in DB)
        self._requests_today = 0
        self._last_reset_date = datetime.now(timezone.utc).date()
        self._last_category_run: Optional[datetime] = None
        self._last_keyword_run: Optional[datetime] = None

    def _is_configured(self) -> bool:
        """Check if NewsAPI key is set."""
        if not self.api_key:
            logger.debug("NewsAPI key not configured — skipping")
            return False
        return True

    def _check_budget(self, needed: int = 1) -> bool:
        """Check if we have enough daily budget remaining.

        Args:
            needed: Number of requests we want to make.

        Returns:
            True if budget allows.
        """
        self._reset_if_new_day()

        # Also check persisted count from DB
        if self.db:
            db_count = self.db.get_newsapi_requests_today()
            self._requests_today = max(self._requests_today, db_count)

        remaining = NEWSAPI_DAILY_LIMIT - self._requests_today
        if remaining < needed:
            logger.warning(
                f"NewsAPI budget exhausted: {self._requests_today}/{NEWSAPI_DAILY_LIMIT} "
                f"used today. Need {needed}, have {remaining}."
            )
            return False
        return True

    def _reset_if_new_day(self):
        """Reset daily counter if it's a new day."""
        today = datetime.now(timezone.utc).date()
        if today != self._last_reset_date:
            logger.info("NewsAPI daily budget reset (new day)")
            self._requests_today = 0
            self._last_reset_date = today

    def _record_requests(self, count: int):
        """Record that N requests were used."""
        self._requests_today += count
        if self.db:
            self.db.update_newsapi_counter(count)
        logger.debug(
            f"NewsAPI: {self._requests_today}/{NEWSAPI_DAILY_LIMIT} requests used today"
        )

    # =============================================================
    # Scheduled Collection
    # =============================================================

    def fetch_categories(self) -> tuple[List[Dict], int]:
        """Fetch top headlines for all configured categories.

        Returns:
            Tuple of (raw_items, requests_used).
        """
        if not self._is_configured():
            return [], 0

        needed = len(NEWSAPI_CATEGORIES)
        if not self._check_budget(needed):
            return [], 0

        all_items = []
        requests_used = 0

        for category in NEWSAPI_CATEGORIES:
            try:
                items = self._fetch_top_headlines(category=category)
                all_items.extend(items)
                requests_used += 1
                logger.debug(f"  NewsAPI [{category}]: {len(items)} articles")
            except Exception as e:
                logger.warning(f"  NewsAPI [{category}] failed: {e}")
                requests_used += 1  # Still counts toward limit

        self._record_requests(requests_used)
        self._last_category_run = datetime.now(timezone.utc)
        logger.info(f"NewsAPI categories: {len(all_items)} articles ({requests_used} requests)")

        return all_items, requests_used

    def fetch_keywords(self) -> tuple[List[Dict], int]:
        """Fetch articles for all configured keyword searches.

        Returns:
            Tuple of (raw_items, requests_used).
        """
        if not self._is_configured():
            return [], 0

        needed = len(NEWSAPI_KEYWORDS)
        if not self._check_budget(needed):
            return [], 0

        all_items = []
        requests_used = 0

        for keyword in NEWSAPI_KEYWORDS:
            try:
                items = self._fetch_everything(query=keyword)
                all_items.extend(items)
                requests_used += 1
                logger.debug(f"  NewsAPI ['{keyword}']: {len(items)} articles")
            except Exception as e:
                logger.warning(f"  NewsAPI ['{keyword}'] failed: {e}")
                requests_used += 1

        self._record_requests(requests_used)
        self._last_keyword_run = datetime.now(timezone.utc)
        logger.info(f"NewsAPI keywords: {len(all_items)} articles ({requests_used} requests)")

        return all_items, requests_used

    # =============================================================
    # On-Demand (for user queries like /top5 ai)
    # =============================================================

    def fetch_on_demand(self, keyword: str) -> List[Dict]:
        """Fetch articles for a specific keyword on demand.

        Uses 1 request from the reserved budget.

        Args:
            keyword: Search term from user query.

        Returns:
            List of raw article dicts.
        """
        if not self._is_configured() or not self._check_budget(1):
            return []

        try:
            items = self._fetch_everything(query=keyword, page_size=10)
            self._record_requests(1)
            logger.info(f"NewsAPI on-demand ['{keyword}']: {len(items)} articles")
            return items
        except Exception as e:
            logger.warning(f"NewsAPI on-demand ['{keyword}'] failed: {e}")
            self._record_requests(1)
            return []

    # =============================================================
    # Core API Calls
    # =============================================================

    def _fetch_top_headlines(
        self, category: str = None, country: str = "us"
    ) -> List[Dict]:
        """Call NewsAPI /v2/top-headlines.

        Args:
            category: NewsAPI category (general, business, technology, etc.)
            country: Country code (default: us).

        Returns:
            List of raw article dicts with source metadata.
        """
        params = {
            "country": country,
            "pageSize": NEWSAPI_PAGE_SIZE,
        }
        if category:
            params["category"] = category

        response = self.session.get(
            f"{NEWSAPI_BASE_URL}/top-headlines",
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        data = response.json()
        if data.get("status") != "ok":
            raise Exception(f"NewsAPI error: {data.get('message', 'Unknown')}")

        collected_at = now_utc_iso()
        return [
            self._parse_newsapi_article(article, category, collected_at)
            for article in data.get("articles", [])
            if article.get("title") and article["title"] != "[Removed]"
        ]

    def _fetch_everything(
        self, query: str, page_size: int = None
    ) -> List[Dict]:
        """Call NewsAPI /v2/everything.

        Args:
            query: Search query string.
            page_size: Override default page size.

        Returns:
            List of raw article dicts with source metadata.
        """
        params = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": page_size or NEWSAPI_PAGE_SIZE,
        }

        response = self.session.get(
            f"{NEWSAPI_BASE_URL}/everything",
            params=params,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        data = response.json()
        if data.get("status") != "ok":
            raise Exception(f"NewsAPI error: {data.get('message', 'Unknown')}")

        collected_at = now_utc_iso()
        return [
            self._parse_newsapi_article(article, None, collected_at)
            for article in data.get("articles", [])
            if article.get("title") and article["title"] != "[Removed]"
        ]

    def _parse_newsapi_article(
        self, article: Dict, category: Optional[str], collected_at: str
    ) -> Dict:
        """Convert a NewsAPI article to raw article dict.

        Args:
            article: NewsAPI article object.
            category: Category it was fetched from (may be None for keyword searches).
            collected_at: Collection timestamp.

        Returns:
            Raw article dict with source metadata.
        """
        # Determine source quality from known sources
        source_id = ""
        source_name = "Unknown"
        if article.get("source"):
            source_id = article["source"].get("id", "") or ""
            source_name = article["source"].get("name", "Unknown")

        quality = NEWSAPI_SOURCE_QUALITY.get(
            source_id, NEWSAPI_SOURCE_QUALITY["default"]
        )

        # Map NewsAPI category to our category system
        category_map = {
            "general": "GENERAL",
            "business": "BUSINESS",
            "technology": "TECHNOLOGY",
            "science": "SCIENCE",
            "health": "HEALTH",
            "sports": "SPORTS",
            "entertainment": "ENTERTAINMENT",
        }
        mapped_category = category_map.get(category, "GENERAL") if category else "GENERAL"

        return {
            "title": article.get("title", "").strip(),
            "url": article.get("url", ""),
            "description": article.get("description", "") or "",
            "content": article.get("content", "") or "",
            "published_at_raw": article.get("publishedAt", ""),
            "author": article.get("author"),
            "image_url": article.get("urlToImage"),
            "collected_at": collected_at,
            "source_name": source_name,
            "source_quality": quality,
            "source_category": mapped_category,
            "source_type": "newsapi",
        }

    # =============================================================
    # Status
    # =============================================================

    def get_budget_info(self) -> Dict:
        """Get current budget status.

        Returns:
            Dict with requests_used, remaining, limit.
        """
        self._reset_if_new_day()
        return {
            "requests_used_today": self._requests_today,
            "remaining": NEWSAPI_DAILY_LIMIT - self._requests_today,
            "daily_limit": NEWSAPI_DAILY_LIMIT,
            "last_category_run": (
                self._last_category_run.isoformat() if self._last_category_run else None
            ),
            "last_keyword_run": (
                self._last_keyword_run.isoformat() if self._last_keyword_run else None
            ),
        }
