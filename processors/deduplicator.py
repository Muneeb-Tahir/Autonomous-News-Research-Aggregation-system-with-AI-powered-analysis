"""
Article deduplicator for the News Intelligence Agent.

Two-stage deduplication:
1. URL-based: Exact URL match (fast, deterministic)
2. Title-based: Normalized title similarity (catches rewrites/syndication)
"""

import re
from typing import List, Set

from database.models import Article
from config.settings import TITLE_SIMILARITY_THRESHOLD
from utils.logger import get_logger

logger = get_logger(__name__)

# Common stop words to ignore in title comparison
STOP_WORDS: Set[str] = {
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or",
    "is", "are", "was", "were", "has", "have", "had", "with", "by", "from",
    "that", "this", "it", "its", "as", "be", "been", "being", "but", "not",
    "no", "so", "if", "up", "out", "do", "did", "does", "can", "will",
    "would", "could", "should", "may", "might", "shall", "about", "into",
    "over", "after", "before", "between", "under", "above", "below",
    "just", "also", "than", "then", "more", "most", "very", "too",
    "how", "what", "when", "where", "who", "why", "which", "new",
    "says", "said", "report", "reports", "according",
}


class Deduplicator:
    """Removes duplicate articles by URL and title similarity."""

    def deduplicate_urls(self, articles: List[Article]) -> List[Article]:
        """Remove articles with identical URLs.

        Keeps the article with the higher source quality when
        duplicates are found.

        Args:
            articles: List of Article objects.

        Returns:
            Deduplicated list.
        """
        seen_urls = {}  # url → Article

        for article in articles:
            normalized_url = self._normalize_url(article.url)

            if normalized_url in seen_urls:
                existing = seen_urls[normalized_url]
                # Keep the one from the higher-quality source
                if article.source_quality > existing.source_quality:
                    # Move existing to additional_sources of new article
                    article.additional_sources.append({
                        "name": existing.source_name,
                        "url": existing.url,
                    })
                    article.additional_sources.extend(existing.additional_sources)
                    seen_urls[normalized_url] = article
                else:
                    # Keep existing, add new as additional source
                    existing.additional_sources.append({
                        "name": article.source_name,
                        "url": article.url,
                    })
            else:
                seen_urls[normalized_url] = article

        result = list(seen_urls.values())
        removed = len(articles) - len(result)
        if removed > 0:
            logger.debug(f"URL dedup: removed {removed} duplicates ({len(articles)} → {len(result)})")

        return result

    def deduplicate_titles(self, articles: List[Article]) -> List[Article]:
        """Remove articles with similar titles (likely same story from different sources).

        Uses normalized title word overlap. When duplicates are found,
        keeps the highest-quality source and merges source lists.

        Args:
            articles: List of Article objects (already URL-deduped).

        Returns:
            Deduplicated list with merged source information.
        """
        if not articles:
            return articles

        # Build normalized title word sets
        title_data = []
        for article in articles:
            words = self._normalize_title(article.title)
            title_data.append((article, words))

        # Group similar articles
        used = set()  # Indices of articles already merged
        result = []

        for i, (article_a, words_a) in enumerate(title_data):
            if i in used:
                continue

            # Find all similar articles
            group = [article_a]
            for j, (article_b, words_b) in enumerate(title_data):
                if j <= i or j in used:
                    continue

                similarity = self._word_similarity(words_a, words_b)
                if similarity >= TITLE_SIMILARITY_THRESHOLD:
                    group.append(article_b)
                    used.add(j)

            used.add(i)

            # Merge group: keep highest quality, collect all sources
            if len(group) > 1:
                merged = self._merge_group(group)
                result.append(merged)
            else:
                result.append(article_a)

        removed = len(articles) - len(result)
        if removed > 0:
            logger.debug(f"Title dedup: merged {removed} similar articles ({len(articles)} → {len(result)})")

        return result

    def _merge_group(self, group: List[Article]) -> Article:
        """Merge a group of similar articles into one.

        Keeps the article from the highest-quality source.
        Adds all other sources to additional_sources.

        Args:
            group: List of similar Article objects.

        Returns:
            Single merged Article.
        """
        # Sort by source quality (highest first)
        group.sort(key=lambda a: a.source_quality, reverse=True)

        primary = group[0]

        # Collect additional sources from all other articles
        for other in group[1:]:
            primary.additional_sources.append({
                "name": other.source_name,
                "url": other.url,
            })
            # Also include any sources the other article had
            primary.additional_sources.extend(other.additional_sources)

        return primary

    def _normalize_url(self, url: str) -> str:
        """Normalize a URL for comparison.

        Removes trailing slashes, query params (some), fragments,
        and normalizes protocol.

        Args:
            url: Raw URL string.

        Returns:
            Normalized URL string.
        """
        url = url.strip().lower()

        # Remove fragment
        url = url.split("#")[0]

        # Remove common tracking parameters
        url = re.sub(r"[?&](utm_\w+|ref|source|fbclid|gclid)=[^&]*", "", url)

        # Remove trailing ?
        url = url.rstrip("?&")

        # Remove trailing slash
        url = url.rstrip("/")

        return url

    def _normalize_title(self, title: str) -> Set[str]:
        """Normalize a title into a set of significant words.

        Removes punctuation, stop words, and short words.

        Args:
            title: Raw title string.

        Returns:
            Set of significant lowercase words.
        """
        # Lowercase and remove punctuation
        title = title.lower()
        title = re.sub(r"[^a-z0-9\s]", "", title)

        # Split into words, remove stop words and short words
        words = {
            word for word in title.split()
            if word not in STOP_WORDS and len(word) > 2
        }

        return words

    def _word_similarity(self, words_a: Set[str], words_b: Set[str]) -> float:
        """Calculate similarity between two word sets.

        Uses Jaccard-like similarity: |intersection| / |smaller set|.
        Using the smaller set as denominator makes it more lenient
        for titles of different lengths.

        Args:
            words_a: First word set.
            words_b: Second word set.

        Returns:
            Similarity score between 0.0 and 1.0.
        """
        if not words_a or not words_b:
            return 0.0

        intersection = words_a & words_b
        # Use the smaller set as denominator to be more lenient
        smaller = min(len(words_a), len(words_b))

        if smaller == 0:
            return 0.0

        return len(intersection) / smaller
