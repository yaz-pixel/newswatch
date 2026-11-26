# P0 walkthrough: what the code does and why

Goal of P0: every 4 hours, GitHub Actions reads ~37 RSS feeds and stores new articles in Neon,
without anyone touching it. Nothing here is smart yet; it is plumbing that must be reliable.

## The data flow (one run of `collect`)

    sources.yaml --> rss.collect --> normalize_all --> db.insert_articles --> Neon
       (who)         (download)       (clean)           (idempotent)        (articles)
                                                              \--> daily snapshot -> data/raw/DATE.jsonl

## File by file

| File | Tier | What it does | Why this way |
|---|---|---|---|
| `schemas.py` | 2 | Pydantic models: Source, RawItem, Article, FeedResult | Typed data between modules; bad data fails at the boundary |
| `config.py` | 2 | Reads `settings.yaml`, `sources.yaml`, env vars (DATABASE_URL) | No hard-coded values; secrets only from env |
| `logging_setup.py` | 2 | JSON log lines with a `run_id` | In CI the log IS the run page; JSON is searchable |
| `ingest/rss.py` | 2 | `parse_feed` (pure) + `fetch_feed` + `collect` (8 threads) | Downloading is I/O-bound, so threads give ~8x speed; one dead feed never stops the rest |
| `process/normalize.py` | 2 (`canonical_url` = **Tier 1**) | URL cleanup, HTML stripping, date fixes, within-batch dedupe | Same article must have one URL, otherwise duplicates fill the DB |
| `db.py` | 2 | migrations runner, upsert sources, insert articles, day query | `ON CONFLICT (url) DO NOTHING` = idempotent inserts |
| `ingest/snapshot.py` | 2 | Writes one JSON object per line per day | Backup + the raw material for replay evaluation later |
| `main.py` | 3 | CLI: migrate, collect, snapshot, check-feeds | Thin; logic lives in modules |
| `migrations/*.sql` | 3 | Tables from Blueprint section 9; indexes | Schema in git, applied in order, once |
| `.github/workflows/cycle.yml` | 3 | Cron every 4 h: migrate, collect, snapshot once a day | Free scheduler; secrets from repo settings |

## Key ideas to explain to your student

1. **Idempotent insert.** `articles.url` is UNIQUE and the insert says `ON CONFLICT DO NOTHING`.
   Running the same batch twice stores it once. That is why a late or repeated cron run is safe.
2. **Lookback overlap.** Each run looks back 12 h although the cadence is 4 h. If a run is skipped
   (GitHub often starts cron late or skips), the next run fills the gap. Safe only because of (1).
3. **Canonical URL.** `http://www.x.com/a/?utm_source=rss` and `https://x.com/a` are one article.
   We lowercase, drop `www.`, force https, remove tracking params, sort params, drop the fragment
   and the trailing slash. Known limit: it is rule-based, so it cannot know a site's own redirects.
4. **Deterministic article_id.** `uuid5(NAMESPACE_URL, url)`: same URL gives the same id on every
   machine, so re-processing never creates a different id for the same article.
5. **Failure isolation.** `fetch_feed` catches every exception and returns a FeedResult. The run
   fails (red in CI) only if zero feeds worked. A few dead feeds are normal; P1 prunes them.
6. **Cron is UTC.** `0 */4 * * *` = 00, 04, 08 ... UTC = 05:30, 09:30 ... IST. GitHub may start it
   late, and pauses schedules after ~60 days without repo activity (public repos).
7. **Pure functions are tested** (`parse_feed`, `canonical_url`, `to_article`); network and DB
   code is not unit-tested yet. The integration test comes in P5.
8. **Snapshot** is built from the DB, not from the run, so re-running it never loses rows.

## How to run it

    cp .env.example .env            # paste the Neon connection string into DATABASE_URL
    uv sync
    make test && make lint
    make check-feeds                # which feed URLs are alive? (needs internet)
    make migrate                    # creates the tables in Neon
    make collect                    # first real collection; run it twice: 2nd run inserts ~0
    # then: GitHub repo -> Settings -> Secrets and variables -> Actions -> New secret
    #       name DATABASE_URL, value = the Neon string; Actions tab -> cycle -> Run workflow

Expected `collect` log (JSON): `feeds_ok` around 30+, `inserted` in the hundreds the first time.

## Be honest about these

- The feed URLs and the owner / state-affiliated / tier values in `sources.yaml` are first-pass
  guesses written without testing the URLs. Run `make check-feeds` and fix or remove dead ones.
- Reuters and AP are not in the list: they no longer offer public RSS feeds.
- `normalize.py` has no language detection yet; `language` is whatever the feed declares.
- The migration SQL was tested on plain Postgres with the vector parts stubbed out, not on
  Neon with pgvector. `halfvec` needs pgvector 0.7+, which Neon supports.
- Your own `migrations/001_init.sql` may differ from mine. Compare before overwriting.

## Check questions (answer in your own words)

1. Why does running `collect` twice not create duplicate rows? Which line does that?
2. Why look back 12 hours when the cron runs every 4?
3. What happens to the run if 5 of 37 feeds are down? If all 37 are?

## Anki cards

- Q: What makes an insert idempotent in this project?
  A: A UNIQUE constraint on `articles.url` plus `ON CONFLICT (url) DO NOTHING`.
- Q: Why is the collector lookback longer than the cron interval?
  A: Cron runs can be late or skipped; overlap fills the gap and idempotent inserts absorb repeats.
- Q: What does `canonical_url` do and why?
  A: Maps URL variants (http/www/utm params/trailing slash) to one form so an article is stored once.

## Skills covered (Blueprint checklist)

Python, SQL, git (you commit), pytest, logging, system design (idempotency, failure isolation),
CI/CD and scheduling (Actions cron in UTC, secrets in CI). Skipped for now: Docker (P7),
embeddings and everything after P0, LLM APIs.

## Your practice due (project rules)

- Tier 1 `canonical_url()`: retype from memory today, cold rebuild tomorrow, again in 7 days.
- Tier 2 files: explain each back in your words and rewrite the one key function once
  (`insert_articles`, `parse_feed`, `to_article`).
- Bug log: for every real bug, write symptom -> your hypothesis -> what the AI said -> how you verified.
