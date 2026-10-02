-- increment_credits / decrement_credits son SECURITY DEFINER y Postgres da EXECUTE a PUBLIC
-- por defecto: con la anon key (pública) cualquiera podía llamarlas por /rest/v1/rpc y
-- regalarse créditos. El backend las invoca con la service role, que conserva el acceso.
REVOKE EXECUTE ON FUNCTION public.increment_credits(UUID, INTEGER) FROM PUBLIC, anon, authenticated;
REVOKE EXECUTE ON FUNCTION public.decrement_credits(UUID, INTEGER) FROM PUBLIC, anon, authenticated;
