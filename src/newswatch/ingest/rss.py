"""Fetch RSS/Atom feeds concurrently and turn entries into RawItems."""

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime

import feedparser
import httpx

from newswatch.config import CollectorSettings
from newswatch.schemas import FeedResult, RawItem, Source

log = logging.getLogger(__name__)


def _entry_datetime(entry: feedparser.FeedParserDict) -> datetime | None:
    """feedparser gives dates as UTC time.struct_time; convert to a timezone-aware datetime."""
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed is None:
        return None
    return datetime(*parsed[:6], tzinfo=UTC)


def parse_feed(content: bytes, source_id: str) -> list[RawItem]:
    """Pure function: feed bytes in, RawItems out (easy to unit test with a saved XML file)."""
    parsed = feedparser.parse(content)
    feed_language = parsed.feed.get("language")
    items: list[RawItem] = []
    for entry in parsed.entries:
        link = entry.get("link")
        title = entry.get("title")
        if not link or not title:
            continue
        items.append(
            RawItem(
                source_id=source_id,
                url=link,
                title=title,
                summary=entry.get("summary", ""),
                language=entry.get("language") or feed_language,
                published_at=_entry_datetime(entry),
            )
        )
    return items


def fetch_feed(client: httpx.Client, source: Source) -> tuple[list[RawItem], FeedResult]:
    """Download and parse one feed. Never raises: one broken feed must not stop the others."""
    try:
        response = client.get(source.rss_url)
        response.raise_for_status()
        items = parse_feed(response.content, source.source_id)
    except Exception as exc:  # noqa: BLE001 - isolation is the point; the error is recorded
        return [], FeedResult(source_id=source.source_id, ok=False, error=repr(exc)[:200])
    if not items:
        return [], FeedResult(source_id=source.source_id, ok=False, error="no entries parsed")
    return items, FeedResult(source_id=source.source_id, ok=True, n_items=len(items))


def collect(
    sources: list[Source], settings: CollectorSettings, since: datetime
) -> tuple[list[RawItem], list[FeedResult]]:
    """Fetch all enabled feeds in parallel; keep items published at or after `since`.

    Items with no date are kept (normalize will date them); the database's UNIQUE(url)
    makes re-seeing an item harmless.
    """
    enabled = [s for s in sources if s.enabled]
    with (
        httpx.Client(
            timeout=settings.timeout_seconds,
            headers={"User-Agent": settings.user_agent},
            follow_redirects=True,
        ) as client,
        ThreadPoolExecutor(max_workers=settings.max_workers) as pool,
    ):
        fetched = list(pool.map(lambda s: fetch_feed(client, s), enabled))

    items: list[RawItem] = []
    results: list[FeedResult] = []
    for feed_items, result in fetched:
        results.append(result)
        if not result.ok:
            log.warning(
                "feed failed",
                extra={"source_id": result.source_id, "error": result.error},
            )
        items.extend(i for i in feed_items if i.published_at is None or i.published_at >= since)
    return items, results
