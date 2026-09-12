"""
Article scorer for the News Intelligence Agent.

Deterministic scoring — no AI needed. Calculates:
- Recency score (how fresh the article is)
- Importance score (how significant the event is)
- Urgency score (how time-sensitive it is)
- Credibility score (how trustworthy the source is)
- Final composite score (weighted combination)
"""

import re
from typing import List
from datetime import datetime, timezone

from database.models import Article
from config.settings import (
    WEIGHT_IMPORTANCE,
    WEIGHT_RECENCY,
    WEIGHT_CREDIBILITY,
    WEIGHT_URGENCY,
    WEIGHT_SOURCE_QUALITY,
    WEIGHT_CATEGORY_BOOST,
    CATEGORY_WEIGHTS,
    BREAKING_KEYWORDS,
    BREAKING_IMPORTANCE_THRESHOLD,
    BREAKING_URGENCY_THRESHOLD,
)
from utils.logger import get_logger
from utils.timezone_utils import hours_since

logger = get_logger(__name__)


class ArticleScorer:
    """Deterministic article scoring engine.

    All scoring is based on heuristics — no AI calls.
    This keeps costs at zero and results reproducible.
    """

    def score_all(self, articles: List[Article]) -> List[Article]:
        """Calculate all scores for each article.

        Args:
            articles: List of Article objects.

        Returns:
            Same list with scores populated.
        """
        for article in articles:
            article.recency_score = self._recency_score(article.published_at)
            article.importance_score = self._importance_score(article)
            article.urgency_score = self._urgency_score(article)
            article.credibility_score = self._credibility_score(article)
            article.final_score = self._final_score(article)

            # Breaking news detection
            article.is_breaking = (
                article.importance_score >= BREAKING_IMPORTANCE_THRESHOLD
                and article.urgency_score >= BREAKING_URGENCY_THRESHOLD
            )

            article.is_processed = True

        return articles

    def _recency_score(self, published_at: str) -> float:
        """Score based on how recently the article was published.

        Scoring tiers:
            < 1 hour  → 100
            1-3 hours → 80
            3-6 hours → 60
            6-12 hours → 40
            12-24 hours → 20
            24+ hours → 10

        Args:
            published_at: ISO 8601 timestamp string.

        Returns:
            Score from 0 to 100.
        """
        try:
            pub_dt = datetime.fromisoformat(published_at)
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            hours = hours_since(pub_dt)
        except (ValueError, TypeError):
            return 50.0  # Unknown age → medium score

        if hours < 1:
            return 100.0
        elif hours < 3:
            return 80.0
        elif hours < 6:
            return 60.0
        elif hours < 12:
            return 40.0
        elif hours < 24:
            return 20.0
        else:
            return 10.0

    def _importance_score(self, article: Article) -> float:
        """Heuristic importance score based on multiple signals.

        Factors:
        - Source quality (high-quality source → higher importance)
        - Category base weight (world news > lifestyle)
        - Breaking keywords in title (+bonus)
        - Multiple sources covering same story (+bonus)
        - Title information density (longer, specific titles)

        Args:
            article: Article object.

        Returns:
            Score from 0 to 100.
        """
        score = 0.0

        # 1. Source quality contribution (0-30 points)
        source_points = (article.source_quality / 10) * 30
        score += source_points

        # 2. Category base weight (0-25 points)
        cat_weight = CATEGORY_WEIGHTS.get(article.category, 40)
        cat_points = (cat_weight / 70) * 25  # Normalize to 0-25
        score += cat_points

        # 3. Breaking keywords bonus (0-20 points)
        title_lower = article.title.lower()
        keyword_hits = sum(1 for kw in BREAKING_KEYWORDS if kw in title_lower)
        keyword_points = min(keyword_hits * 10, 20)
        score += keyword_points

        # 4. Multi-source bonus (0-15 points)
        source_count = len(article.additional_sources) + 1  # +1 for primary
        multi_source_points = min((source_count - 1) * 5, 15)
        score += multi_source_points

        # 5. Title information density (0-10 points)
        # Longer, specific titles tend to indicate substantive news
        word_count = len(article.title.split())
        if word_count >= 8:
            density_points = 10
        elif word_count >= 5:
            density_points = 7
        else:
            density_points = 3

        # Penalize ALL CAPS titles (clickbait indicator)
        if article.title.isupper():
            density_points = max(0, density_points - 5)

        # Penalize clickbait patterns
        clickbait_patterns = [
            r"you won'?t believe",
            r"this is why",
            r"here'?s what",
            r"shocking",
            r"\d+ reasons",
            r"what happened next",
            r"gone wrong",
        ]
        for pattern in clickbait_patterns:
            if re.search(pattern, title_lower):
                density_points = max(0, density_points - 3)
                break

        score += density_points

        return min(score, 100.0)

    def _urgency_score(self, article: Article) -> float:
        """Score how time-sensitive the article is.

        Different from importance: a scientific discovery is important
        but not urgent; an earthquake is both important AND urgent.

        Args:
            article: Article object.

        Returns:
            Score from 0 to 100.
        """
        score = 0.0

        # 1. Recency contributes to urgency (0-40 points)
        recency_contribution = article.recency_score * 0.4
        score += recency_contribution

        # 2. Breaking keywords (0-30 points)
        title_lower = article.title.lower()
        urgent_keywords = [
            "breaking", "earthquake", "explosion", "shooting", "crash",
            "killed", "dead", "dies", "attack", "emergency", "tsunami",
            "hurricane", "tornado", "bombing", "collapse", "outbreak",
            "evacuation", "missile", "strikes", "floods", "wildfire",
            "just in", "happening now", "live", "urgent",
        ]
        hits = sum(1 for kw in urgent_keywords if kw in title_lower)
        urgent_keyword_points = min(hits * 15, 30)
        score += urgent_keyword_points

        # 3. Category urgency bias (0-20 points)
        high_urgency_categories = {
            "WORLD": 18, "POLITICS": 15, "HEALTH": 15,
            "CLIMATE": 12, "CYBERSECURITY": 12, "FINANCE": 10,
        }
        medium_urgency_categories = {
            "TECHNOLOGY": 8, "BUSINESS": 8, "AI": 7,
            "SCIENCE": 5, "SPORTS": 8, "CRYPTO": 8,
        }
        low_urgency_categories = {
            "ENTERTAINMENT": 3, "GAMING": 2, "LIFESTYLE": 2,
            "TRAVEL": 2, "MOVIES": 2, "TV": 2, "MUSIC": 2,
        }

        cat = article.category
        if cat in high_urgency_categories:
            score += high_urgency_categories[cat]
        elif cat in medium_urgency_categories:
            score += medium_urgency_categories[cat]
        elif cat in low_urgency_categories:
            score += low_urgency_categories[cat]
        else:
            score += 5  # Default

        # 4. Source quality contribution (0-10 points)
        score += (article.source_quality / 10) * 10

        return min(score, 100.0)

    def _credibility_score(self, article: Article) -> float:
        """Score the credibility/trustworthiness of the article.

        Based on:
        - Source quality (primary factor)
        - Number of independent sources
        - Whether description provides substance

        Args:
            article: Article object.

        Returns:
            Score from 0 to 100.
        """
        score = 0.0

        # 1. Source quality is the primary credibility indicator (0-50 points)
        score += (article.source_quality / 10) * 50

        # 2. Multiple sources increase credibility (0-30 points)
        source_count = len(article.additional_sources) + 1
        if source_count >= 4:
            score += 30
        elif source_count >= 3:
            score += 25
        elif source_count >= 2:
            score += 15
        # Single source: no bonus

        # 3. Content substance (0-20 points)
        # Articles with longer descriptions tend to be more substantive
        desc_len = len(article.description)
        if desc_len > 200:
            score += 20
        elif desc_len > 100:
            score += 15
        elif desc_len > 50:
            score += 10
        elif desc_len > 0:
            score += 5

        return min(score, 100.0)

    def _final_score(self, article: Article) -> float:
        """Calculate the weighted final score.

        Formula:
            importance × 0.35 +
            recency × 0.20 +
            credibility × 0.20 +
            urgency × 0.10 +
            source_quality × 0.10 +
            category_boost × 0.05

        Args:
            article: Article with individual scores already set.

        Returns:
            Weighted composite score from 0 to 100.
        """
        source_quality_normalized = (article.source_quality / 10) * 100
        category_boost = CATEGORY_WEIGHTS.get(article.category, 40)
        # Normalize category boost to 0-100 scale
        category_boost_normalized = (category_boost / 70) * 100

        final = (
            article.importance_score * WEIGHT_IMPORTANCE
            + article.recency_score * WEIGHT_RECENCY
            + article.credibility_score * WEIGHT_CREDIBILITY
            + article.urgency_score * WEIGHT_URGENCY
            + source_quality_normalized * WEIGHT_SOURCE_QUALITY
            + category_boost_normalized * WEIGHT_CATEGORY_BOOST
        )

        return round(min(final, 100.0), 1)
