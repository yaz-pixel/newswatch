-- 002_indexes.sql: indexes from Blueprint section 9.
CREATE INDEX articles_fetched_at_idx ON articles (fetched_at);
CREATE INDEX articles_published_at_idx ON articles (published_at);
CREATE INDEX articles_embedding_idx ON articles USING hnsw (embedding halfvec_cosine_ops);
CREATE INDEX events_centroid_idx ON events USING hnsw (centroid halfvec_cosine_ops);
CREATE INDEX events_open_idx ON events (watch_id, last_updated) WHERE closed_at IS NULL;
