# backend/db.py
"""
Cliente de Supabase con la service role key, compartido por todo el backend.

Las tablas user_cvs y generations tienen RLS activada y SIN políticas: solo esta
clave puede leerlas. Nunca exponer este cliente ni su clave al frontend.

client es None si falta SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY; los módulos que
lo usan se vuelven no-op (dev sin credenciales).
"""
import logging
import os

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

client = None

_url = os.getenv("SUPABASE_URL")
_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if _url and _key:
    try:
        from supabase import create_client

        client = create_client(_url, _key)
        logger.info("[db] Supabase service-role client initialized")
    except ImportError:
        logger.warning("[db] supabase package not installed — persistence disabled")
else:
    logger.warning("[db] SUPABASE_SERVICE_ROLE_KEY not set — credits/CVs/history disabled")
