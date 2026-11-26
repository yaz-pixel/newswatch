from pathlib import Path

from newswatch.ingest.rss import parse_feed

FIXTURE = Path(__file__).parent.parent / "fixtures" / "sample_feed.xml"


def test_parse_feed_extracts_items_and_skips_broken_ones() -> None:
    items = parse_feed(FIXTURE.read_bytes(), "sample")
    assert [i.title for i in items] == ["Talks resume in capital", "Item without a date"]
    assert items[0].published_at is not None
    assert items[0].published_at.tzinfo is not None
    assert items[0].language == "en"
    assert items[1].published_at is None


def test_parse_feed_on_garbage_returns_empty() -> None:
    assert parse_feed(b"<html>not a feed</html>", "sample") == []
