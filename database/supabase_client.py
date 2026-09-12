"""
Supabase database client for the News Intelligence Agent.

Handles all database operations: insert, query, update, cleanup.
Uses Supabase Python client for PostgreSQL access.
"""

import json
from typing import List, Optional, Dict
from datetime import datetime, timezone, timedelta

from supabase import create_client, Client

from config.settings import SUPABASE_URL, SUPABASE_KEY, MAX_AGE_HOURS, MAX_ARTICLES
from database.models import Article
from utils.logger import get_logger
from utils.timezone_utils import now_utc, now_utc_iso, hours_ago

logger = get_logger(__name__)


class NewsDatabase:
    """All database operations for the news agent."""

    def __init__(self):
        """Initialize Supabase client."""
        if not SUPABASE_URL or not SUPABASE_KEY:
            logger.warning("Supabase credentials not configured. Database operations will fail.")
            self.client = None
            return

        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Connected to Supabase database")

    def _ensure_client(self) -> bool:
        """Check if database client is available."""
        if self.client is None:
            logger.error("Database client not initialized. Check SUPABASE_URL and SUPABASE_KEY.")
            return False
        return True

    # =============================================================
    # Article Operations
    # =============================================================

    def upsert_articles(self, articles: List[Article]) -> int:
        """Insert articles into database, skip duplicates by URL.

        Args:
            articles: List of normalized Article objects.

        Returns:
            Number of articles successfully inserted.
        """
        if not self._ensure_client() or not articles:
            return 0

        inserted = 0
        for article in articles:
            try:
                data = article.to_dict()
                # Upsert: insert if URL doesn't exist, skip if it does
                self.client.table("articles").upsert(
                    data,
                    on_conflict="url",
                ).execute()
                inserted += 1
            except Exception as e:
                # Log but don't crash — one bad article shouldn't stop everything
                logger.debug(f"Skipped article (likely duplicate): {article.url[:80]} — {e}")

        logger.info(f"Inserted {inserted}/{len(articles)} articles into database")
        return inserted

    def get_unprocessed(self, limit: int = 100) -> List[Dict]:
        """Get articles that haven't been scored yet.

        Args:
            limit: Maximum number of articles to return.

        Returns:
            List of article dictionaries.
        """
        if not self._ensure_client():
            return []

        try:
            response = (
                self.client.table("articles")
                .select("*")
                .eq("is_processed", False)
                .order("collected_at", desc=True)
                .limit(limit)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to get unprocessed articles: {e}")
            return []

    def update_article_scores(self, url: str, scores: Dict) -> bool:
        """Update scores for an article by URL.

        Args:
            url: Article URL (unique identifier).
            scores: Dict with importance_score, urgency_score, recency_score,
                    credibility_score, final_score, is_breaking, is_processed,
                    story_group_id.

        Returns:
            True if update succeeded.
        """
        if not self._ensure_client():
            return False

        try:
            self.client.table("articles").update(scores).eq("url", url).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to update scores for {url[:80]}: {e}")
            return False

    def batch_update_scores(self, updates: List[Dict]) -> int:
        """Update scores for multiple articles.

        Args:
            updates: List of dicts, each with 'url' and score fields.

        Returns:
            Number of successful updates.
        """
        if not self._ensure_client():
            return 0

        success = 0
        for update in updates:
            url = update.get("url")
            if url:
                scores = {k: v for k, v in update.items() if k != "url"}
                if self.update_article_scores(url, scores):
                    success += 1

        logger.info(f"Updated scores for {success}/{len(updates)} articles")
        return success

    def get_top_articles(
        self,
        category: Optional[str] = None,
        time_hours: int = 24,
        limit: int = 30,
        breaking_only: bool = False,
    ) -> List[Dict]:
        """Query top articles by final_score.

        Args:
            category: Optional category filter (e.g., 'AI', 'WORLD').
            time_hours: Only include articles from last N hours.
            limit: Maximum articles to return.
            breaking_only: If True, only return breaking news.

        Returns:
            List of article dicts, ordered by final_score DESC.
        """
        if not self._ensure_client():
            return []

        try:
            cutoff = hours_ago(time_hours).isoformat()

            query = (
                self.client.table("articles")
                .select("*")
                .eq("is_processed", True)
                .gte("collected_at", cutoff)
                .order("final_score", desc=True)
                .limit(limit)
            )

            if category:
                query = query.eq("category", category.upper())

            if breaking_only:
                query = query.eq("is_breaking", True)

            response = query.execute()
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to query top articles: {e}")
            return []

    def get_latest_articles(self, limit: int = 5) -> List[Dict]:
        """Get the most recently collected articles.

        Args:
            limit: Number of articles to return.

        Returns:
            List of article dicts, ordered by collected_at DESC.
        """
        if not self._ensure_client():
            return []

        try:
            response = (
                self.client.table("articles")
                .select("*")
                .order("collected_at", desc=True)
                .limit(limit)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to get latest articles: {e}")
            return []

    def search_articles(self, query_text: str, limit: int = 20) -> List[Dict]:
        """Full-text search on article titles and descriptions.

        Args:
            query_text: Search terms.
            limit: Maximum results.

        Returns:
            List of matching article dicts.
        """
        if not self._ensure_client():
            return []

        try:
            # Use PostgreSQL full-text search via Supabase RPC
            # Fallback to ILIKE if FTS isn't set up
            search_term = f"%{query_text}%"
            response = (
                self.client.table("articles")
                .select("*")
                .or_(f"title.ilike.{search_term},description.ilike.{search_term}")
                .order("final_score", desc=True)
                .limit(limit)
                .execute()
            )
            return response.data or []
        except Exception as e:
            logger.error(f"Failed to search articles: {e}")
            return []

    def article_exists(self, url: str) -> bool:
        """Check if an article URL already exists in the database.

        Args:
            url: Article URL to check.

        Returns:
            True if article exists.
        """
        if not self._ensure_client():
            return False

        try:
            response = (
                self.client.table("articles")
                .select("url")
                .eq("url", url)
                .limit(1)
                .execute()
            )
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Failed to check article existence: {e}")
            return False

    def get_article_count(self) -> int:
        """Get total number of articles in database."""
        if not self._ensure_client():
            return 0

        try:
            response = (
                self.client.table("articles")
                .select("id", count="exact")
                .execute()
            )
            return response.count or 0
        except Exception as e:
            logger.error(f"Failed to get article count: {e}")
            return 0

    # =============================================================
    # Cleanup
    # =============================================================

    def cleanup_old_articles(self, max_age_hours: int = None) -> int:
        """Delete articles older than max_age_hours.

        Also caps total articles at MAX_ARTICLES.

        Args:
            max_age_hours: Override default max age.

        Returns:
            Number of articles deleted.
        """
        if not self._ensure_client():
            return 0

        age = max_age_hours or MAX_AGE_HOURS
        cutoff = hours_ago(age).isoformat()
        deleted = 0

        try:
            # Delete old articles
            response = (
                self.client.table("articles")
                .delete()
                .lt("collected_at", cutoff)
                .execute()
            )
            deleted = len(response.data) if response.data else 0

            # If still over limit, delete lowest-scored articles
            total = self.get_article_count()
            if total > MAX_ARTICLES:
                excess = total - MAX_ARTICLES
                # Get the lowest-scored articles
                lowest = (
                    self.client.table("articles")
                    .select("id")
                    .order("final_score", desc=False)
                    .limit(excess)
                    .execute()
                )
                if lowest.data:
                    ids = [row["id"] for row in lowest.data]
                    for article_id in ids:
                        self.client.table("articles").delete().eq("id", article_id).execute()
                    deleted += len(ids)

            if deleted > 0:
                logger.info(f"Cleaned up {deleted} old/excess articles")
            return deleted
        except Exception as e:
            logger.error(f"Failed to cleanup articles: {e}")
            return 0

    # =============================================================
    # System Status
    # =============================================================

    def update_status(
        self,
        articles_collected: int,
        sources_checked: int,
        sources_failed: List[str] = None,
    ):
        """Update the system_status table after a collection run.

        Args:
            articles_collected: Number of articles collected this run.
            sources_checked: Number of sources attempted.
            sources_failed: List of source names that failed.
        """
        if not self._ensure_client():
            return

        total = self.get_article_count()
        failed = sources_failed or []

        if failed:
            status = "degraded"
        else:
            status = "healthy"

        try:
            self.client.table("system_status").upsert(
                {
                    "id": 1,
                    "last_collection": now_utc_iso(),
                    "articles_collected": articles_collected,
                    "total_articles": total,
                    "sources_checked": sources_checked,
                    "sources_failed": failed,
                    "status": status,
                    "updated_at": now_utc_iso(),
                }
            ).execute()
        except Exception as e:
            logger.error(f"Failed to update system status: {e}")

    def get_status(self) -> Dict:
        """Get current system status.

        Returns:
            Dict with last_collection, total_articles, status, etc.
        """
        if not self._ensure_client():
            return {
                "status": "offline",
                "message": "Database not connected",
                "total_articles": 0,
            }

        try:
            response = (
                self.client.table("system_status")
                .select("*")
                .eq("id", 1)
                .limit(1)
                .execute()
            )
            if response.data:
                return response.data[0]
            return {"status": "initializing", "total_articles": 0}
        except Exception as e:
            logger.error(f"Failed to get system status: {e}")
            return {"status": "error", "message": str(e)}

    def update_newsapi_counter(self, requests_used: int):
        """Increment the NewsAPI daily request counter.

        Resets automatically on new day.

        Args:
            requests_used: Number of requests made.
        """
        if not self._ensure_client():
            return

        try:
            status = self.get_status()
            today = datetime.now(timezone.utc).date().isoformat()
            last_reset = status.get("newsapi_last_reset", "")

            if last_reset != today:
                # New day — reset counter
                current = requests_used
                self.client.table("system_status").update(
                    {
                        "newsapi_requests_today": current,
                        "newsapi_last_reset": today,
                    }
                ).eq("id", 1).execute()
            else:
                current = status.get("newsapi_requests_today", 0) + requests_used
                self.client.table("system_status").update(
                    {"newsapi_requests_today": current}
                ).eq("id", 1).execute()
        except Exception as e:
            logger.error(f"Failed to update NewsAPI counter: {e}")

    def get_newsapi_requests_today(self) -> int:
        """Get number of NewsAPI requests used today."""
        status = self.get_status()
        today = datetime.now(timezone.utc).date().isoformat()

        if status.get("newsapi_last_reset", "") != today:
            return 0
        return status.get("newsapi_requests_today", 0)

    # =============================================================
    # Alert Log
    # =============================================================

    def log_alert(self, story_group_id: str, title: str):
        """Log that a breaking news alert was sent.

        Args:
            story_group_id: The story group that was alerted.
            title: Article title for reference.
        """
        if not self._ensure_client():
            return

        try:
            self.client.table("alert_log").insert(
                {
                    "story_group_id": story_group_id,
                    "article_title": title,
                }
            ).execute()
        except Exception as e:
            logger.error(f"Failed to log alert: {e}")

    def was_alert_sent(self, story_group_id: str, cooldown_hours: int = 2) -> bool:
        """Check if an alert was already sent for this story group.

        Args:
            story_group_id: The story group to check.
            cooldown_hours: Hours within which a re-alert is suppressed.

        Returns:
            True if alert was already sent within cooldown period.
        """
        if not self._ensure_client():
            return True  # Err on side of not alerting if DB is down

        try:
            cutoff = hours_ago(cooldown_hours).isoformat()
            response = (
                self.client.table("alert_log")
                .select("id")
                .eq("story_group_id", story_group_id)
                .gte("alerted_at", cutoff)
                .limit(1)
                .execute()
            )
            return len(response.data) > 0
        except Exception as e:
            logger.error(f"Failed to check alert log: {e}")
            return True  # Err on side of not alerting
