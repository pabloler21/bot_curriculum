# tests/test_sessions.py
from datetime import datetime, timedelta, timezone

from backend.sessions import (
    cleanup_sessions,
    cv_sessions,
    delete_session,
    get_session,
    store_session,
)


def setup_function():
    cv_sessions.clear()


def test_store_and_get_session():
    token = store_session("cv text here", "resume.pdf")
    session = get_session(token)
    assert session is not None
    assert session.cv_text == "cv text here"
    assert session.filename == "resume.pdf"
    assert session.char_count == len("cv text here")


def test_get_session_returns_none_for_unknown_token():
    assert get_session("nonexistent-token") is None


def test_delete_session():
    token = store_session("text", "file.pdf")
    delete_session(token)
    assert get_session(token) is None


def test_delete_nonexistent_session_does_not_raise():
    delete_session("ghost-token")  # must not raise


def test_cleanup_removes_expired_sessions():
    token = store_session("text", "file.pdf")
    # Manually backdate the session
    cv_sessions[token].uploaded_at = datetime.now(timezone.utc) - timedelta(minutes=61)
    cleanup_sessions()
    assert get_session(token) is None


def test_cleanup_keeps_fresh_sessions():
    token = store_session("text", "file.pdf")
    cleanup_sessions()
    assert get_session(token) is not None
