"""
Authenticity checker for the News Intelligence Agent.

Cross-validates news stories using multiple signals:
1. Multi-source corroboration — same event reported by independent outlets
2. Source tier system — Reuters/AP/BBC carry more weight than unknown blogs
3. Red flag detection — clickbait, missing attribution, sensationalism
4. Freshness validation — old news repackaged as new

No external API calls — uses the data we already collect from 25+ sources.
"""

import re
from typing import List, Dict, Set
from datetime import datetime, timezone

from database.models import Article
from utils.logger import get_logger
from utils.timezone_utils import hours_since

logger = get_logger(__name__)


# ─── Source Tiers ─────────────────────────────────────────
# Tier 1 (Gold): Major wire services and international broadcasters
# Tier 2 (Strong): Well-known national/tech outlets
# Tier 3 (Standard): Regional or niche outlets
# Unranked sources get a baseline score

TIER_1_SOURCES: Set[str] = {
    "reuters", "associated press", "ap", "bbc", "bbc news",
    "afp", "al jazeera", "the guardian", "the new york times",
    "the washington post", "npr",
}

TIER_2_SOURCES: Set[str] = {
    "cnn", "cnbc", "bloomberg", "financial times", "the economist",
    "wall street journal", "wsj", "techcrunch", "ars technica",
    "the verge", "wired", "nature", "science", "mit technology review",
    "espn", "abc news", "cbs news", "nbc news", "sky news", "dw",
    "france 24", "times of india", "south china morning post",
    "coindesk", "decrypt", "the information", "axios",
    "politico", "nasa", "space.com",
}

TIER_3_SOURCES: Set[str] = {
    "venturebeat", "engadget", "mashable", "9to5mac", "the register",
    "techradar", "zdnet", "pc magazine", "tom's hardware",
    "cointelegraph", "the block", "gizmodo", "eurogamer",
    "gamespot", "ign",
}

# ─── Red Flag Patterns ───────────────────────────────────
# Clickbait / sensationalism indicators
CLICKBAIT_PATTERNS = [
    r"\byou won't believe\b",
    r"\bshocking\b",
    r"\bthis one trick\b",
    r"\bwhat happens next\b",
    r"\bnumber \d+ will\b",
    r"\b\d+ reasons?\b.*\b(?:why|that)\b",
    r"\bhuge mistake\b",
    r"\beveryone is talking about\b",
    r"\binsiders reveal\b",
    r"\bsecret(?:ly)?\b",
    r"\bmind-blowing\b",
    r"\bunbelievable\b",
]

# Question headlines are often used for unverified claims
QUESTION_HEADLINE = re.compile(r"\?$")

# ALL CAPS words (more than 2) suggest sensationalism
ALL_CAPS_PATTERN = re.compile(r"\b[A-Z]{4,}\b")


