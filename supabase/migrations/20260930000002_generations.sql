-- Task 4.1: historial de generaciones (My Jobs). RLS activada SIN políticas.
CREATE TABLE IF NOT EXISTS public.generations (
  id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID        NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  kind            TEXT        NOT NULL CHECK (kind IN ('cv', 'cover', 'both', 'improve')),
  job_title       TEXT,
  company         TEXT,
  job_description TEXT,
  job_url         TEXT,
  result          JSONB       NOT NULL
);

CREATE INDEX IF NOT EXISTS generations_user_created_idx
  ON public.generations (user_id, created_at DESC);

ALTER TABLE public.generations ENABLE ROW LEVEL SECURITY;
