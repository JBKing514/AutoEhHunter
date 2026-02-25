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
    cover_embedding_status text NOT NULL DEFAULT 'pending',

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
ALTER TABLE works ADD COLUMN IF NOT EXISTS cover_embedding_status text NOT NULL DEFAULT 'pending';

UPDATE works
SET cover_embedding_status = CASE
    WHEN visual_embedding IS NOT NULL THEN 'complete'
    WHEN cover_embedding_status IN ('pending', 'processing', 'complete', 'fail') THEN cover_embedding_status
    ELSE 'pending'
END;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'works_cover_embedding_status_chk'
    ) THEN
        ALTER TABLE works
        ADD CONSTRAINT works_cover_embedding_status_chk
        CHECK (cover_embedding_status IN ('pending', 'processing', 'complete', 'fail'));
    END IF;
END $$;

-- Fast tag membership queries: WHERE tags @> ARRAY['artist:foo']
CREATE INDEX IF NOT EXISTS idx_works_tags_gin ON works USING gin (tags);
CREATE INDEX IF NOT EXISTS idx_works_lastreadtime ON works (lastreadtime);
CREATE INDEX IF NOT EXISTS idx_works_eh_posted ON works (eh_posted);
CREATE INDEX IF NOT EXISTS idx_works_date_added ON works (date_added);
CREATE INDEX IF NOT EXISTS idx_works_cover_status ON works (cover_embedding_status);

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
    cover_embedding_status text NOT NULL DEFAULT 'pending',
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
ALTER TABLE eh_works ADD COLUMN IF NOT EXISTS cover_embedding_status text NOT NULL DEFAULT 'pending';
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

UPDATE eh_works
SET cover_embedding_status = CASE
    WHEN cover_embedding IS NOT NULL THEN 'complete'
    WHEN cover_embedding_status IN ('pending', 'processing', 'complete', 'fail') THEN cover_embedding_status
    ELSE 'pending'
END;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'eh_works_cover_embedding_status_chk'
    ) THEN
        ALTER TABLE eh_works
        ADD CONSTRAINT eh_works_cover_embedding_status_chk
        CHECK (cover_embedding_status IN ('pending', 'processing', 'complete', 'fail'));
    END IF;
END $$;

ALTER TABLE eh_works DROP COLUMN IF EXISTS cover_image_b64;
ALTER TABLE eh_works DROP COLUMN IF EXISTS cover_mime;
ALTER TABLE eh_works DROP COLUMN IF EXISTS gallery_url;

CREATE INDEX IF NOT EXISTS idx_eh_works_posted ON eh_works (posted);
CREATE INDEX IF NOT EXISTS idx_eh_works_last_fetched ON eh_works (last_fetched_at);
CREATE INDEX IF NOT EXISTS idx_eh_works_cover_status ON eh_works (cover_embedding_status);
CREATE INDEX IF NOT EXISTS idx_eh_works_tags_gin ON eh_works USING gin (tags);
CREATE INDEX IF NOT EXISTS idx_eh_works_tags_translated_gin ON eh_works USING gin (tags_translated);
CREATE INDEX IF NOT EXISTS idx_eh_works_cover_vec ON eh_works USING hnsw (cover_embedding vector_cosine_ops);

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

-- Short-term memory for Web UI chat session context.
CREATE TABLE IF NOT EXISTS chat_history (
    id           bigserial PRIMARY KEY,
    session_id   text NOT NULL,
    user_id      text NOT NULL DEFAULT 'default_user',
    role         text NOT NULL,
    content      text NOT NULL,
    tool_calls   jsonb,
    created_at   timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS session_id text;
ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS user_id text NOT NULL DEFAULT 'default_user';
ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS role text;
ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS content text;
ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS tool_calls jsonb;
ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_chat_history_session ON chat_history (session_id);
CREATE INDEX IF NOT EXISTS idx_chat_history_user_session_created ON chat_history (user_id, session_id, created_at);

-- Long-term semantic memory for Agent retrieval (facts/preferences/blacklist).
CREATE TABLE IF NOT EXISTS semantic_memory (
    id           bigserial PRIMARY KEY,
    user_id      text NOT NULL DEFAULT 'default_user',
    fact         text NOT NULL,
    embedding    vector(1024),
    created_at   timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE semantic_memory ADD COLUMN IF NOT EXISTS user_id text NOT NULL DEFAULT 'default_user';
ALTER TABLE semantic_memory ADD COLUMN IF NOT EXISTS fact text;
ALTER TABLE semantic_memory ADD COLUMN IF NOT EXISTS embedding vector(1024);
ALTER TABLE semantic_memory ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_semantic_memory_user_created ON semantic_memory (user_id, created_at);
CREATE INDEX IF NOT EXISTS idx_semantic_memory_vec ON semantic_memory USING hnsw (embedding vector_cosine_ops);

-- User interactions for recommendation feedback (click/read/dislike).
CREATE TABLE IF NOT EXISTS user_interactions (
    id           bigserial PRIMARY KEY,
    user_id      text NOT NULL DEFAULT 'default_user',
    session_id   text,
    arcid        text NOT NULL,
    action_type  text NOT NULL,
    weight       double precision NOT NULL DEFAULT 1.0,
    created_at   timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT user_interactions_action_type_chk CHECK (action_type IN ('click', 'read', 'dislike', 'impression'))
);

ALTER TABLE user_interactions ADD COLUMN IF NOT EXISTS user_id text NOT NULL DEFAULT 'default_user';
ALTER TABLE user_interactions ADD COLUMN IF NOT EXISTS session_id text;
ALTER TABLE user_interactions ADD COLUMN IF NOT EXISTS arcid text;
ALTER TABLE user_interactions ADD COLUMN IF NOT EXISTS action_type text;
ALTER TABLE user_interactions ADD COLUMN IF NOT EXISTS weight double precision NOT NULL DEFAULT 1.0;
ALTER TABLE user_interactions ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'user_interactions_action_type_chk'
    ) THEN
        ALTER TABLE user_interactions
        ADD CONSTRAINT user_interactions_action_type_chk
        CHECK (action_type IN ('click', 'read', 'dislike', 'impression'));
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_user_interactions_user_arcid ON user_interactions (user_id, arcid);
CREATE INDEX IF NOT EXISTS idx_user_interactions_user_action_created ON user_interactions (user_id, action_type, created_at);
CREATE INDEX IF NOT EXISTS idx_user_interactions_session_created ON user_interactions (session_id, created_at);

-- Cached user vector profile for fast Rocchio-style recommend retrieval.
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id      text PRIMARY KEY,
    session_id   text,
    base_vector  vector(1024),
    updated_at   timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS session_id text;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS base_vector vector(1024);
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_user_profiles_updated_at ON user_profiles (updated_at);

COMMIT;
