"""
Story grouper for the News Intelligence Agent.

Groups related articles covering the same event using
word-overlap similarity on normalized titles.
No AI or embeddings needed — purely deterministic.
"""

import re
import uuid
from typing import List, Set, Dict

from database.models import Article
from config.settings import STORY_GROUP_SIMILARITY
from utils.logger import get_logger

logger = get_logger(__name__)

# Words to ignore in title comparison
STOP_WORDS: Set[str] = {
    "the", "a", "an", "in", "on", "at", "to", "for", "of", "and", "or",
    "is", "are", "was", "were", "has", "have", "had", "with", "by", "from",
    "that", "this", "it", "its", "as", "be", "been", "being", "but", "not",
    "no", "so", "if", "up", "out", "do", "did", "does", "can", "will",
    "would", "could", "should", "may", "might", "about", "into", "over",
    "after", "before", "just", "also", "than", "then", "more", "most",
    "says", "said", "new", "report", "reports", "according", "how",
    "what", "when", "where", "who", "why", "which", "top", "best",
}


class StoryGrouper:
    """Groups related articles that cover the same event.

    Example:
        'OpenAI launches new model' and 'OpenAI unveils latest AI model'
        → Same story group.

    This ensures Top 5 shows 5 different events, not 5 articles
    about the same thing.
    """

    def group(self, articles: List[Article]) -> List[Article]:
        """Assign story_group_id to related articles.

        Algorithm:
        1. Normalize each title to a word set
        2. Compare all pairs
        3. If word overlap >= threshold → same story group
        4. Assign the same group_id (UUID)

        Args:
            articles: List of scored Article objects.

        Returns:
            Same articles with story_group_id set.
        """
        if not articles:
            return articles

        # Build normalized title word sets
        title_words = [self._normalize_title(a.title) for a in articles]

        # Track which articles are grouped
        used = set()
        groups = []  # List of (group_id, [indices])

        for i in range(len(articles)):
            if i in used:
                continue

            # Start a new group with this article
            group_id = str(uuid.uuid4())[:8]
            group_indices = [i]
            used.add(i)

            # Find all similar articles
            for j in range(i + 1, len(articles)):
                if j in used:
                    continue

                similarity = self._word_similarity(title_words[i], title_words[j])
                if similarity >= STORY_GROUP_SIMILARITY:
                    group_indices.append(j)
                    used.add(j)

            groups.append((group_id, group_indices))

        # Assign group IDs
        multi_article_groups = 0
        for group_id, indices in groups:
            for idx in indices:
                articles[idx].story_group_id = group_id

            if len(indices) > 1:
                multi_article_groups += 1
                # Log grouped stories for debugging
                titles = [articles[idx].title[:60] for idx in indices[:3]]
                logger.debug(
                    f"Story group '{group_id}' ({len(indices)} articles): "
                    f"{', '.join(titles)}"
                )

        if multi_article_groups > 0:
            logger.info(
                f"Grouped {sum(len(g[1]) for g in groups if len(g[1]) > 1)} articles "
                f"into {multi_article_groups} story groups"
            )

        return articles

    def get_primary_per_group(self, articles: List[Dict]) -> List[Dict]:
        """From a list of articles, keep only the best one per story group.

        Used when building Top 5 to ensure diversity — 5 different
        stories, not 5 articles about the same event.

        The "best" article in each group is the one with the highest
        final_score.

        Args:
            articles: List of article dicts (from database query).

        Returns:
            Filtered list with one article per story group.
        """
        if not articles:
            return articles

        # Group by story_group_id
        groups: Dict[str, List[Dict]] = {}
        no_group = []

        for article in articles:
            group_id = article.get("story_group_id")
            if group_id:
                groups.setdefault(group_id, []).append(article)
            else:
                no_group.append(article)

        # Pick the best article from each group
        primaries = []
        for group_id, group_articles in groups.items():
            # Sort by final_score descending
            group_articles.sort(
                key=lambda a: a.get("final_score", 0),
                reverse=True,
            )
            primary = group_articles[0]

            # Merge all sources from the group
            all_sources = primary.get("additional_sources", []) or []
            for other in group_articles[1:]:
                all_sources.append({
                    "name": other.get("source_name", "Unknown"),
                    "url": other.get("url", ""),
                })
                # Include the other article's additional sources too
                other_sources = other.get("additional_sources", []) or []
                all_sources.extend(other_sources)

            primary["additional_sources"] = all_sources
            primary["source_count"] = len(all_sources) + 1  # +1 for primary
            primaries.append(primary)

        # Combine: grouped primaries + ungrouped articles
        result = primaries + no_group

        # Re-sort by final_score
        result.sort(key=lambda a: a.get("final_score", 0), reverse=True)

        removed = len(articles) - len(result)
        if removed > 0:
            logger.debug(f"Story group dedup: {len(articles)} → {len(result)} ({removed} grouped)")

        return result

    def _normalize_title(self, title: str) -> Set[str]:
        """Normalize a title into a set of significant words.

        Args:
            title: Raw title string.

        Returns:
            Set of lowercase significant words.
        """
        title = title.lower()
        title = re.sub(r"[^a-z0-9\s]", "", title)

        words = {
            word for word in title.split()
            if word not in STOP_WORDS and len(word) > 2
        }

        return words

    def _word_similarity(self, words_a: Set[str], words_b: Set[str]) -> float:
        """Calculate similarity between two word sets.

        Uses: |intersection| / |smaller set|
        This is lenient for titles of different lengths.

        Args:
            words_a: First word set.
            words_b: Second word set.

        Returns:
            Similarity score between 0.0 and 1.0.
        """
        if not words_a or not words_b:
            return 0.0

        intersection = words_a & words_b
        smaller = min(len(words_a), len(words_b))

        if smaller == 0:
            return 0.0

        return len(intersection) / smaller
