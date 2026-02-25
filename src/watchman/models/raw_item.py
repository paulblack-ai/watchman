"""Raw item model for unprocessed feed entries."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class RawItem(BaseModel):
    """A raw, unprocessed item from a signal source.

    Raw items are stored in the raw_items table before normalization
    into signal cards. Kept for debugging, re-processing, and auditing.
    """

    id: int | None = None
    source_name: str
    collector_type: Literal["rss", "api", "scrape"]
    title: str | None = None
    url: str | None = None
    summary: str | None = None
    published_date: datetime | None = None
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    raw_data: str | None = None
    processed: bool = False
