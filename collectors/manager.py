"""
Collector manager for the News Intelligence Agent.

Orchestrates all collectors (RSS + NewsAPI), runs the full
collection → normalize → deduplicate → score → store pipeline.
"""

from typing import List, Dict
from datetime import datetime, timezone

from collectors.rss_collector import RSSCollector
from collectors.newsapi_collector import NewsAPICollector
from processors.normalizer import ArticleNormalizer
from processors.deduplicator import Deduplicator
from processors.scorer import ArticleScorer
from processors.story_grouper import StoryGrouper
from processors.authenticity_checker import AuthenticityChecker
from database.supabase_client import NewsDatabase
from database.models import Article
from utils.logger import get_logger
from utils.timezone_utils import now_utc

logger = get_logger(__name__)


class CollectorManager:
    """Orchestrates the full news collection pipeline.

    Pipeline:
    1. Fetch from all sources (RSS + NewsAPI)
    2. Normalize to common Article schema
    3. Filter (English, age, quality)
    4. Deduplicate (URL + title)
    5. Score (importance, urgency, recency, final)
    6. Group related stories
    7. Store in database
    8. Update system status
    """

    def __init__(
        self,
        db: NewsDatabase,
        rss_collector: RSSCollector = None,
        newsapi_collector: NewsAPICollector = None,
        normalizer: ArticleNormalizer = None,
        deduplicator: Deduplicator = None,
        scorer: ArticleScorer = None,
        story_grouper: StoryGrouper = None,
    ):
        self.db = db
        self.rss = rss_collector or RSSCollector()
        self.newsapi = newsapi_collector or NewsAPICollector(db=db)
        self.normalizer = normalizer or ArticleNormalizer()
        self.deduplicator = deduplicator or Deduplicator()
        self.scorer = scorer or ArticleScorer()
        self.grouper = story_grouper or StoryGrouper()
        self.authenticity = AuthenticityChecker()

        # Track NewsAPI scheduling
        self._last_newsapi_category_run: datetime = None
        self._last_newsapi_keyword_run: datetime = None

    def collect(self) -> Dict:
        """Run the full collection pipeline.

        This is the main method called by the scheduler every 30 minutes.

        Returns:
            Dict with collection results (counts, failures, etc.)
        """
        logger.info("=" * 60)
        logger.info("STARTING NEWS COLLECTION")
        logger.info("=" * 60)

        results = {
            "raw_count": 0,
            "normalized_count": 0,
            "after_filter": 0,
            "after_dedup": 0,
            "stored_count": 0,
            "sources_checked": 0,
            "sources_failed": [],
            "breaking_articles": [],
        }

        # ─── Step 1: Fetch from all sources ────────────────────
        raw_items = []

        # RSS feeds (always run — free & unlimited)
        rss_items, rss_failed = self.rss.fetch_all()
        raw_items.extend(rss_items)
        results["sources_checked"] += len(self.rss.sources)
        results["sources_failed"].extend(rss_failed)

        # NewsAPI (run on schedule — limited budget)
        newsapi_items = self._run_newsapi_if_due()
        raw_items.extend(newsapi_items)

        results["raw_count"] = len(raw_items)
        logger.info(f"Step 1 — Raw articles collected: {results['raw_count']}")

        if not raw_items:
            logger.warning("No articles collected from any source!")
            self.db.update_status(0, results["sources_checked"], results["sources_failed"])
            return results

        # ─── Step 2: Normalize ─────────────────────────────────
        articles = self.normalizer.normalize_all(raw_items)
        results["normalized_count"] = len(articles)
        logger.info(f"Step 2 — Normalized: {results['normalized_count']}")

        # ─── Step 3: Filter ───────────────────────────────────
        articles = self.normalizer.filter_articles(articles)
        results["after_filter"] = len(articles)
        logger.info(f"Step 3 — After filtering: {results['after_filter']}")

        # ─── Step 4: Deduplicate ──────────────────────────────
        articles = self.deduplicator.deduplicate_urls(articles)
        articles = self.deduplicator.deduplicate_titles(articles)
        results["after_dedup"] = len(articles)
        logger.info(f"Step 4 — After deduplication: {results['after_dedup']}")

        # ─── Step 5: Score ────────────────────────────────────
        articles = self.scorer.score_all(articles)
        logger.info(f"Step 5 — Scored {len(articles)} articles")

        # ─── Step 6: Group related stories ────────────────────
        articles = self.grouper.group(articles)
        logger.info(f"Step 6 — Story grouping complete")

        # ─── Step 7: Authenticity verification ────────────────
        articles = self.authenticity.check_all(articles)
        logger.info(f"Step 7 -- Authenticity check complete")

        # ─── Step 8: Detect breaking news ─────────────────────
        breaking = [a for a in articles if a.is_breaking]
        results["breaking_articles"] = breaking
        if breaking:
            logger.info(f"Step 8 -- {len(breaking)} BREAKING article(s) detected!")

        # ─── Step 9: Store in database ────────────────────────
        stored = self.db.upsert_articles(articles)
        results["stored_count"] = stored
        logger.info(f"Step 9 -- Stored {stored} articles in database")

        # ─── Step 9: Cleanup old articles ─────────────────────
        cleaned = self.db.cleanup_old_articles()
        if cleaned > 0:
            logger.info(f"Step 8 — Cleaned up {cleaned} old articles")

        # ─── Step 10: Update system status ────────────────────
        self.db.update_status(
            articles_collected=stored,
            sources_checked=results["sources_checked"],
            sources_failed=results["sources_failed"],
        )

        logger.info("=" * 60)
        logger.info(
            f"COLLECTION COMPLETE: {results['raw_count']} raw → "
            f"{results['after_dedup']} unique → {results['stored_count']} stored"
        )
        logger.info("=" * 60)

        return results

    def _run_newsapi_if_due(self) -> List[Dict]:
        """Run NewsAPI collection if enough time has passed.

        Category calls: every 6 hours
        Keyword calls: every 8 hours

        Returns:
            List of raw article dicts from NewsAPI.
        """
        now = now_utc()
        items = []

        # Category calls (every 6 hours)
        should_run_categories = (
            self._last_newsapi_category_run is None
            or (now - self._last_newsapi_category_run).total_seconds() >= 6 * 3600
        )

        if should_run_categories:
            cat_items, _ = self.newsapi.fetch_categories()
            items.extend(cat_items)
            self._last_newsapi_category_run = now

        # Keyword calls (every 8 hours)
        should_run_keywords = (
            self._last_newsapi_keyword_run is None
            or (now - self._last_newsapi_keyword_run).total_seconds() >= 8 * 3600
        )

        if should_run_keywords:
            kw_items, _ = self.newsapi.fetch_keywords()
            items.extend(kw_items)
            self._last_newsapi_keyword_run = now

        return items
