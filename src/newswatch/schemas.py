"""Typed data models shared by every module (Pydantic v2)."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class Source(BaseModel):
    """One row of the source registry (config/sources.yaml -> sources table)."""

    source_id: str
    name: str
    rss_url: str
    region: str | None = None
    owner_group: str | None = None  # same owner => not independent (used in P6)
    state_affiliated: bool = False
    reliability_tier: int = Field(default=2, ge=1, le=3)
    enabled: bool = True


class RawItem(BaseModel):
    """One entry exactly as the feed gave it, before any cleaning."""

    source_id: str
    url: str
    title: str
    summary: str = ""
    language: str | None = None
    published_at: datetime | None = None


class Article(BaseModel):
    """A cleaned article, ready for the articles table."""

    article_id: UUID
    source_id: str
    url: str  # canonical
    title: str
    lede: str  # short extract only; full text is never stored
    language: str | None
    published_at: datetime
    fetched_at: datetime


class FeedResult(BaseModel):
    """Health report for one feed in one collection run."""

    source_id: str
    ok: bool
    n_items: int = 0
    error: str | None = None
