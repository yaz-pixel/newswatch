"""Postgres access: migrations, idempotent inserts, simple queries."""

import logging
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

from newswatch.schemas import Article, Source

log = logging.getLogger(__name__)


def connect(database_url: str | None) -> psycopg.Connection[dict[str, Any]]:
    """Open a connection. Rows come back as dicts. Use it as `with connect(...) as conn:`."""
    if not database_url:
        raise RuntimeError("DATABASE_URL is not set (copy .env.example to .env)")
    return psycopg.connect(database_url, row_factory=dict_row)


def apply_migrations(conn: psycopg.Connection[Any], migrations_dir: Path) -> list[str]:
    """Run every migrations/*.sql file once, in filename order. Returns the files applied now."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        " filename text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())"
    )
    done = {row["filename"] for row in conn.execute("SELECT filename FROM schema_migrations")}
    applied: list[str] = []
    for path in sorted(migrations_dir.glob("*.sql")):
        if path.name in done:
            continue
        conn.execute(path.read_text(encoding="utf-8"))  # type: ignore[arg-type]
        conn.execute("INSERT INTO schema_migrations (filename) VALUES (%s)", (path.name,))
        applied.append(path.name)
        log.info("migration applied", extra={"file": path.name})
    conn.commit()
    return applied


def upsert_sources(conn: psycopg.Connection[Any], sources: list[Source]) -> int:
    """Insert new sources and refresh changed ones, so sources.yaml stays the source of truth."""
    sql = """
        INSERT INTO sources
            (source_id, name, rss_url, region, owner_group, state_affiliated, reliability_tier)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (source_id) DO UPDATE SET
            name = EXCLUDED.name, rss_url = EXCLUDED.rss_url, region = EXCLUDED.region,
            owner_group = EXCLUDED.owner_group, state_affiliated = EXCLUDED.state_affiliated,
            reliability_tier = EXCLUDED.reliability_tier
    """
    with conn.cursor() as cur:
        for s in sources:
            cur.execute(
                sql,
                (s.source_id, s.name, s.rss_url, s.region, s.owner_group,
                 s.state_affiliated, s.reliability_tier),
            )  # fmt: skip
    conn.commit()
    return len(sources)


def insert_articles(conn: psycopg.Connection[Any], articles: list[Article]) -> int:
    """Idempotent insert: an article whose URL already exists is skipped, not duplicated.

    Returns how many rows were really new. Running the same batch twice returns 0 the second time.
    """
    sql = """
        INSERT INTO articles
            (article_id, source_id, url, title, lede, language, published_at, fetched_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (url) DO NOTHING
    """
    inserted = 0
    with conn.cursor() as cur:
        for a in articles:
            cur.execute(
                sql,
                (a.article_id, a.source_id, a.url, a.title, a.lede, a.language,
                 a.published_at, a.fetched_at),
            )  # fmt: skip
            inserted += cur.rowcount  # 1 if inserted, 0 if the URL was already there
    conn.commit()
    return inserted


def articles_fetched_on(conn: psycopg.Connection[Any], day: date) -> list[dict[str, Any]]:
    """All articles first seen during one UTC day (used for the daily JSONL snapshot)."""
    start = datetime.combine(day, time.min, tzinfo=UTC)
    rows = conn.execute(
        "SELECT article_id, source_id, url, title, lede, language, published_at, fetched_at "
        "FROM articles WHERE fetched_at >= %s AND fetched_at < %s ORDER BY fetched_at, url",
        (start, start + timedelta(days=1)),
    )
    return list(rows)
