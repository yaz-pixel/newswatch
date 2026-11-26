"""Turn raw feed items into clean Articles."""

import html
import logging
import re
from datetime import datetime, timedelta
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import NAMESPACE_URL, uuid5

from newswatch.schemas import Article, RawItem

log = logging.getLogger(__name__)

# Query parameters that identify the visitor or campaign, not the page.
_TRACKING_PARAMS = frozenset(
    {
        "fbclid", "gclid", "igshid", "mc_cid", "mc_eid", "ocid", "cmpid", "ito", "ref",
        "ref_src", "cid", "smid", "partner", "taid", "at_medium", "at_campaign", "xtor",
        "cmp", "rss", "referrer", "source", "src",
    }
)  # fmt: skip
_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def _is_tracking_param(name: str) -> bool:
    name = name.lower()
    return name.startswith("utm_") or name in _TRACKING_PARAMS


def canonical_url(url: str) -> str:
    """Return one stable form of a URL, so the same article is never stored twice.

    TIER 1 (core): you retype this one yourself. Rules, in order:
      1. lowercase scheme and host, drop "www.", unify http -> https
      2. drop default ports (80, 443) and the #fragment
      3. strip the trailing slash from the path (but keep "/" for the site root)
      4. remove tracking query params (utm_*, fbclid, ...) and sort the rest
    Raises ValueError for URLs that cannot be parsed (callers drop those items).
    """
    parts = urlsplit(url.strip())
    if not parts.scheme or not parts.hostname:
        raise ValueError(f"not an absolute URL: {url!r}")

    host = parts.hostname.lower().removeprefix("www.")
    port = parts.port  # may raise ValueError on a malformed port: that is fine
    if port and port not in (80, 443):
        host = f"{host}:{port}"

    path = parts.path or "/"
    if len(path) > 1:
        path = path.rstrip("/") or "/"

    kept = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not _is_tracking_param(key)
    ]
    query = urlencode(sorted(kept))
    return urlunsplit(("https", host, path, query, ""))


def strip_html(text: str) -> str:
    """Remove tags and entities, collapse whitespace. Feed summaries often contain HTML."""
    no_tags = _TAG_RE.sub(" ", text)
    return _SPACE_RE.sub(" ", html.unescape(no_tags)).strip()


def truncate(text: str, max_chars: int) -> str:
    """Cut at a word boundary and add an ellipsis. Keeps the lede short (excerpt only)."""
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars].rsplit(" ", 1)[0].rstrip(" ,;:-")
    return f"{cut}…"


def to_article(
    item: RawItem,
    fetched_at: datetime,
    lede_max_chars: int = 500,
    max_future_skew: timedelta = timedelta(hours=1),
) -> Article | None:
    """Convert one RawItem to an Article, or None if it is unusable (no URL or no title)."""
    title = strip_html(item.title)
    if not item.url or not title:
        return None
    try:
        url = canonical_url(item.url)
    except ValueError:
        log.warning("dropping item with bad url", extra={"source_id": item.source_id})
        return None

    # Date fixes: a missing date or one in the future is replaced by the fetch time.
    published = item.published_at
    if published is None or published > fetched_at + max_future_skew:
        published = fetched_at

    return Article(
        article_id=uuid5(NAMESPACE_URL, url),  # same URL -> same id, on every machine
        source_id=item.source_id,
        url=url,
        title=title,
        lede=truncate(strip_html(item.summary), lede_max_chars),
        language=item.language,
        published_at=published,
        fetched_at=fetched_at,
    )


def normalize_all(
    items: list[RawItem],
    fetched_at: datetime,
    lede_max_chars: int = 500,
    max_future_skew: timedelta = timedelta(hours=1),
) -> tuple[list[Article], int]:
    """Normalize a batch. Returns (articles, dropped_count). Same URL twice -> kept once."""
    seen: set[str] = set()
    articles: list[Article] = []
    for item in items:
        article = to_article(item, fetched_at, lede_max_chars, max_future_skew)
        if article is None or article.url in seen:
            continue
        seen.add(article.url)
        articles.append(article)
    return articles, len(items) - len(articles)
