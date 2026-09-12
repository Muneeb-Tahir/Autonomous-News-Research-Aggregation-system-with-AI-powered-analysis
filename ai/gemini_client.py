"""
Gemini API client for the News Intelligence Agent.

Uses Google Gemini 3.6 Flash (free tier) for:
- Formatting Top 5 news presentation
- Formatting breaking news alerts

Does NOT use Gemini for scoring, deduplication, or filtering.
Includes deterministic fallback if Gemini is unavailable.
"""

import json
from typing import List, Dict, Optional

import google.generativeai as genai

from config.settings import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_TEMPERATURE, GEMINI_MAX_OUTPUT_TOKENS
from ai.prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, BREAKING_PROMPT_TEMPLATE
from utils.logger import get_logger
from utils.timezone_utils import now_local_formatted

logger = get_logger(__name__)


class GeminiClient:
    """Wrapper around Google Gemini for news formatting.

    Only used for presentation — never as a news source.
    Falls back to deterministic formatting if API fails.
    """

    def __init__(self):
        """Initialize Gemini client."""
        self.available = False

        if not GEMINI_API_KEY:
            logger.warning("Gemini API key not configured. Using deterministic fallback.")
            return

        try:
            genai.configure(api_key=GEMINI_API_KEY)
            self.model = genai.GenerativeModel(
                model_name=GEMINI_MODEL,
                system_instruction=SYSTEM_PROMPT,
                generation_config=genai.GenerationConfig(
                    temperature=GEMINI_TEMPERATURE,
                    max_output_tokens=GEMINI_MAX_OUTPUT_TOKENS,
                ),
            )
            self.available = True
            logger.info(f"Gemini client initialized (model: {GEMINI_MODEL})")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini: {e}")

    def format_top5(self, articles: List[Dict]) -> str:
        """Format top articles into a presentation using Gemini.

        Falls back to deterministic formatting if Gemini fails.

        Args:
            articles: List of article dicts (from database).

        Returns:
            Formatted text string ready for Telegram/web.
        """
        if not articles:
            return "📭 No news articles found for your query."

        # Try Gemini first
        if self.available:
            try:
                result = self._call_gemini_top5(articles)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Gemini formatting failed, using fallback: {e}")

        # Deterministic fallback
        return self._deterministic_top5(articles)

    def format_breaking(self, article: Dict) -> str:
        """Format a breaking news alert using Gemini.

        Args:
            article: Article dict.

        Returns:
            Formatted breaking news text.
        """
        if self.available:
            try:
                result = self._call_gemini_breaking(article)
                if result:
                    return result
            except Exception as e:
                logger.warning(f"Gemini breaking format failed, using fallback: {e}")

        return self._deterministic_breaking(article)

    # =============================================================
    # Gemini API Calls
    # =============================================================

    def _call_gemini_top5(self, articles: List[Dict]) -> Optional[str]:
        """Call Gemini to format the Top 5 presentation.

        Args:
            articles: Article dicts to format.

        Returns:
            Formatted string, or None if call fails.
        """
        # Prepare article data (slim down to essential fields)
        slim_articles = []
        for i, a in enumerate(articles[:5], 1):
            sources_list = [a.get("source_name", "Unknown")]
            for src in (a.get("additional_sources") or []):
                if isinstance(src, dict) and src.get("name"):
                    sources_list.append(src["name"])

            source_urls = [a.get("url", "")]
            for src in (a.get("additional_sources") or []):
                if isinstance(src, dict) and src.get("url"):
                    source_urls.append(src["url"])

            slim_articles.append({
                "rank": i,
                "title": a.get("title", ""),
                "description": a.get("description", ""),
                "category": a.get("category", "GENERAL"),
                "importance_score": round(a.get("importance_score", 0)),
                "urgency_score": round(a.get("urgency_score", 0)),
                "sources": sources_list[:5],  # Cap at 5 sources
                "urls": source_urls[:5],
                "published_at": a.get("published_at", ""),
            })

        user_prompt = USER_PROMPT_TEMPLATE.format(
            count=len(slim_articles),
            current_time=now_local_formatted(),
            articles_json=json.dumps(slim_articles, indent=2),
        )

        response = self.model.generate_content(user_prompt)

        if response and response.text:
            return response.text.strip()

        return None

    def _call_gemini_breaking(self, article: Dict) -> Optional[str]:
        """Call Gemini to format a breaking news alert.

        Args:
            article: Article dict.

        Returns:
            Formatted string, or None if call fails.
        """
        slim = {
            "title": article.get("title", ""),
            "description": article.get("description", ""),
            "category": article.get("category", "GENERAL"),
            "importance_score": round(article.get("importance_score", 0)),
            "urgency_score": round(article.get("urgency_score", 0)),
            "source": article.get("source_name", "Unknown"),
            "url": article.get("url", ""),
        }

        prompt = BREAKING_PROMPT_TEMPLATE.format(
            article_json=json.dumps(slim, indent=2),
        )

        response = self.model.generate_content(prompt)

        if response and response.text:
            return response.text.strip()

        return None

    # =============================================================
    # Deterministic Fallbacks
    # =============================================================

    def _deterministic_top5(self, articles: List[Dict]) -> str:
        """Format Top 5 without AI — simple template-based formatting.

        Used when Gemini is unavailable or fails.

        Args:
            articles: Article dicts.

        Returns:
            Formatted text string.
        """
        rank_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"]
        lines = []

        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        lines.append("🔥 **TOP 5 NEWS RIGHT NOW**")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"📊 Updated: {now_local_formatted()}")
        lines.append("")

        for i, article in enumerate(articles[:5]):
            emoji = rank_emojis[i] if i < len(rank_emojis) else f"**{i+1}.**"

            # Build source list
            sources = [article.get("source_name", "Unknown")]
            for src in (article.get("additional_sources") or [])[:3]:
                if isinstance(src, dict) and src.get("name"):
                    sources.append(src["name"])

            lines.append(f"{emoji} **{article.get('title', 'Untitled')}**")
            lines.append("")
            lines.append(
                f"📁 {article.get('category', 'GENERAL')} | "
                f"🔥 {round(article.get('importance_score', 0))}/100 | "
                f"⚡ {round(article.get('urgency_score', 0))}/100"
            )
            lines.append(f"📰 {', '.join(sources)}")
            lines.append("")

            desc = article.get("description", "")
            if desc:
                # Truncate long descriptions
                if len(desc) > 300:
                    desc = desc[:297] + "..."
                lines.append(desc)
                lines.append("")

            lines.append(f"🔗 {article.get('url', '')}")
            lines.append("")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━")
            lines.append("")

        lines.append("📊 News collected from multiple sources.")
        lines.append(f"Last updated: {now_local_formatted()}")

        return "\n".join(lines)

    def _deterministic_breaking(self, article: Dict) -> str:
        """Format breaking news without AI.

        Args:
            article: Article dict.

        Returns:
            Formatted breaking news text.
        """
        lines = [
            "🚨 **BREAKING NEWS** 🚨",
            "",
            f"**{article.get('title', 'Breaking Story')}**",
            "",
            f"📁 {article.get('category', 'GENERAL')} | "
            f"🔥 {round(article.get('importance_score', 0))}/100 | "
            f"⚡ {round(article.get('urgency_score', 0))}/100",
            "",
        ]

        desc = article.get("description", "")
        if desc:
            lines.append(desc)
            lines.append("")

        lines.append(f"📰 {article.get('source_name', 'Unknown')}")
        lines.append(f"🔗 {article.get('url', '')}")

        return "\n".join(lines)
