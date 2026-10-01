"""GET/PUT /cv — CV base del usuario autenticado."""
import io
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from backend import sessions
from backend.sessions import CVSession

CV_TEXT = "Jane Doe Senior Python Engineer. " * 5  # >100 chars


def _put_session(text=CV_TEXT):
    token = str(uuid.uuid4())
    sessions.cv_sessions[token] = CVSession(
        token=token, cv_text=text, filename="cv.pdf", uploaded_at=datetime.now(timezone.utc)
    )
    return token


def test_get_cv_requires_auth(client):
    assert client.get("/cv").status_code == 401


def test_get_cv_404_when_missing(client, as_user):
    with patch("src.routes.cv.get_cv", return_value=None):
        assert client.get("/cv").status_code == 404


def test_get_cv_returns_metadata_without_text(client, as_user):
    row = {"user_id": as_user, "cv_text": CV_TEXT, "filename": "cv.pdf", "source": "upload",
           "last_evaluation": {"overall_score": 70}, "updated_at": "2026-09-30T00:00:00Z"}
    with patch("src.routes.cv.get_cv", return_value=row):
        data = client.get("/cv").json()
    assert data == {"filename": "cv.pdf", "source": "upload",
                    "last_evaluation": {"overall_score": 70}, "updated_at": "2026-09-30T00:00:00Z"}


def test_put_cv_with_file(client, as_user):
    with patch("src.routes.cv_input.extract_text", return_value=CV_TEXT), \
         patch("src.routes.cv.save_cv") as save:
        res = client.put("/cv", files={"file": ("cv.pdf", io.BytesIO(b"%PDF-1.4 x"), "application/pdf")})
    assert res.status_code == 200
    save.assert_called_once_with(as_user, CV_TEXT, "cv.pdf", "upload")


def test_put_cv_claims_session_token(client, as_user):
    token = _put_session()
    with patch("src.routes.cv.save_cv") as save:
        res = client.put("/cv", headers={"X-CV-Session-Token": token}, data={})
    assert res.status_code == 200
    save.assert_called_once_with(as_user, CV_TEXT, "cv.pdf", "upload")


def test_put_cv_with_expired_token_is_400(client, as_user):
    with patch("src.routes.cv.save_cv") as save:
        res = client.put("/cv", headers={"X-CV-Session-Token": str(uuid.uuid4())}, data={})
    assert res.status_code == 400
    save.assert_not_called()


def test_put_cv_without_input_is_400(client, as_user):
    assert client.put("/cv", data={}).status_code == 400


def test_put_cv_rejects_too_short_text(client, as_user):
    token = _put_session(text="short")
    with patch("src.routes.cv.save_cv") as save:
        res = client.put("/cv", headers={"X-CV-Session-Token": token}, data={})
    assert res.status_code == 422
    save.assert_not_called()
