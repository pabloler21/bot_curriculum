# tests/test_credits.py
"""Unit tests for backend/credits.py — all Supabase calls are mocked."""
from unittest.mock import MagicMock, patch

import pytest

from backend.credits import InsufficientCredits

USER_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _sb(balance: int = 5) -> MagicMock:
    """Return a minimal Supabase mock pre-wired for common queries."""
    mock = MagicMock()
    # table().select().eq().execute()
    mock.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"balance": balance}]
    )
    # table().upsert().execute()
    mock.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[])
    return mock


# ── get_balance ───────────────────────────────────────────────────────────────

class TestGetBalance:
    def test_returns_balance_from_db(self):
        from backend.credits import get_balance
        with patch("backend.credits._supabase", _sb(balance=7)):
            assert get_balance(USER_ID) == 7

    def test_returns_0_when_no_record(self):
        from backend.credits import get_balance
        mock = _sb()
        mock.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
        with patch("backend.credits._supabase", mock):
            assert get_balance(USER_ID) == 0

    def test_returns_0_when_supabase_unavailable(self):
        from backend.credits import get_balance
        with patch("backend.credits._supabase", None):
            assert get_balance(USER_ID) == 0


# ── decrement ─────────────────────────────────────────────────────────────────

class TestDecrement:
    def test_returns_new_balance(self):
        from backend.credits import decrement
        mock = _sb()
        mock.rpc.return_value.execute.return_value = MagicMock(data=4)
        with patch("backend.credits._supabase", mock):
            assert decrement(USER_ID) == 4

    def test_calls_rpc_with_correct_args(self):
        from backend.credits import decrement
        mock = _sb()
        mock.rpc.return_value.execute.return_value = MagicMock(data=3)
        with patch("backend.credits._supabase", mock):
            decrement(USER_ID, amount=2)
        mock.rpc.assert_called_once_with(
            "decrement_credits", {"p_user_id": USER_ID, "p_amount": 2}
        )

    def test_raises_insufficient_credits(self):
        from backend.credits import decrement
        mock = _sb()
        mock.rpc.return_value.execute.side_effect = Exception("insufficient_credits")
        with patch("backend.credits._supabase", mock):
            with pytest.raises(InsufficientCredits):
                decrement(USER_ID)

    def test_reraises_unexpected_errors(self):
        from backend.credits import decrement
        mock = _sb()
        mock.rpc.return_value.execute.side_effect = Exception("connection timeout")
        with patch("backend.credits._supabase", mock):
            with pytest.raises(Exception, match="connection timeout"):
                decrement(USER_ID)

    def test_noop_when_supabase_unavailable(self):
        from backend.credits import decrement
        with patch("backend.credits._supabase", None):
            assert decrement(USER_ID) == 0


# ── restore ───────────────────────────────────────────────────────────────────

class TestRestore:
    def test_calls_increment_rpc(self):
        from backend.credits import restore
        mock = _sb()
        with patch("backend.credits._supabase", mock):
            restore(USER_ID, amount=1)
        mock.rpc.assert_called_once_with(
            "increment_credits", {"p_user_id": USER_ID, "p_amount": 1}
        )

    def test_noop_when_supabase_unavailable(self):
        from backend.credits import restore
        with patch("backend.credits._supabase", None):
            restore(USER_ID)  # must not raise


# ── add_credits ───────────────────────────────────────────────────────────────

class TestAddCredits:
    def test_returns_new_balance(self):
        from backend.credits import add_credits
        mock = _sb()
        mock.rpc.return_value.execute.return_value = MagicMock(data=10)
        with patch("backend.credits._supabase", mock):
            assert add_credits(USER_ID, 10) == 10

    def test_returns_0_when_rpc_returns_none(self):
        from backend.credits import add_credits
        mock = _sb()
        mock.rpc.return_value.execute.return_value = MagicMock(data=None)
        with patch("backend.credits._supabase", mock):
            assert add_credits(USER_ID, 5) == 0

    def test_noop_when_supabase_unavailable(self):
        from backend.credits import add_credits
        with patch("backend.credits._supabase", None):
            assert add_credits(USER_ID, 5) == 0


# ── ensure_user ───────────────────────────────────────────────────────────────

class TestEnsureUser:
    def test_upserts_with_zero_balance(self):
        from backend.credits import ensure_user
        mock = _sb()
        with patch("backend.credits._supabase", mock):
            ensure_user(USER_ID)
        mock.table.return_value.upsert.assert_called_once_with(
            {"user_id": USER_ID, "balance": 0},
            on_conflict="user_id",
            ignore_duplicates=True,
        )

    def test_noop_when_supabase_unavailable(self):
        from backend.credits import ensure_user
        with patch("backend.credits._supabase", None):
            ensure_user(USER_ID)  # must not raise
