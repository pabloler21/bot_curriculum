# backend/sessions.py
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel

from backend.ranker import embed_text

logger = logging.getLogger(__name__)

SESSION_TTL_MINUTES = 60

# ── Supabase setup (optional) ─────────────────────────────────────────────────
# When SUPABASE_URL + SUPABASE_KEY are set, all session operations hit Postgres.
# Without them the module falls back to the in-memory dict (local dev / tests).

_SUPABASE_URL = os.getenv("SUPABASE_URL")
_SUPABASE_KEY = os.getenv("SUPABASE_KEY")
_USE_SUPABASE = bool(_SUPABASE_URL and _SUPABASE_KEY)

_supabase = None
if _USE_SUPABASE:
    try:
        from supabase import create_client
        _supabase = create_client(_SUPABASE_URL, _SUPABASE_KEY)
        logger.info("[sessions] Supabase client initialized")
    except ImportError:
        logger.warning("[sessions] supabase package not installed — falling back to in-memory")
        _USE_SUPABASE = False


# ── Model ─────────────────────────────────────────────────────────────────────

class CVSession(BaseModel):
    token: str
    cv_text: str
    cv_embedding: list[float] = []
    filename: str
    uploaded_at: datetime
    scored_jobs: dict[str, Any] = {}


# ── In-memory store (fallback) ────────────────────────────────────────────────
# Always exported so tests can inspect and manipulate it directly.
cv_sessions: dict[str, CVSession] = {}


# ── Public interface ──────────────────────────────────────────────────────────

def store_session(cv_text: str, filename: str) -> CVSession:
    """Store extracted CV text and return the new CVSession."""
    cleanup_sessions()
    token = str(uuid.uuid4())

    embedding: list[float] = []
    try:
        embedding = embed_text(cv_text)
        logger.info("[sessions] CV embedding computed (%d dims)", len(embedding))
    except Exception:
        logger.warning("[sessions] Failed to compute CV embedding", exc_info=True)

    session = CVSession(
        token=token,
        cv_text=cv_text,
        cv_embedding=embedding,
        filename=filename,
        uploaded_at=datetime.now(timezone.utc),
    )

    if _USE_SUPABASE:
        _supabase.table("cv_sessions").insert({
            "token": token,
            "cv_text": cv_text,
            "cv_embedding": embedding,
            "filename": filename,
            "uploaded_at": session.uploaded_at.isoformat(),
            "scored_jobs": {},
        }).execute()
        logger.info("[sessions][supabase] Stored session %s (%d chars)", token[:8], len(cv_text))
    else:
        cv_sessions[token] = session
        logger.info(
            "[sessions] Stored session %s (%d chars, %s)", token[:8], len(cv_text), filename
        )

    return session


def get_session(token: str) -> CVSession | None:
    """Return session if it exists and hasn't expired, else None."""
    if _USE_SUPABASE:
        try:
            uuid.UUID(token)
        except ValueError:
            return None
        return _get_session_supabase(token)

    session = cv_sessions.get(token)
    if session is None:
        return None
    if datetime.now(timezone.utc) - session.uploaded_at > timedelta(minutes=SESSION_TTL_MINUTES):
        del cv_sessions[token]
        logger.info("[sessions] Session %s expired and removed", token[:8])
        return None
    return session


def delete_session(token: str) -> bool:
    """Explicitly remove a session. Returns True if it existed."""
    if _USE_SUPABASE:
        try:
            uuid.UUID(token)
        except ValueError:
            return False
        result = _supabase.table("cv_sessions").delete().eq("token", token).execute()
        return bool(result.data)
    return cv_sessions.pop(token, None) is not None


def cleanup_sessions() -> None:
    """Remove all sessions older than SESSION_TTL_MINUTES."""
    if _USE_SUPABASE:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=SESSION_TTL_MINUTES)).isoformat()
        _supabase.table("cv_sessions").delete().lt("uploaded_at", cutoff).execute()
        logger.debug("[sessions][supabase] Cleaned up expired sessions")
        return

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=SESSION_TTL_MINUTES)
    expired = [t for t, s in cv_sessions.items() if s.uploaded_at < cutoff]
    for t in expired:
        del cv_sessions[t]
    if expired:
        logger.info("[sessions] Cleaned up %d expired sessions", len(expired))


# ── Supabase helpers ──────────────────────────────────────────────────────────

def _get_session_supabase(token: str) -> CVSession | None:
    cutoff = (datetime.now(timezone.utc) - timedelta(minutes=SESSION_TTL_MINUTES)).isoformat()
    result = (
        _supabase.table("cv_sessions")
        .select("*")
        .eq("token", token)
        .gt("uploaded_at", cutoff)
        .execute()
    )
    if not result.data:
        return None
    row = result.data[0]
    return CVSession(
        token=row["token"],
        cv_text=row["cv_text"],
        cv_embedding=row.get("cv_embedding") or [],
        filename=row["filename"],
        uploaded_at=datetime.fromisoformat(row["uploaded_at"]),
        scored_jobs=row.get("scored_jobs") or {},
    )
