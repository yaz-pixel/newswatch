"""Command line entry point: migrate | collect | snapshot | check-feeds."""

import argparse
import logging
from datetime import UTC, date, datetime, timedelta

from newswatch import db
from newswatch.config import load_settings, load_sources
from newswatch.ingest import rss, snapshot
from newswatch.logging_setup import setup_logging
from newswatch.process import normalize

log = logging.getLogger("newswatch")


def cmd_migrate() -> int:
    settings = load_settings()
    with db.connect(settings.database_url) as conn:
        applied = db.apply_migrations(conn, settings.migrations_dir)
    log.info("migrate done", extra={"applied": applied})
    return 0


def cmd_collect() -> int:
    settings = load_settings()
    sources = load_sources(settings.config_dir / "sources.yaml")
    now = datetime.now(UTC)
    since = now - timedelta(hours=settings.collector.lookback_hours)

    raw, results = rss.collect(sources, settings.collector, since)
    articles, dropped = normalize.normalize_all(
        raw,
        fetched_at=now,
        lede_max_chars=settings.collector.lede_max_chars,
        max_future_skew=timedelta(hours=settings.collector.max_future_skew_hours),
    )
    with db.connect(settings.database_url) as conn:
        db.upsert_sources(conn, sources)
        inserted = db.insert_articles(conn, articles)

    feeds_ok = sum(r.ok for r in results)
    log.info(
        "collect done",
        extra={
            "feeds_total": len(results),
            "feeds_ok": feeds_ok,
            "feeds_failed": len(results) - feeds_ok,
            "raw_items": len(raw),
            "articles": len(articles),
            "dropped": dropped,
            "inserted": inserted,
        },
    )
    # Fail the run (red in CI) only if nothing worked at all; a few dead feeds are normal.
    return 0 if feeds_ok > 0 else 1


def cmd_snapshot(day: date) -> int:
    settings = load_settings()
    with db.connect(settings.database_url) as conn:
        rows = db.articles_fetched_on(conn, day)
    snapshot.write_snapshot(rows, day, settings.raw_dir)
    return 0


def cmd_check_feeds() -> int:
    """Fetch every feed once and print its health. No database needed."""
    settings = load_settings()
    sources = load_sources(settings.config_dir / "sources.yaml")
    since = datetime.now(UTC) - timedelta(days=3650)  # no date filter: count everything
    _, results = rss.collect(sources, settings.collector, since)
    for r in sorted(results, key=lambda r: (r.ok, r.source_id)):
        status = f"ok  {r.n_items:>3} items" if r.ok else f"FAIL {r.error}"
        log.info("feed", extra={"source_id": r.source_id, "status": status})
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(prog="newswatch")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("migrate", help="apply SQL files in migrations/")
    sub.add_parser("collect", help="fetch feeds and store new articles")
    snap = sub.add_parser("snapshot", help="write data/raw/YYYY-MM-DD.jsonl from the database")
    snap.add_argument("--date", type=date.fromisoformat, help="UTC day, default: yesterday")
    sub.add_parser("check-feeds", help="test every feed in sources.yaml")
    args = parser.parse_args()

    setup_logging(load_settings().log_level)
    if args.command == "migrate":
        code = cmd_migrate()
    elif args.command == "collect":
        code = cmd_collect()
    elif args.command == "snapshot":
        day = args.date or (datetime.now(UTC) - timedelta(days=1)).date()
        code = cmd_snapshot(day)
    else:
        code = cmd_check_feeds()
    raise SystemExit(code)


if __name__ == "__main__":
    main()
