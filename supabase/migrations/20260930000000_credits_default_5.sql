-- Task 4.1: bono de signup de 5 créditos (solo afecta a filas nuevas)
ALTER TABLE public.credits ALTER COLUMN balance SET DEFAULT 5;
