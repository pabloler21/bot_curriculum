# backend/auth.py
"""
Supabase JWT authentication dependency for FastAPI.

Phase 1a: optional — endpoints accept requests with or without a valid JWT.
Phase 1b: make it required on /adapt to enforce free tier + credits.

Usage:
    from backend.auth import OptionalUser

    @router.post("/adapt")
    async def adapt(user_id: OptionalUser, ...):
        # user_id is a UUID string if authenticated, None otherwise
"""
import logging
import os
from typing import Annotated

from fastapi import Depends, HTTPException, Request

logger = logging.getLogger(__name__)

_SUPABASE_URL = os.getenv("SUPABASE_URL")
_SUPABASE_KEY = os.getenv("SUPABASE_KEY")

_supabase = None
if _SUPABASE_URL and _SUPABASE_KEY:
    try:
        from supabase import create_client
        _supabase = create_client(_SUPABASE_URL, _SUPABASE_KEY)
        logger.info("[auth] Supabase client initialized")
    except ImportError:
        logger.warning("[auth] supabase package not installed — auth will always return None")


def get_current_user(request: Request) -> str | None:
    """
    Extract and validate the Supabase JWT from the Authorization header.

    Returns the user_id (UUID string) if the token is valid, None otherwise.
    Never raises — invalid or missing tokens are treated as unauthenticated.
    """
    if _supabase is None:
        return None

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header.removeprefix("Bearer ").strip()
    if not token:
        return None

    try:
        response = _supabase.auth.get_user(token)
        user_id = response.user.id if response and response.user else None
        if user_id:
            logger.debug("[auth] Authenticated user %s", str(user_id)[:8])
        return str(user_id) if user_id else None
    except Exception as exc:
        logger.debug("[auth] JWT validation failed: %s", exc)
        return None


# FastAPI dependency aliases — use these in route signatures
OptionalUser = Annotated[str | None, Depends(get_current_user)]


def get_required_user(request: Request) -> str:
    """Like get_current_user but raises 401 if not authenticated."""
    user_id = get_current_user(request)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id


RequiredUser = Annotated[str, Depends(get_required_user)]
