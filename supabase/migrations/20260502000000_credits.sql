-- Task 3.4: credits table + atomic RPC functions
-- Apply this in Supabase Dashboard → SQL Editor

-- ── Table ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.credits (
  user_id    UUID        PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  balance    INTEGER     NOT NULL DEFAULT 0,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT balance_non_negative CHECK (balance >= 0)
);

-- ── Row Level Security ────────────────────────────────────────────────────────
ALTER TABLE public.credits ENABLE ROW LEVEL SECURITY;

CREATE POLICY "users_read_own_credits"
  ON public.credits FOR SELECT
  USING (auth.uid() = user_id);

-- ── Atomic decrement (raises if balance < amount) ─────────────────────────────
CREATE OR REPLACE FUNCTION public.decrement_credits(p_user_id UUID, p_amount INTEGER)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_new_balance INTEGER;
BEGIN
  UPDATE public.credits
  SET    balance    = balance - p_amount,
         updated_at = NOW()
  WHERE  user_id = p_user_id
  AND    balance >= p_amount
  RETURNING balance INTO v_new_balance;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'insufficient_credits';
  END IF;

  RETURN v_new_balance;
END;
$$;

-- ── Atomic increment ──────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.increment_credits(p_user_id UUID, p_amount INTEGER)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
  v_new_balance INTEGER;
BEGIN
  UPDATE public.credits
  SET    balance    = balance + p_amount,
         updated_at = NOW()
  WHERE  user_id = p_user_id
  RETURNING balance INTO v_new_balance;

  RETURN v_new_balance;
END;
$$;
