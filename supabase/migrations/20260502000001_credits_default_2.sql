-- Task 3.7: free tier — new users start with 2 credits instead of 0
ALTER TABLE public.credits ALTER COLUMN balance SET DEFAULT 2;
