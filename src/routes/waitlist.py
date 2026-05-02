# src/routes/waitlist.py
"""POST /waitlist — register interest in the Pro plan."""
import logging
import os

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr

from backend.auth import OptionalUser

logger = logging.getLogger(__name__)
router = APIRouter()

try:
    from supabase import create_client
    _url = os.getenv("SUPABASE_URL", "")
    _key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
    _supabase = create_client(_url, _key) if _url and _key else None
except Exception as exc:
    logger.warning("[waitlist] Supabase unavailable: %s", exc)
    _supabase = None


class WaitlistRequest(BaseModel):
    email: EmailStr


@router.post("/waitlist", status_code=201)
def join_waitlist(body: WaitlistRequest, user_id: OptionalUser):
    """
    Register an email address on the Pro waitlist.
    Idempotent — re-joining the same email is a no-op (returns 201 either way).
    """
    email = body.email.lower()

    if _supabase is None:
        logger.warning("[waitlist] Supabase unavailable — not persisting %s", email)
        return JSONResponse(status_code=201, content={"status": "ok"})

    try:
        _supabase.table("waitlist").upsert(
            {"email": email, "user_id": user_id},
            on_conflict="email",
            ignore_duplicates=True,
        ).execute()
        logger.info("[waitlist] Registered %s (user=%s)", email, user_id[:8] if user_id else "anon")
    except Exception as exc:
        logger.warning("[waitlist] Insert failed for %s: %s", email, exc)

    return JSONResponse(status_code=201, content={"status": "ok"})