class AuthenticityChecker:
    """Cross-validates news stories for authenticity.

    Produces an authenticity_score (0-100) for each article:
        90-100: Highly verified — multiple Tier 1 sources confirm
        70-89:  Well-sourced — reputable outlet + corroboration
        50-69:  Standard — single credible source, no red flags
        30-49:  Low confidence — single unknown source or red flags
        0-29:   Suspicious — multiple red flags, unverified

    The score is embedded in the article's credibility_score and
    the verification details are added to additional_sources.
    """

    def check_all(self, articles: List[Article]) -> List[Article]:
        """Run authenticity checks on all articles.

        Args:
            articles: List of scored Article objects.

        Returns:
            Same list with updated credibility scores and verification data.
        """
        # Build a story-group index for cross-referencing
        group_index = self._build_group_index(articles)

        for article in articles:
            score, flags = self._check_article(article, group_index)
            article.credibility_score = score
            # Re-calculate final score with updated credibility
            article.final_score = self._recalculate_final(article)

        verified = sum(1 for a in articles if a.credibility_score >= 70)
        flagged = sum(1 for a in articles if a.credibility_score < 50)
        logger.info(
            f"Authenticity check: {len(articles)} articles, "
            f"{verified} verified (70+), {flagged} flagged (<50)"
        )

        return articles

    def _check_article(
        self, article: Article, group_index: Dict[str, List[Article]]
    ) -> tuple:
        """Check a single article's authenticity.

        Returns:
            (score: float, flags: list of warning strings)
        """
        score = 50.0  # Baseline
        flags = []

        # ─── Signal 1: Source Tier ────────────────────────
        source_lower = article.source_name.lower().strip()

        if source_lower in TIER_1_SOURCES:
            score += 30  # Tier 1 = very trustworthy
        elif source_lower in TIER_2_SOURCES:
            score += 20  # Tier 2 = trustworthy
        elif source_lower in TIER_3_SOURCES:
            score += 10  # Tier 3 = known outlet
        else:
            score -= 5   # Unknown source
            flags.append("unknown_source")

        # ─── Signal 2: Multi-Source Corroboration ─────────
        group_id = article.story_group_id
        if group_id and group_id in group_index:
            group = group_index[group_id]
            unique_sources = set(a.source_name.lower() for a in group)
            source_count = len(unique_sources)

            if source_count >= 5:
                score += 20  # 5+ independent sources = very verified
            elif source_count >= 3:
                score += 15  # 3-4 sources = well corroborated
            elif source_count >= 2:
                score += 8   # 2 sources = some corroboration

            # Bonus if Tier 1 sources are in the group
            tier1_in_group = unique_sources & TIER_1_SOURCES
            if tier1_in_group:
                score += 5  # Wire service confirms
        else:
            # Single-source story with no corroboration
            if source_lower not in TIER_1_SOURCES:
                score -= 5
                flags.append("single_source")

        # ─── Signal 3: Red Flag Detection ─────────────────
        title_lower = article.title.lower()

        # Clickbait patterns
        clickbait_count = sum(
            1 for pattern in CLICKBAIT_PATTERNS
            if re.search(pattern, title_lower)
        )
        if clickbait_count > 0:
            score -= clickbait_count * 10
            flags.append(f"clickbait_x{clickbait_count}")

        # Question headline (weaker signal)
        if QUESTION_HEADLINE.search(article.title.strip()):
            score -= 5
            flags.append("question_headline")

        # Excessive caps
        caps_matches = ALL_CAPS_PATTERN.findall(article.title)
        if len(caps_matches) >= 2:
            score -= 8
            flags.append("excessive_caps")

        # No description or very short description
        if not article.description or len(article.description.strip()) < 20:
            score -= 5
            flags.append("no_description")

        # ─── Signal 4: Freshness Check ────────────────────
        try:
            pub_dt = datetime.fromisoformat(article.published_at)
            if pub_dt.tzinfo is None:
                pub_dt = pub_dt.replace(tzinfo=timezone.utc)
            age_hours = hours_since(pub_dt)

            if age_hours > 168:  # Older than 7 days
                score -= 10
                flags.append("old_news")
            elif age_hours > 48:
                score -= 3
                flags.append("stale")
        except (ValueError, TypeError):
            score -= 5
            flags.append("no_date")

        # ─── Signal 5: Source Quality Integration ─────────
        # Use the source's own quality rating
        if article.source_quality >= 9:
            score += 5
        elif article.source_quality <= 4:
            score -= 5
            flags.append("low_quality_source")

        # Clamp to 0-100
        score = max(0, min(100, score))

        return score, flags

    def _build_group_index(
        self, articles: List[Article]
    ) -> Dict[str, List[Article]]:
        """Build an index of story_group_id → [articles].

        Args:
            articles: All articles in the batch.

        Returns:
            Dict mapping group IDs to their member articles.
        """
        index: Dict[str, List[Article]] = {}
        for article in articles:
            if article.story_group_id:
                index.setdefault(article.story_group_id, []).append(article)
        return index

    def _recalculate_final(self, article: Article) -> float:
        """Recalculate final_score after updating credibility.

        Uses the same weights from settings.
        """
        from config.settings import (
            WEIGHT_IMPORTANCE, WEIGHT_RECENCY, WEIGHT_CREDIBILITY,
            WEIGHT_URGENCY, WEIGHT_SOURCE_QUALITY, WEIGHT_CATEGORY_BOOST,
            CATEGORY_WEIGHTS,
        )

        cat_boost = CATEGORY_WEIGHTS.get(article.category, 40) / 70.0 * 100

        final = (
            article.importance_score * WEIGHT_IMPORTANCE
            + article.recency_score * WEIGHT_RECENCY
            + article.credibility_score * WEIGHT_CREDIBILITY
            + article.urgency_score * WEIGHT_URGENCY
            + article.source_quality * 10 * WEIGHT_SOURCE_QUALITY
            + cat_boost * WEIGHT_CATEGORY_BOOST
        )

        return round(min(100, max(0, final)), 1)
