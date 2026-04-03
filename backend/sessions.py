# backend/sessions.py
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)

SESSION_TTL_MINUTES = 60


class CVSession(BaseModel):
    token: str
    cv_text: str
    cv_embedding: list[float] = []
    filename: str
    uploaded_at: datetime
    scored_jobs: dict[str, Any] = {}


# Module-level store: token → CVSession
cv_sessions: dict[str, CVSession] = {}


def store_session(cv_text: str, filename: str) -> CVSession:
    """Store extracted CV text, return CVSession object."""
    cleanup_sessions()
    token = str(uuid.uuid4())
    session = CVSession(
        token=token,
        cv_text=cv_text,
        filename=filename,
        uploaded_at=datetime.now(timezone.utc),
    )
    cv_sessions[token] = session
    logger.info(
        "[sessions] Stored session %s (%d chars, %s)", token[:8], len(cv_text), filename
    )
    return session


def get_session(token: str) -> CVSession | None:
    """Return session if it exists and is not expired."""
    session = cv_sessions.get(token)
    if session is None:
        return None
    age = datetime.now(timezone.utc) - session.uploaded_at
    if age > timedelta(minutes=SESSION_TTL_MINUTES):
        del cv_sessions[token]
        logger.info("[sessions] Session %s expired and removed", token[:8])
        return None
    return session


def delete_session(token: str) -> bool:
    """Explicitly remove a session. Returns True if it existed."""
    return cv_sessions.pop(token, None) is not None


def cleanup_sessions() -> None:
    """Remove all sessions older than SESSION_TTL_MINUTES."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=SESSION_TTL_MINUTES)
    expired = [t for t, s in cv_sessions.items() if s.uploaded_at < cutoff]
    for t in expired:
        del cv_sessions[t]
    if expired:
        logger.info("[sessions] Cleaned up %d expired sessions", len(expired))
