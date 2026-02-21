-- LANraragi JSONL analysis schema (text-only, pgvector-ready)
--
-- Usage:
--   psql "postgresql://user:pass@host:5432/dbname" -f schema.sql

BEGIN;

-- pgvector
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS works (
    arcid         text PRIMARY KEY,
    title         text NOT NULL DEFAULT '',
    tags          text[] NOT NULL DEFAULT ARRAY[]::text[],

    -- VLM-generated description text
    description   text,

    -- Embeddings (pgvector)
    desc_embedding   vector(1024),
    visual_embedding vector(1152),

    -- Timestamp-like fields extracted from tags (epoch seconds)
    eh_posted     bigint,
    date_added    bigint,
    lastreadtime  bigint,

    -- Raw line from JSONL (for future reprocessing)
    raw           jsonb NOT NULL DEFAULT '{}'::jsonb,

    last_seen_at  timestamptz NOT NULL DEFAULT now()
);

-- Backfill-friendly schema upgrades for existing installs
ALTER TABLE works ADD COLUMN IF NOT EXISTS description text;
ALTER TABLE works ADD COLUMN IF NOT EXISTS desc_embedding vector(1024);
ALTER TABLE works ADD COLUMN IF NOT EXISTS visual_embedding vector(1152);

-- Fast tag membership queries: WHERE tags @> ARRAY['artist:foo']
CREATE INDEX IF NOT EXISTS idx_works_tags_gin ON works USING gin (tags);
CREATE INDEX IF NOT EXISTS idx_works_lastreadtime ON works (lastreadtime);
CREATE INDEX IF NOT EXISTS idx_works_eh_posted ON works (eh_posted);
CREATE INDEX IF NOT EXISTS idx_works_date_added ON works (date_added);

