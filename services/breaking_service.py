"""
Breaking news service for the News Intelligence Agent.

Detects breaking news from scored articles and manages
alert cooldowns to prevent spam.
"""

from typing import List, Dict, Optional

from database.supabase_client import NewsDatabase
from database.models import Article
from config.settings import BREAKING_COOLDOWN_HOURS
from utils.logger import get_logger

logger = get_logger(__name__)


class BreakingService:
    """Detects breaking news and manages alert cooldowns."""

    def __init__(self, db: NewsDatabase):
        self.db = db

    def detect(self, articles: List[Article]) -> List[Article]:
        """Find breaking news articles that haven't been alerted yet.

        Args:
            articles: List of scored Article objects.

        Returns:
            List of breaking articles that need alerts sent.
        """
        breaking = [a for a in articles if a.is_breaking]

        if not breaking:
            return []

        # Filter out stories that were already alerted
        new_breaking = []
        for article in breaking:
            group_id = article.story_group_id or article.url

            if not self.db.was_alert_sent(group_id, BREAKING_COOLDOWN_HOURS):
                new_breaking.append(article)
                logger.info(f"🚨 New breaking story: {article.title[:80]}")
            else:
                logger.debug(f"Breaking story already alerted: {article.title[:60]}")

        return new_breaking

    def mark_alerted(self, article: Article):
        """Mark a breaking story as alerted (prevents re-alerting).

        Args:
            article: The article that was alerted.
        """
        group_id = article.story_group_id or article.url
        self.db.log_alert(group_id, article.title)
        logger.info(f"Logged alert for story group: {group_id}")
