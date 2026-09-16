"""
Collector manager for the News Intelligence Agent.

Orchestrates all collectors (RSS + NewsAPI), runs the full
collection → normalize → deduplicate → score → store pipeline.
Emits real-time progress events via the ProgressTracker.
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
from services.progress_tracker import get_tracker
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
        """Run the full collection pipeline with real-time progress tracking.

        This is the main method called by the scheduler every 30 minutes.

        Returns:
            Dict with collection results (counts, failures, etc.)
        """
        tracker = get_tracker()
        tracker.start("news")

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

        try:
            # ─── Step 1: Fetch RSS feeds ───────────────────────────
            total_rss = len(self.rss.sources)
            tracker.update_stage("rss_fetch", f"Fetching {total_rss} RSS feeds...", current=0, total=total_rss)

            raw_items = []
            rss_items, rss_failed = self.rss.fetch_all()
            raw_items.extend(rss_items)
            results["sources_checked"] += total_rss
            results["sources_failed"].extend(rss_failed)
            tracker.update_stage("rss_fetch", f"RSS complete: {len(rss_items)} articles from {total_rss - len(rss_failed)} sources", current=total_rss, total=total_rss)
            tracker.stage_complete("rss_fetch")

            # ─── Step 2: Fetch from NewsAPI ────────────────────────
            tracker.update_stage("newsapi_fetch", "Checking NewsAPI schedule...", current=0, total=1)
            newsapi_items = self._run_newsapi_if_due()
            raw_items.extend(newsapi_items)
            tracker.update_stage("newsapi_fetch", f"NewsAPI: {len(newsapi_items)} articles", current=1, total=1)
            tracker.stage_complete("newsapi_fetch")

            results["raw_count"] = len(raw_items)
            logger.info(f"Step 1 — Raw articles collected: {results['raw_count']}")

            if not raw_items:
                logger.warning("No articles collected from any source!")
                self.db.update_status(0, results["sources_checked"], results["sources_failed"])
                tracker.complete(results)
                return results

            # ─── Step 3: Normalize ─────────────────────────────────
            tracker.update_stage("normalize", f"Normalizing {len(raw_items)} articles...", current=0, total=len(raw_items))
            articles = self.normalizer.normalize_all(raw_items)
            results["normalized_count"] = len(articles)
            tracker.update_stage("normalize", f"Normalized: {len(articles)} articles", current=len(articles), total=len(raw_items))
            tracker.stage_complete("normalize")
            logger.info(f"Step 2 — Normalized: {results['normalized_count']}")

            # ─── Step 4: Filter ───────────────────────────────────
            tracker.update_stage("filter", f"Filtering {len(articles)} articles...", current=0, total=len(articles))
            articles = self.normalizer.filter_articles(articles)
            results["after_filter"] = len(articles)
            tracker.update_stage("filter", f"After filtering: {len(articles)} articles", current=len(articles), total=len(articles))
            tracker.stage_complete("filter")
            logger.info(f"Step 3 — After filtering: {results['after_filter']}")

            # ─── Step 5: Deduplicate ──────────────────────────────
            before_dedup = len(articles)
            tracker.update_stage("deduplicate", f"Deduplicating {before_dedup} articles...", current=0, total=before_dedup)
            articles = self.deduplicator.deduplicate_urls(articles)
            tracker.update_stage("deduplicate", f"URL dedup done, checking titles...", current=len(articles), total=before_dedup)
            articles = self.deduplicator.deduplicate_titles(articles)
            results["after_dedup"] = len(articles)
            removed = before_dedup - len(articles)
            tracker.update_stage("deduplicate", f"Removed {removed} duplicates → {len(articles)} unique", current=len(articles), total=before_dedup)
            tracker.stage_complete("deduplicate")
            logger.info(f"Step 4 — After deduplication: {results['after_dedup']}")

            # ─── Step 6: Score ────────────────────────────────────
            tracker.update_stage("score", f"Scoring {len(articles)} articles...", current=0, total=len(articles))
            articles = self.scorer.score_all(articles)
            tracker.update_stage("score", f"Scored {len(articles)} articles", current=len(articles), total=len(articles))
            tracker.stage_complete("score")
            logger.info(f"Step 5 — Scored {len(articles)} articles")

            # ─── Step 7: Group related stories ────────────────────
            tracker.update_stage("group", f"Grouping {len(articles)} articles into stories...", current=0, total=len(articles))
            articles = self.grouper.group(articles)
            tracker.update_stage("group", "Story grouping complete", current=len(articles), total=len(articles))
            tracker.stage_complete("group")
            logger.info(f"Step 6 — Story grouping complete")

            # ─── Step 8: Authenticity verification ────────────────
            tracker.update_stage("authenticity", f"Checking authenticity of {len(articles)} articles...", current=0, total=len(articles))
            articles = self.authenticity.check_all(articles)
            tracker.update_stage("authenticity", "Authenticity check complete", current=len(articles), total=len(articles))
            tracker.stage_complete("authenticity")
            logger.info(f"Step 7 -- Authenticity check complete")

            # ─── Detect breaking news ─────────────────────────────
            breaking = [a for a in articles if a.is_breaking]
            results["breaking_articles"] = breaking
            if breaking:
                logger.info(f"Step 8 -- {len(breaking)} BREAKING article(s) detected!")

            # ─── Step 9: Store in database ────────────────────────
            tracker.update_stage("store", f"Storing {len(articles)} articles in database...", current=0, total=len(articles))
            stored = self.db.upsert_articles(articles)
            results["stored_count"] = stored
            tracker.update_stage("store", f"Stored {stored} articles", current=stored, total=len(articles))
            tracker.stage_complete("store")
            logger.info(f"Step 9 -- Stored {stored} articles in database")

            # ─── Step 10: Cleanup & finalize ──────────────────────
            tracker.update_stage("cleanup", "Cleaning up old articles...", current=0, total=1)
            cleaned = self.db.cleanup_old_articles()
            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} old articles")

            self.db.update_status(
                articles_collected=stored,
                sources_checked=results["sources_checked"],
                sources_failed=results["sources_failed"],
            )
            tracker.update_stage("cleanup", "Finalization complete", current=1, total=1)
            tracker.stage_complete("cleanup")

            logger.info("=" * 60)
            logger.info(
                f"COLLECTION COMPLETE: {results['raw_count']} raw → "
                f"{results['after_dedup']} unique → {results['stored_count']} stored"
            )
            logger.info("=" * 60)

            tracker.complete(results)

        except Exception as e:
            logger.error(f"Collection pipeline error: {e}")
            tracker.error(str(e))
            raise

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
