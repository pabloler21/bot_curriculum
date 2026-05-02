# backend/credits.py
"""
Credit balance management backed by Supabase.

All writes go through atomic SQL functions (decrement_credits / increment_credits)
to avoid race conditions. Every public function is a no-op when Supabase is
unavailable, so the adapter keeps working in dev without credentials.
"""
import logging
import os

logger = logging.getLogger(__name__)

_SUPABASE_URL = os.getenv("SUPABASE_URL")
_SUPABASE_KEY = os.getenv("SUPABASE_KEY")

_supabase = None
if _SUPABASE_URL and _SUPABASE_KEY:
    try:
        from supabase import create_client
        _supabase = create_client(_SUPABASE_URL, _SUPABASE_KEY)
        logger.info("[credits] Supabase client initialized")
    except ImportError:
        logger.warning("[credits] supabase package not installed — credits disabled")


class InsufficientCredits(Exception):
    """Raised when a decrement would push balance below zero."""


def ensure_user(user_id: str) -> None:
    """Insert a credits row with balance=0 if one doesn't exist yet (idempotent)."""
    if _supabase is None:
        return
    _supabase.table("credits").upsert(
        {"user_id": user_id, "balance": 0},
        on_conflict="user_id",
        ignore_duplicates=True,
    ).execute()


def get_balance(user_id: str) -> int:
    """Return current credit balance. Returns 0 if no record or Supabase unavailable."""
    if _supabase is None:
        return 0
    result = _supabase.table("credits").select("balance").eq("user_id", user_id).execute()
    return result.data[0]["balance"] if result.data else 0


def decrement(user_id: str, amount: int = 1) -> int:
    """
    Atomically subtract `amount` credits.

    Returns the new balance.
    Raises InsufficientCredits if balance < amount.
    Returns 0 (no-op) if Supabase is unavailable.
    """
    if _supabase is None:
        return 0
    try:
        result = _supabase.rpc(
            "decrement_credits",
            {"p_user_id": user_id, "p_amount": amount},
        ).execute()
        return result.data
    except Exception as exc:
        if "insufficient_credits" in str(exc):
            raise InsufficientCredits(f"User {user_id[:8]}… has no credits") from exc
        raise


def restore(user_id: str, amount: int = 1) -> None:
    """Add credits back — call this when the pipeline fails after a decrement."""
    if _supabase is None:
        return
    _supabase.rpc(
        "increment_credits",
        {"p_user_id": user_id, "p_amount": amount},
    ).execute()


def add_credits(user_id: str, amount: int) -> int:
    """Add `amount` credits to the user's balance. Returns new balance."""
    if _supabase is None:
        return 0
    result = _supabase.rpc(
        "increment_credits",
        {"p_user_id": user_id, "p_amount": amount},
    ).execute()
    return result.data if result.data is not None else 0
