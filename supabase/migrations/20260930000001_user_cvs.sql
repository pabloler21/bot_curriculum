-- Task 4.1: CV base por usuario. RLS activada SIN políticas: solo la service role accede.
CREATE TABLE IF NOT EXISTS public.user_cvs (
  user_id         UUID        PRIMARY KEY,
  cv_text         TEXT        NOT NULL,
  filename        TEXT,
  source          TEXT        NOT NULL DEFAULT 'upload' CHECK (source IN ('upload', 'improved')),
  last_evaluation JSONB,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE public.user_cvs ENABLE ROW LEVEL SECURITY;