-- Vector search indexes (HNSW)
CREATE INDEX IF NOT EXISTS idx_works_desc_vec ON works USING hnsw (desc_embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_works_visual_vec ON works USING hnsw (visual_embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS read_events (
    id           bigserial PRIMARY KEY,
    arcid        text NOT NULL REFERENCES works(arcid) ON DELETE CASCADE,
    read_time    bigint NOT NULL,
    source_file  text NOT NULL,
    ingested_at  timestamptz NOT NULL DEFAULT now(),
    raw          jsonb NOT NULL DEFAULT '{}'::jsonb,
    UNIQUE (arcid, read_time)
);

CREATE INDEX IF NOT EXISTS idx_read_events_read_time ON read_events (read_time);
CREATE INDEX IF NOT EXISTS idx_read_events_arcid ON read_events (arcid);

-- E-Hentai metadata cache for recommendations.
-- Stores gallery metadata + translated tags + cover embedding.
CREATE TABLE IF NOT EXISTS eh_works (
    gid                  bigint NOT NULL,
    token                text NOT NULL,
    eh_url               text NOT NULL,
    ex_url               text NOT NULL,
    title                text NOT NULL DEFAULT '',
    title_jpn            text NOT NULL DEFAULT '',
    category             text,
    tags                 text[] NOT NULL DEFAULT ARRAY[]::text[],
    tags_translated      text[] NOT NULL DEFAULT ARRAY[]::text[],
    cover_embedding      vector(1152),
    posted               bigint,
    uploader             text,
    filecount            integer,
    translation_repo_url text,
    translation_head_sha text,
    raw                  jsonb NOT NULL DEFAULT '{}'::jsonb,
    last_fetched_at      timestamptz NOT NULL DEFAULT now(),
    created_at           timestamptz NOT NULL DEFAULT now(),
    updated_at           timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (gid, token)
);

ALTER TABLE eh_works ADD COLUMN IF NOT EXISTS title_jpn text NOT NULL DEFAULT '';
ALTER TABLE eh_works ADD COLUMN IF NOT EXISTS category text;
ALTER TABLE eh_works ADD COLUMN IF NOT EXISTS tags text[] NOT NULL DEFAULT ARRAY[]::text[];
ALTER TABLE eh_works ADD COLUMN IF NOT EXISTS tags_translated text[] NOT NULL DEFAULT ARRAY[]::text[];
ALTER TABLE eh_works ADD COLUMN IF NOT EXISTS eh_url text;
ALTER TABLE eh_works ADD COLUMN IF NOT EXISTS ex_url text;
ALTER TABLE eh_works ADD COLUMN IF NOT EXISTS cover_embedding vector(1152);
ALTER TABLE eh_works ADD COLUMN IF NOT EXISTS posted bigint;
ALTER TABLE eh_works ADD COLUMN IF NOT EXISTS uploader text;
ALTER TABLE eh_works ADD COLUMN IF NOT EXISTS filecount integer;
ALTER TABLE eh_works ADD COLUMN IF NOT EXISTS translation_repo_url text;
ALTER TABLE eh_works ADD COLUMN IF NOT EXISTS translation_head_sha text;
ALTER TABLE eh_works ADD COLUMN IF NOT EXISTS raw jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE eh_works ADD COLUMN IF NOT EXISTS last_fetched_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE eh_works ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE eh_works ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

UPDATE eh_works
SET eh_url = COALESCE(eh_url, 'https://e-hentai.org/g/' || gid::text || '/' || token || '/');

UPDATE eh_works
SET ex_url = COALESCE(ex_url, 'https://exhentai.org/g/' || gid::text || '/' || token || '/');

ALTER TABLE eh_works DROP COLUMN IF EXISTS cover_image_b64;
ALTER TABLE eh_works DROP COLUMN IF EXISTS cover_mime;
ALTER TABLE eh_works DROP COLUMN IF EXISTS gallery_url;

CREATE INDEX IF NOT EXISTS idx_eh_works_posted ON eh_works (posted);
CREATE INDEX IF NOT EXISTS idx_eh_works_last_fetched ON eh_works (last_fetched_at);
CREATE INDEX IF NOT EXISTS idx_eh_works_tags_gin ON eh_works USING gin (tags);
CREATE INDEX IF NOT EXISTS idx_eh_works_tags_translated_gin ON eh_works USING gin (tags_translated);
CREATE INDEX IF NOT EXISTS idx_eh_works_cover_vec_l2 ON eh_works USING hnsw (cover_embedding vector_l2_ops);

-- Incremental EH fetch queue (cross-service safe, no shared txt file needed).
CREATE TABLE IF NOT EXISTS eh_queue (
    id            bigserial PRIMARY KEY,
    gid           bigint NOT NULL,
    token         text NOT NULL,
    eh_url        text NOT NULL,
    status        text NOT NULL DEFAULT 'pending',
    result        text,
    attempts      integer NOT NULL DEFAULT 0,
    last_error    text,
    created_at    timestamptz NOT NULL DEFAULT now(),
    updated_at    timestamptz NOT NULL DEFAULT now(),
    locked_at     timestamptz,
    completed_at  timestamptz,
    UNIQUE (gid, token)
);

CREATE INDEX IF NOT EXISTS idx_eh_queue_status_created ON eh_queue (status, created_at);
CREATE INDEX IF NOT EXISTS idx_eh_queue_gid_token ON eh_queue (gid, token);

-- Runtime configuration store (PG -> JSON -> ENV fallback chain).
CREATE TABLE IF NOT EXISTS app_config (
    scope        text NOT NULL DEFAULT 'global',
    key          text NOT NULL,
    value        text NOT NULL,
    value_type   text NOT NULL DEFAULT 'string',
    is_secret    boolean NOT NULL DEFAULT false,
    description  text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    updated_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (scope, key)
);

ALTER TABLE app_config ADD COLUMN IF NOT EXISTS scope text NOT NULL DEFAULT 'global';
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS key text;
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS value text;
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS value_type text NOT NULL DEFAULT 'string';
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS is_secret boolean NOT NULL DEFAULT false;
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS description text;
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE app_config ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_app_config_updated_at ON app_config (updated_at);

COMMIT;
