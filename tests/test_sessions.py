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


# ── Route tests ──────────────────────────────────────────────────────────────
import io
from fastapi.testclient import TestClient
from src.main import app
from unittest.mock import patch


route_client = TestClient(app)


def test_post_session_returns_token():
    fake_pdf = b"%PDF-1.4 fake content"
    with patch("src.routes.session.extract_text", return_value="extracted cv text"):
        response = route_client.post(
            "/session",
            files={"file": ("resume.pdf", io.BytesIO(fake_pdf), "application/pdf")},
        )
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["filename"] == "resume.pdf"
    assert data["char_count"] == len("extracted cv text")


def test_post_session_rejects_empty_file():
    with patch("src.routes.session.extract_text", return_value="text"):
        response = route_client.post(
            "/session",
            files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
        )
    assert response.status_code == 400


def test_post_session_rejects_oversized_file():
    big_content = b"x" * (5 * 1024 * 1024 + 1)
    with patch("src.routes.session.extract_text", return_value="text"):
        response = route_client.post(
            "/session",
            files={"file": ("big.pdf", io.BytesIO(big_content), "application/pdf")},
        )
    assert response.status_code == 413


def test_get_session_exists():
    with patch("src.routes.session.extract_text", return_value="cv text"):
        post_res = route_client.post(
            "/session",
            files={"file": ("cv.pdf", io.BytesIO(b"data"), "application/pdf")},
        )
    token = post_res.json()["token"]
    response = route_client.get(f"/session/{token}")
    assert response.status_code == 200
    data = response.json()
    assert data["exists"] is True
    assert data["filename"] == "cv.pdf"


def test_get_session_not_found():
    response = route_client.get("/session/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


def test_delete_session():
    with patch("src.routes.session.extract_text", return_value="text"):
        post_res = route_client.post(
            "/session",
            files={"file": ("cv.pdf", io.BytesIO(b"data"), "application/pdf")},
        )
    token = post_res.json()["token"]
    del_res = route_client.delete(f"/session/{token}")
    assert del_res.status_code == 204
    get_res = route_client.get(f"/session/{token}")
    assert get_res.status_code == 404
