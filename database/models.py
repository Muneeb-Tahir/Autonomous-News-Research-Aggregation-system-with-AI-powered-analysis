"""
Article data model for the News Intelligence Agent.

Every article from every source is normalized to this schema.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import datetime


@dataclass
class Article:
    """Normalized article representation.

    Every article from RSS, NewsAPI, or any future source
    is converted to this format before processing.
    """

    # Required fields
    title: str
    url: str
    source_name: str
    source_quality: int  # 1-10
    category: str
    published_at: str  # UTC ISO 8601
    collected_at: str  # UTC ISO 8601

    # Optional content fields
    description: str = ""
    content: str = ""
    author: Optional[str] = None
    image_url: Optional[str] = None
    language: str = "en"

    # Scores (0-100), calculated by processors/scorer.py
    importance_score: float = 0.0
    urgency_score: float = 0.0
    recency_score: float = 0.0
    credibility_score: float = 0.0
    final_score: float = 0.0

    # Story grouping
    story_group_id: Optional[str] = None
    additional_sources: List[Dict] = field(default_factory=list)

    # Flags
    is_breaking: bool = False
    is_processed: bool = False

    def to_dict(self) -> dict:
        """Convert to dictionary for Supabase insertion.

        Returns:
            Dict matching the articles table columns.
        """
        return {
            "url": self.url,
            "title": self.title,
            "description": self.description,
            "content": self.content,
            "source_name": self.source_name,
            "source_quality": self.source_quality,
            "author": self.author,
            "published_at": self.published_at,
            "collected_at": self.collected_at,
            "category": self.category,
            "image_url": self.image_url,
            "language": self.language,
            "importance_score": self.importance_score,
            "urgency_score": self.urgency_score,
            "recency_score": self.recency_score,
            "credibility_score": self.credibility_score,
            "final_score": self.final_score,
            "story_group_id": self.story_group_id,
            "additional_sources": self.additional_sources,
            "is_breaking": self.is_breaking,
            "is_processed": self.is_processed,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Article":
        """Create an Article from a database row dictionary.

        Args:
            data: Dictionary from Supabase query result.

        Returns:
            Article instance.
        """
        return cls(
            title=data.get("title", ""),
            url=data.get("url", ""),
            source_name=data.get("source_name", "Unknown"),
            source_quality=data.get("source_quality", 5),
            category=data.get("category", "GENERAL"),
            published_at=data.get("published_at", ""),
            collected_at=data.get("collected_at", ""),
            description=data.get("description", ""),
            content=data.get("content", ""),
            author=data.get("author"),
            image_url=data.get("image_url"),
            language=data.get("language", "en"),
            importance_score=data.get("importance_score", 0.0),
            urgency_score=data.get("urgency_score", 0.0),
            recency_score=data.get("recency_score", 0.0),
            credibility_score=data.get("credibility_score", 0.0),
            final_score=data.get("final_score", 0.0),
            story_group_id=data.get("story_group_id"),
            additional_sources=data.get("additional_sources", []),
            is_breaking=data.get("is_breaking", False),
            is_processed=data.get("is_processed", False),
        )

    def __str__(self) -> str:
        return f"[{self.category}] {self.title} ({self.source_name}, score={self.final_score:.0f})"
