import io
from datetime import date, datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.jobs import Job
from backend.jobs import _cache as jobs_cache
from backend.sessions import cv_sessions, store_session
from src.main import app

eval_client = TestClient(app)


def setup_function():
    cv_sessions.clear()
    jobs_cache["data"] = None


def make_job(job_id: str) -> Job:
    return Job(
        id=job_id,
        title="Python Developer",
        company="Test Co",
        location="Remote",
        employment_type="full_time",
        salary_range=None,
        description="Python FastAPI developer needed. Must know Docker.",
        tags=["python"],
        url=f"https://example.com/{job_id}",
        posted_at=date(2025, 1, 1),
    )


MOCK_EVAL = {
    "candidate_name": "John Doe",
    "overall_score": 75,
    "approved": False,
    "formatting_issues": [],
    "keywords_found": ["Python"],
    "keywords_missing": ["Docker"],
    "recommendations": ["Add Docker"],
    "summary": "Good candidate",
}


def test_post_evaluate_with_job_id_injects_description():
    jobs_cache["data"] = ([make_job("42")], datetime.now(timezone.utc))

    with patch("src.routes.evaluate.evaluate_cv", return_value=MOCK_EVAL) as mock_eval:
        with patch("src.routes.evaluate.extract_text", return_value="My Python CV"):
            eval_client.post(
                "/evaluate",
                data={"job_id": "42"},
                files={"file": ("cv.pdf", io.BytesIO(b"data"), "application/pdf")},
            )
    # evaluate_cv must have been called with job_context containing the job description
    call_kwargs = mock_eval.call_args
    job_context = call_kwargs.kwargs.get("job_context") or (
        call_kwargs.args[1] if len(call_kwargs.args) > 1 else None
    )
    assert job_context is not None
    assert "Docker" in job_context


def test_post_evaluate_with_unknown_job_id_falls_back_to_generic():
    jobs_cache["data"] = ([make_job("999")], datetime.now(timezone.utc))

    with patch("src.routes.evaluate.evaluate_cv", return_value=MOCK_EVAL) as mock_eval:
        with patch("src.routes.evaluate.extract_text", return_value="My CV"):
            eval_client.post(
                "/evaluate",
                data={"job_id": "unknown-id"},
                files={"file": ("cv.pdf", io.BytesIO(b"data"), "application/pdf")},
            )
    call_kwargs = mock_eval.call_args
    job_context = call_kwargs.kwargs.get("job_context") or (
        call_kwargs.args[1] if len(call_kwargs.args) > 1 else None
    )
    # No job found → job_context should be None or empty
    assert not job_context


def test_post_evaluate_with_session_token_uses_session_cv():
    cv_sessions.clear()
    token = store_session("Session CV text", "cv.pdf").token

    with patch("src.routes.evaluate.evaluate_cv", return_value=MOCK_EVAL) as mock_eval:
        response = eval_client.post(
            "/evaluate",
            data={},
            files={"file": ("empty.pdf", io.BytesIO(b""), "application/pdf")},
            headers={"X-CV-Session-Token": token},
        )
    assert response.status_code == 200
    call_kwargs = mock_eval.call_args
    cv_text_used = (
        call_kwargs.args[0]
        if call_kwargs.args
        else call_kwargs.kwargs.get("cv_text")
    )
    assert cv_text_used == "Session CV text"


def _reset_evaluate_limiter():
    """Reset slowapi in-memory hit counters for /evaluate."""
    from src.routes.evaluate import limiter as _lim
    _lim._storage.reset()


def test_post_evaluate_without_file_uses_session_token():
    """Bug fix: file=None + X-CV-Session-Token must not return 422."""
    _reset_evaluate_limiter()
    cv_sessions.clear()
    token = store_session("Session CV text", "cv.pdf").token

    with patch("src.routes.evaluate.evaluate_cv", return_value=MOCK_EVAL) as mock_eval:
        response = eval_client.post(
            "/evaluate",
            headers={"X-CV-Session-Token": token},
        )
    assert response.status_code == 200
    cv_text_used = (
        mock_eval.call_args.args[0]
        if mock_eval.call_args.args
        else mock_eval.call_args.kwargs.get("cv_text")
    )
    assert cv_text_used == "Session CV text"


def test_post_evaluate_without_file_or_session_returns_400():
    """No file and no session token must return 400, not 422."""
    _reset_evaluate_limiter()
    response = eval_client.post("/evaluate")
    assert response.status_code == 400
    assert response.json()["detail"] == "No CV provided"


# ── Task 4.1: strengths/weaknesses + CV base ──────────────────────────────────
import uuid as _uuid
from datetime import datetime as _dt
from datetime import timezone as _tz
from unittest.mock import patch as _patch

from backend import sessions as _sessions
from backend.evaluator import ResumeEvaluation
from backend.sessions import CVSession as _CVSession

_EVAL = {
    "candidate_name": "Jane", "overall_score": 72, "approved": False,
    "formatting_issues": [], "keywords_found": [], "keywords_missing": [],
    "recommendations": ["Add metrics"], "summary": "ok",
    "strengths": ["Clear structure"], "weaknesses": ["No metrics"],
}


def test_resume_evaluation_has_strengths_and_weaknesses():
    fields = ResumeEvaluation.model_fields
    assert "strengths" in fields and "weaknesses" in fields


def _session_token():
    token = str(_uuid.uuid4())
    _sessions.cv_sessions[token] = _CVSession(
        token=token, cv_text="Jane CV " * 20, filename="cv.pdf", uploaded_at=_dt.now(_tz.utc)
    )
    return token


def test_evaluate_saves_evaluation_when_logged_in(client, as_user):
    token = _session_token()
    with _patch("src.routes.evaluate.evaluate_cv", return_value=_EVAL), \
         _patch("src.routes.evaluate.save_evaluation") as save:
        res = client.post("/evaluate", headers={"X-CV-Session-Token": token}, data={})
    assert res.status_code == 200
    assert res.json()["strengths"] == ["Clear structure"]
    save.assert_called_once_with(as_user, _EVAL)


def test_evaluate_does_not_save_when_anonymous(client):
    token = _session_token()
    with _patch("src.routes.evaluate.evaluate_cv", return_value=_EVAL), \
         _patch("src.routes.evaluate.save_evaluation") as save:
        res = client.post("/evaluate", headers={"X-CV-Session-Token": token}, data={})
    assert res.status_code == 200
    save.assert_not_called()


def test_evaluate_uses_base_cv_when_logged_in_without_input(client, as_user):
    base = {"cv_text": "Base CV text " * 20, "filename": "base.pdf"}
    with _patch("src.routes.evaluate.get_cv", return_value=base), \
         _patch("src.routes.evaluate.evaluate_cv", return_value=_EVAL) as ev, \
         _patch("src.routes.evaluate.save_evaluation"):
        res = client.post("/evaluate", data={})
    assert res.status_code == 200
    assert ev.call_args.args[0] == base["cv_text"]


def test_evaluate_without_any_cv_is_400(client, as_user):
    with _patch("src.routes.evaluate.get_cv", return_value=None):
        assert client.post("/evaluate", data={}).status_code == 400
