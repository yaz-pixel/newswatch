from datetime import UTC, datetime, timedelta

import pytest

from newswatch.process.normalize import (
    canonical_url,
    normalize_all,
    strip_html,
    to_article,
    truncate,
)
from newswatch.schemas import RawItem

NOW = datetime(2026, 11, 16, 8, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("http://www.Example.com/a/b/", "https://example.com/a/b"),
        ("https://example.com/a?utm_source=x&id=2&fbclid=abc", "https://example.com/a?id=2"),
        ("https://example.com/a?b=2&a=1", "https://example.com/a?a=1&b=2"),
        ("https://example.com/a#section", "https://example.com/a"),
        ("https://example.com:443/a", "https://example.com/a"),
        ("https://example.com:8080/a", "https://example.com:8080/a"),
        ("https://example.com", "https://example.com/"),
        ("  https://example.com/a  ", "https://example.com/a"),
    ],
)
def test_canonical_url(raw: str, expected: str) -> None:
    assert canonical_url(raw) == expected


def test_canonical_url_is_idempotent() -> None:
    once = canonical_url("http://www.example.com/a/?utm_medium=x&z=1&a=2")
    assert canonical_url(once) == once


@pytest.mark.parametrize("bad", ["", "not a url", "/relative/path"])
def test_canonical_url_rejects_bad_input(bad: str) -> None:
    with pytest.raises(ValueError):
        canonical_url(bad)


def test_strip_html_removes_tags_and_entities() -> None:
    assert strip_html("<p>Hello &amp; <b>world</b></p>\n  ok") == "Hello & world ok"


def test_truncate_cuts_at_word_boundary() -> None:
    assert truncate("one two three four", 10) == "one two…"
    assert truncate("short", 10) == "short"


def _item(**kw) -> RawItem:
    base = {"source_id": "s1", "url": "https://example.com/a", "title": "Title"}
    return RawItem(**{**base, **kw})


def test_to_article_basic() -> None:
    a = to_article(_item(summary="<p>Body</p>", published_at=NOW - timedelta(hours=2)), NOW)
    assert a is not None
    assert a.url == "https://example.com/a"
    assert a.lede == "Body"
    assert a.published_at == NOW - timedelta(hours=2)


def test_to_article_fixes_missing_and_future_dates() -> None:
    assert to_article(_item(published_at=None), NOW).published_at == NOW
    assert to_article(_item(published_at=NOW + timedelta(days=2)), NOW).published_at == NOW


def test_to_article_drops_unusable_items() -> None:
    assert to_article(_item(title="  "), NOW) is None
    assert to_article(_item(url="nonsense"), NOW) is None


def test_article_id_is_stable_for_same_url() -> None:
    a1 = to_article(_item(url="http://www.example.com/a/?utm_source=x"), NOW)
    a2 = to_article(_item(url="https://example.com/a"), NOW)
    assert a1.article_id == a2.article_id


def test_normalize_all_keeps_one_per_url() -> None:
    items = [
        _item(source_id="s1", url="https://example.com/a?utm_source=x"),
        _item(source_id="s2", url="https://www.example.com/a"),
        _item(url="https://example.com/b"),
        _item(url="bad"),
    ]
    articles, dropped = normalize_all(items, NOW)
    assert [a.url for a in articles] == ["https://example.com/a", "https://example.com/b"]
    assert dropped == 2
