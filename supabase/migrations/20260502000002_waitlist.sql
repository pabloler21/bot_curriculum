-- Task 3.11: waitlist table for Pro tier interest
CREATE TABLE IF NOT EXISTS public.waitlist (
    email       TEXT        PRIMARY KEY,
    user_id     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.waitlist ENABLE ROW LEVEL SECURITY;

-- Anyone can insert their own email; nobody can read others' rows
CREATE POLICY "insert_own" ON public.waitlist
    FOR INSERT WITH CHECK (true);

CREATE POLICY "select_own" ON public.waitlist
    FOR SELECT USING (user_id = auth.uid()::text);
