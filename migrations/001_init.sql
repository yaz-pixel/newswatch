-- 001_init.sql: tables from Blueprint section 9.
-- P0 only writes to sources and articles; the others are created now so the schema is stable.
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE sources (
    source_id        text PRIMARY KEY,                  -- "bbc_world"
    name             text NOT NULL,
    rss_url          text NOT NULL,
    region           text,
    owner_group      text,                              -- same owner => not independent
    state_affiliated boolean DEFAULT false,
    reliability_tier smallint CHECK (reliability_tier BETWEEN 1 AND 3)
);

CREATE TABLE articles (
    article_id   uuid PRIMARY KEY,
    source_id    text REFERENCES sources(source_id),
    url          text UNIQUE NOT NULL,                  -- canonical; UNIQUE makes inserts idempotent
    title        text NOT NULL,
    lede         text,                                  -- short extract only
    language     text,
    published_at timestamptz NOT NULL,
    fetched_at   timestamptz NOT NULL DEFAULT now(),
    dup_of       uuid REFERENCES articles(article_id),  -- syndication family head (P5)
    embedding    halfvec(384),                          -- filled in P5
    event_id     uuid                                   -- set by the clusterer (P5)
);

CREATE TABLE events (
    event_id             uuid PRIMARY KEY,
    watch_id             text NOT NULL,
    title                text NOT NULL,
    centroid             halfvec(384),
    entities             text[],
    first_seen           timestamptz NOT NULL,
    last_updated         timestamptz NOT NULL,
    closed_at            timestamptz,
    tier                 text CHECK (tier IN ('critical', 'notable', 'background')),
    tier_score           real,
    model_version        text,
    status               text CHECK (status IN
                           ('reported', 'corroborated', 'confirmed', 'disputed', 'retracted')),
    independent_sources  int NOT NULL DEFAULT 1
);

CREATE TABLE briefs (
    brief_id    uuid PRIMARY KEY,
    watch_id    text NOT NULL,
    for_date    date NOT NULL,
    content_md  text NOT NULL,
    cost_usd    numeric(8, 4),
    created_at  timestamptz DEFAULT now(),
    UNIQUE (watch_id, for_date)
);

CREATE TABLE event_updates (                            -- append-only
    update_id   uuid PRIMARY KEY,
    event_id    uuid NOT NULL REFERENCES events(event_id),
    kind        text CHECK (kind IN ('new_event', 'new_fact', 'status_change', 'revision')),
    summary     text NOT NULL,
    source_ids  uuid[] NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    brief_id    uuid REFERENCES briefs(brief_id)        -- NULL until reported: prevents repeats
);

CREATE TABLE cycle_runs (
    run_id        uuid PRIMARY KEY,
    watch_id      text NOT NULL,
    window_start  timestamptz NOT NULL,
    window_end    timestamptz NOT NULL,
    status        text CHECK (status IN ('running', 'ok', 'degraded', 'failed')),
    counts        jsonb,
    cost_usd      numeric(8, 4) DEFAULT 0,
    error         text,
    started_at    timestamptz DEFAULT now(),
    finished_at   timestamptz,
    UNIQUE (watch_id, window_start)                     -- idempotency: one run per window
);
