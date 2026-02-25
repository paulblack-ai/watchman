"""Signal card model for normalized, deduplicated signals."""

import hashlib
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SignalCard(BaseModel):
    """A normalized signal card ready for scoring and review.

    Signal cards are the canonical representation of a signal after
    normalization from raw items and deduplication.
    """

    id: int | None = None
    title: str
    source_name: str
    date: datetime
    url: str
    tier: Literal[1, 2, 3]
    summary: str | None = None
    collector_type: Literal["rss", "api", "scrape"]
    url_hash: str
    content_fingerprint: str | None = None
    duplicate_of: int | None = None
    seen_count: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Phase 2: scoring fields
    relevance_score: float | None = None
    score_breakdown: str | None = None  # JSON string
    top_dimension: str | None = None

    # Phase 2: review workflow fields
    review_state: str = "pending"
    reviewed_at: datetime | None = None
    snooze_until: datetime | None = None
    slack_message_ts: str | None = None
    slack_channel_id: str | None = None

    # Phase 3: enrichment fields
    enrichment_state: str = "pending"
    enrichment_data: str | None = None  # JSON string of IcebreakerToolEntry
    enrichment_error: str | None = None
    enriched_at: datetime | None = None

    @staticmethod
    def compute_url_hash(url: str) -> str:
        """Compute SHA-256 hash of normalized URL for exact deduplication."""
        normalized = url.strip().lower().rstrip("/")
        return hashlib.sha256(normalized.encode()).hexdigest()

    @staticmethod
    def compute_content_fingerprint(title: str, date: datetime | None) -> str:
        """Compute SHA-256 hash of normalized title + date for content deduplication."""
        normalized_title = title.strip().lower()
        date_str = date.isoformat() if date else ""
        content = f"{normalized_title}|{date_str}"
        return hashlib.sha256(content.encode()).hexdigest()
