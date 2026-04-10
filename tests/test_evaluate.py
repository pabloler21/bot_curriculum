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
