"""
Top 5 service for the News Intelligence Agent.

The core user-facing service. Handles:
- Parsing user queries (natural language → structured query)
- Querying the database
- Deduplicating by story group
- Formatting via Gemini (with fallback)
- Caching results
"""

import re
from typing import Dict, Optional, List
from dataclasses import dataclass

from database.supabase_client import NewsDatabase
from processors.story_grouper import StoryGrouper
from ai.gemini_client import GeminiClient
from services.cache_service import CacheService
from config.settings import CATEGORY_ALIASES
from utils.logger import get_logger
from utils.timezone_utils import now_local_formatted

logger = get_logger(__name__)


@dataclass
class ParsedQuery:
    """Structured representation of a user's news query."""
    category: Optional[str] = None
    time_hours: int = 168
    limit: int = 20
    breaking_only: bool = False
    latest_only: bool = False
    status_request: bool = False
    help_request: bool = False
    search_term: Optional[str] = None
    raw_text: str = ""


class Top5Service:
    """The core service for querying and presenting top news.

    Used by both Telegram bot and FastAPI endpoints.
    """

    def __init__(
        self,
        db: NewsDatabase,
        gemini: GeminiClient,
        cache: CacheService,
        story_grouper: StoryGrouper = None,
    ):
        self.db = db
        self.gemini = gemini
        self.cache = cache
        self.grouper = story_grouper or StoryGrouper()

    def get_top5(
        self,
        category: str = None,
        time_hours: int = 168,
        limit: int = 20,
    ) -> str:
        """Get the top N most important news stories.

        Pipeline:
        1. Check cache
        2. Query database (top 30 by final_score)
        3. Deduplicate by story group (keep best per event)
        4. Take top N
        5. Format via Gemini (or fallback)
        6. Cache result

        Args:
            category: Optional category filter.
            time_hours: Time range in hours.
            limit: Number of stories to return.

        Returns:
            Formatted text string ready for display.
        """
        # Check cache
        cache_key = self.cache.make_key(category, time_hours)
        cached = self.cache.get(cache_key)
        if cached:
            logger.info("Serving Top 5 from cache")
            return cached

        # Query database
        articles = self.db.get_top_articles(
            category=category,
            time_hours=time_hours,
            limit=60,  # Get 60, then deduplicate down to 20
        )

        if not articles:
            return self._no_results_message(category, time_hours)

        # Deduplicate by story group (1 article per event)
        unique_stories = self.grouper.get_primary_per_group(articles)

        # Take top N
        top_stories = unique_stories[:limit]

        logger.info(
            f"Top 20 query: {len(articles)} DB results -> "
            f"{len(unique_stories)} unique stories -> "
            f"{len(top_stories)} returned"
        )

        # Format via Gemini (with fallback)
        formatted = self.gemini.format_top5(top_stories)

        # Cache result
        self.cache.set(cache_key, formatted)

        return formatted

    def get_breaking(self) -> str:
        """Get current breaking news.

        Returns:
            Formatted breaking news, or a 'no breaking news' message.
        """
        articles = self.db.get_top_articles(
            time_hours=6,
            limit=5,
            breaking_only=True,
        )

        if not articles:
            return "📭 No breaking news at the moment.\n\nUse /top5 to see the most important stories."

        # Deduplicate
        unique = self.grouper.get_primary_per_group(articles)

        return self.gemini.format_top5(unique[:3])  # Max 3 breaking stories

    def get_latest(self, limit: int = 10) -> str:
        """Get the most recently collected articles.

        Args:
            limit: Number of articles.

        Returns:
            Formatted list of latest articles.
        """
        articles = self.db.get_latest_articles(limit=limit)

        if not articles:
            return "📭 No articles in database yet. The collector may not have run."

        return self.gemini.format_top5(articles)

    def get_status(self) -> str:
        """Get system health status.

        Returns:
            Formatted status string.
        """
        status = self.db.get_status()

        if status.get("status") == "offline":
            return "🔴 **System Offline**\nDatabase not connected."

        # Determine health emoji
        health = status.get("status", "unknown")
        health_emoji = {
            "healthy": "🟢",
            "degraded": "🟡",
            "error": "🔴",
            "initializing": "🔵",
        }.get(health, "⚪")

        # Calculate time since last collection
        from utils.timezone_utils import format_relative_time, utc_to_local_str
        from datetime import datetime, timezone

        last_collection = status.get("last_collection", "")
        time_ago = "never"
        if last_collection:
            try:
                dt = datetime.fromisoformat(last_collection)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                time_ago = format_relative_time(dt)
            except (ValueError, TypeError):
                pass

        lines = [
            f"{health_emoji} **System Status: {health.upper()}**",
            "",
            f"📊 Articles in database: {status.get('total_articles', 0)}",
            f"🕐 Last collection: {time_ago}",
            f"📡 Sources checked: {status.get('sources_checked', 0)}",
        ]

        failed = status.get("sources_failed", [])
        if failed:
            lines.append(f"⚠️ Failed sources: {', '.join(failed)}")
        else:
            lines.append("✅ All sources operational")

        lines.append(f"\n📊 Last updated: {now_local_formatted()}")

        return "\n".join(lines)

    def handle_query(self, text: str) -> str:
        """Handle a natural language query from the user.

        Parses the query, routes to appropriate handler, returns result.

        Args:
            text: Raw user message text.

        Returns:
            Formatted response string.
        """
        query = self.parse_query(text)

        if query.help_request:
            return self._help_message()

        if query.status_request:
            return self.get_status()

        if query.breaking_only:
            return self.get_breaking()

        if query.latest_only:
            return self.get_latest(limit=query.limit)

        return self.get_top5(
            category=query.category,
            time_hours=query.time_hours,
            limit=query.limit,
        )

    def parse_query(self, text: str) -> ParsedQuery:
        """Parse a natural language query into a structured query.

        Handles:
        - /top5
        - /top5 ai
        - /top5 world 6h
        - /breaking
        - /status
        - /latest
        - /help
        - 'What's the biggest news today?'
        - 'Top 5 AI news from the last 6 hours'

        Args:
            text: Raw user message.

        Returns:
            ParsedQuery with extracted parameters.
        """
        query = ParsedQuery(raw_text=text)
        text_lower = text.strip().lower()

        # ─── Command matching ─────────────────────────────────
        if text_lower in ("/help", "/start", "help"):
            query.help_request = True
            return query

        if text_lower in ("/status", "status"):
            query.status_request = True
            return query

        if text_lower in ("/breaking", "breaking", "breaking news"):
            query.breaking_only = True
            return query

        if text_lower in ("/latest", "latest", "recent"):
            query.latest_only = True
            return query

        # ─── Extract time range ───────────────────────────────
        # Match patterns like "6h", "6 hours", "last 12 hours"
        time_match = re.search(r"(?:last\s+)?(\d+)\s*(?:h|hours?)", text_lower)
        if time_match:
            query.time_hours = int(time_match.group(1))

        # "today" → 24 hours
        if "today" in text_lower:
            query.time_hours = 24

        # ─── Extract limit ────────────────────────────────────
        limit_match = re.search(r"top\s*(\d+)", text_lower)
        if limit_match:
            query.limit = min(int(limit_match.group(1)), 20)  # Cap at 20

        # ─── Extract category ─────────────────────────────────
        # Remove command prefix
        clean = re.sub(r"^/top\d*\s*", "", text_lower).strip()
        clean = re.sub(r"^top\s*\d*\s*", "", clean).strip()
        clean = re.sub(r"\b(news|stories|most important|right now|give me|what|the|show me)\b", "", clean).strip()
        clean = re.sub(r"\b(from|in|last|past|hours?|biggest|happening)\b", "", clean).strip()
        clean = re.sub(r"\d+\s*h?", "", clean).strip()  # Remove time patterns

        if clean:
            # Try to match a category alias
            for alias, category in CATEGORY_ALIASES.items():
                if alias in clean:
                    query.category = category
                    break

        return query

    def _no_results_message(self, category: str = None, time_hours: int = 24) -> str:
        """Message when no articles found for a query."""
        if category:
            return (
                f"📭 No {category} news found in the last {time_hours} hours.\n\n"
                "Try a broader query like /top5 or a different category."
            )
        return (
            f"📭 No news articles found in the last {time_hours} hours.\n\n"
            "The collector may not have run yet. Check /status for details."
        )

    def _help_message(self) -> str:
        """Return the help/command list message."""
        lines = [
            "**News Intelligence Agent**",
            "",
            "**Commands:**",
            "/top20 -- Top 20 most important news",
            "/top20 ai -- Top 20 AI news",
            "/top20 world -- Top 20 world news",
            "/top5 -- Top 5 only",
            "/breaking -- Current breaking news",
            "/latest -- 10 most recent articles",
            "/status -- System health",
            "/help -- This message",
            "",
            "**Natural language:**",
            "* 'What is the biggest news today?'",
            "* 'Top 10 AI news from the last 6 hours'",
            "* 'Show me breaking news'",
            "",
            f"Last updated: {now_local_formatted()}",
        ]
        return "\n".join(lines)
