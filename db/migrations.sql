-- Aurea — Supabase migrations
-- Run these in the Supabase SQL Editor (project dashboard → SQL Editor → New query)
-- Safe to run multiple times (all statements use IF NOT EXISTS / OR REPLACE).

-- ── cv_sessions ───────────────────────────────────────────────────────────────
-- Replaces the in-memory dict in backend/sessions.py.
-- TTL is enforced in Python (SESSION_TTL_MINUTES = 60).

CREATE TABLE IF NOT EXISTS cv_sessions (
    token        UUID        PRIMARY KEY,
    cv_text      TEXT        NOT NULL,
    cv_embedding JSONB       NOT NULL DEFAULT '[]'::jsonb,
    filename     TEXT        NOT NULL,
    uploaded_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    scored_jobs  JSONB       NOT NULL DEFAULT '{}'::jsonb
);

-- Index used by cleanup queries (DELETE WHERE uploaded_at < cutoff)
CREATE INDEX IF NOT EXISTS cv_sessions_uploaded_at_idx
    ON cv_sessions (uploaded_at);


-- ── pipeline_runs ─────────────────────────────────────────────────────────────
-- One row per /adapt invocation. Written by backend/adapter/logger.py.
-- Phase 1a: logger writes to stdout only.
-- Phase 1b: update logger.py to INSERT/UPDATE here.

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id                       UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id                   UUID        UNIQUE NOT NULL,
    user_id                  TEXT,                          -- NULL until auth is added (Phase 1b)
    status                   TEXT        NOT NULL DEFAULT 'created',
    cv_text_length           INT,
    jd_length                INT,
    output_language          TEXT        NOT NULL DEFAULT 'en',
    retries                  INT         NOT NULL DEFAULT 0,
    suspicious_bullets_count INT         NOT NULL DEFAULT 0,
    duration_ms              INT,
    error_message            TEXT,
    created_at               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS pipeline_runs_user_id_idx
    ON pipeline_runs (user_id);

CREATE INDEX IF NOT EXISTS pipeline_runs_created_at_idx
    ON pipeline_runs (created_at);

-- Auto-update updated_at on every row change
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS pipeline_runs_set_updated_at ON pipeline_runs;
CREATE TRIGGER pipeline_runs_set_updated_at
    BEFORE UPDATE ON pipeline_runs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
