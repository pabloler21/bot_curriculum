# tests/test_adapt_route.py
"""Tests for POST /adapt and GET /adapt/{run_id}/pdf endpoints."""
import io
import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.job_fetch import JobFetchError
from backend.schemas import AdaptationResult, CVSchema, PipelineStatus, WorkExperience
from src.main import app
from src.routes.adapt import limiter as adapt_limiter

client = TestClient(app)

# Reusable CV text ≥100 chars to pass the length validation in /adapt
_CV_TEXT = (
    "Jane Doe Senior Python Engineer. 5 years FastAPI PostgreSQL Docker AWS "
    "microservices backend development. Buenos Aires Argentina."
)


@pytest.fixture(autouse=True)
def reset_limiters():
    """Reset all rate limiters before every test in this module."""
    app.state.limiter.reset()
    adapt_limiter.reset()
    yield


@pytest.fixture(autouse=True)
def mock_auth():
    """Provide a default authenticated user so /adapt tests don't hit 401."""
    with patch("backend.auth.get_current_user", return_value="test-user-id"):
        yield


@pytest.fixture(autouse=True)
def mock_credits():
    """Mock credit functions so tests don't hit Supabase."""
    with patch("src.routes.adapt.ensure_user"), \
         patch("src.routes.adapt.decrement"), \
         patch("src.routes.adapt.restore"):
        yield


def make_adapted_schema() -> CVSchema:
    return CVSchema(
        candidate_name="Jane Doe",
        experiences=[
            WorkExperience(
                company="Acme",
                role="Dev",
                start_date="2020",
                bullets=["Built FastAPI API"],
            )
        ],
        skills=["Python"],
        education=[],
    )


def make_adaptation_result(status=PipelineStatus.COMPLETED) -> AdaptationResult:
    return AdaptationResult(
        run_id=str(uuid.uuid4()),
        status=status,
        adapted_schema=make_adapted_schema(),
        gaps=[],
        cover_letter="Dear Hiring Manager...",
    )


class TestPostAdapt:
    def test_missing_file_and_no_session_returns_400(self):
        response = client.post(
            "/adapt",
            data={"job_input": "We need a Python developer with FastAPI experience and more text here."},
        )
        assert response.status_code == 400
        assert "Upload your CV first" in response.json()["detail"]

    def test_too_short_jd_returns_422(self):
        response = client.post(
            "/adapt",
            data={"job_input": "Too short"},
            files={"file": ("cv.pdf", io.BytesIO(b"fake pdf"), "application/pdf")},
        )
        assert response.status_code == 422

    def test_file_too_large_returns_413(self):
        big_file = b"x" * (6 * 1024 * 1024)  # 6 MB
        with patch("src.routes.cv_input.extract_text", return_value="some text"):
            response = client.post(
                "/adapt",
                data={
                    "job_input": "A" * 200,
                    "output_language": "en",
                },
                files={"file": ("cv.pdf", io.BytesIO(big_file), "application/pdf")},
            )
        assert response.status_code == 413

    def test_invalid_session_token_format_returns_400(self):
        response = client.post(
            "/adapt",
            data={
                "job_input": "We need a Python developer with FastAPI experience and Docker knowledge.",
                "output_language": "en",
            },
            headers={"X-CV-Session-Token": "not-a-uuid"},
        )
        assert response.status_code == 400

    def test_expired_session_returns_400(self):
        fake_token = str(uuid.uuid4())
        response = client.post(
            "/adapt",
            data={
                "job_input": "Python developer needed with experience in APIs and microservices.",
                "output_language": "en",
            },
            headers={"X-CV-Session-Token": fake_token},
        )
        assert response.status_code == 400
        assert "Session not found" in response.json()["detail"]

    def test_successful_adapt_with_file_returns_result(self):
        jd = "We are looking for a Python developer with 3+ years FastAPI and PostgreSQL experience."
        result = make_adaptation_result()
        pdf_bytes = b"%PDF-1.4 fake pdf content"
        cv_text = _CV_TEXT

        with patch("src.routes.cv_input.extract_text", return_value=cv_text), \
             patch("src.routes.adapt.run_pipeline", new_callable=AsyncMock, return_value=(result, pdf_bytes)):
            response = client.post(
                "/adapt",
                data={"job_input": jd, "output_language": "en"},
                files={"file": ("cv.pdf", io.BytesIO(b"fake pdf"), "application/pdf")},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["run_id"] == result.run_id
        assert data["cover_letter"] is not None

    def test_pipeline_failed_extract_returns_200_with_error_status(self):
        """The route returns 200 with failure status in body, not HTTP 500."""
        jd = "Senior Python developer needed for our fintech startup with Docker and Kubernetes."
        result = AdaptationResult(
            run_id=str(uuid.uuid4()),
            status=PipelineStatus.FAILED_EXTRACT,
            error_message="PDF is image-only",
        )
        cv_text = _CV_TEXT

        with patch("src.routes.cv_input.extract_text", return_value=cv_text), \
             patch("src.routes.adapt.run_pipeline", new_callable=AsyncMock, return_value=(result, None)):
            response = client.post(
                "/adapt",
                data={"job_input": jd, "output_language": "en"},
                files={"file": ("cv.pdf", io.BytesIO(b"fake"), "application/pdf")},
            )

        assert response.status_code == 200
        assert response.json()["status"] == "failed_extract"

    def test_language_es_is_accepted(self):
        jd = "Buscamos desarrollador Python con experiencia en FastAPI y microservicios backend."
        result = make_adaptation_result()
        cv_text = _CV_TEXT

        mock_pipeline_patch = patch(
            "src.routes.adapt.run_pipeline", new_callable=AsyncMock, return_value=(result, None)
        )
        with patch("src.routes.cv_input.extract_text", return_value=cv_text), \
             mock_pipeline_patch as mock_pipeline:
            response = client.post(
                "/adapt",
                data={"job_input": jd, "output_language": "es"},
                files={"file": ("cv.pdf", io.BytesIO(b"fake"), "application/pdf")},
            )

        assert response.status_code == 200
        # Verify language was passed to pipeline
        call_kwargs = mock_pipeline.call_args.kwargs
        assert call_kwargs.get("output_language") == "es"


class TestCredits:
    """Credit gate on POST /adapt."""

    _JD = "We need a senior Python developer with FastAPI and PostgreSQL experience."

    def test_returns_402_when_no_credits(self):
        from backend.credits import InsufficientCredits
        with patch("src.routes.cv_input.extract_text", return_value=_CV_TEXT), \
             patch("src.routes.adapt.ensure_user"), \
             patch("src.routes.adapt.decrement", side_effect=InsufficientCredits):
            response = client.post(
                "/adapt",
                data={"job_input": self._JD},
                files={"file": ("cv.pdf", io.BytesIO(b"fake"), "application/pdf")},
            )
        assert response.status_code == 402
        assert response.json()["code"] == "no_credits"

    def test_decrement_called_before_pipeline(self):
        result = make_adaptation_result()
        with patch("src.routes.cv_input.extract_text", return_value=_CV_TEXT), \
             patch("src.routes.adapt.ensure_user"), \
             patch("src.routes.adapt.decrement") as mock_dec, \
             patch("src.routes.adapt.run_pipeline", new_callable=AsyncMock, return_value=(result, None)):
            client.post(
                "/adapt",
                data={"job_input": self._JD},
                files={"file": ("cv.pdf", io.BytesIO(b"fake"), "application/pdf")},
            )
        mock_dec.assert_called_once_with("test-user-id", 2)

    def test_restore_called_on_pipeline_failure(self):
        with patch("src.routes.cv_input.extract_text", return_value=_CV_TEXT), \
             patch("src.routes.adapt.ensure_user"), \
             patch("src.routes.adapt.decrement"), \
             patch("src.routes.adapt.restore") as mock_restore, \
             patch("src.routes.adapt.run_pipeline", new_callable=AsyncMock, side_effect=Exception("boom")):
            client.post(
                "/adapt",
                data={"job_input": self._JD},
                files={"file": ("cv.pdf", io.BytesIO(b"fake"), "application/pdf")},
            )
        mock_restore.assert_called_once_with("test-user-id", 2)


class TestDownloadPdf:
    def test_invalid_run_id_format_returns_400(self):
        response = client.get("/adapt/not-a-uuid/pdf")
        assert response.status_code == 400

    def test_unknown_run_id_returns_404(self):
        response = client.get(f"/adapt/{uuid.uuid4()}/pdf")
        assert response.status_code == 404

    def test_pdf_downloadable_after_successful_adapt(self):
        jd = "Senior Python developer with FastAPI, PostgreSQL, and Docker experience needed."
        pdf_bytes = b"%PDF-1.4 real content here"
        result = make_adaptation_result()
        cv_text = _CV_TEXT

        with patch("src.routes.cv_input.extract_text", return_value=cv_text), \
             patch("src.routes.adapt.run_pipeline", new_callable=AsyncMock, return_value=(result, pdf_bytes)):
            adapt_res = client.post(
                "/adapt",
                data={"job_input": jd, "output_language": "en"},
                files={"file": ("cv.pdf", io.BytesIO(b"fake"), "application/pdf")},
            )

        run_id = adapt_res.json()["run_id"]
        pdf_res = client.get(f"/adapt/{run_id}/pdf")

        assert pdf_res.status_code == 200
        assert pdf_res.headers["content-type"] == "application/pdf"
        assert pdf_res.content == pdf_bytes

    def test_no_pdf_if_pipeline_returned_none(self):
        """If pipeline returned no pdf_bytes, 404 on download."""
        jd = "Senior Python developer needed with FastAPI and PostgreSQL and AWS experience."
        result = make_adaptation_result()
        cv_text = _CV_TEXT

        with patch("src.routes.cv_input.extract_text", return_value=cv_text), \
             patch("src.routes.adapt.run_pipeline", new_callable=AsyncMock, return_value=(result, None)):
            adapt_res = client.post(
                "/adapt",
                data={"job_input": jd},
                files={"file": ("cv.pdf", io.BytesIO(b"fake"), "application/pdf")},
            )

        run_id = adapt_res.json()["run_id"]
        pdf_res = client.get(f"/adapt/{run_id}/pdf")
        assert pdf_res.status_code == 404


# ── Task 4.1: modos, job link, CV base, historial ─────────────────────────────
_JD = "We need a Python developer with FastAPI experience and Docker knowledge."
_HIST = {"add.return_value": "hist-id"}  # history.add devuelve un id serializable
_BASE = {"cv_text": _CV_TEXT, "filename": "base.pdf"}


def _ok_result(**kw):
    return AdaptationResult(run_id=str(uuid.uuid4()), status=PipelineStatus.COMPLETED,
                            adapted_schema=make_adapted_schema(), **kw)


@pytest.mark.parametrize("mode,cost", [("cv", 1), ("cover", 1), ("both", 2)])
def test_mode_charges_its_cost(mode, cost):
    with patch("src.routes.adapt.get_cv", return_value=_BASE), \
         patch("src.routes.adapt.run_pipeline", AsyncMock(return_value=(_ok_result(), None))) as rp, \
         patch("src.routes.adapt.decrement") as dec, \
         patch("src.routes.adapt.history", **_HIST) as hist:
        res = client.post("/adapt", data={"job_input": _JD, "mode": mode})
    assert res.status_code == 200
    dec.assert_called_once_with("test-user-id", cost)
    assert rp.call_args.kwargs["mode"] == mode
    hist.add.assert_called_once()
    assert hist.add.call_args.args[1] == mode


def test_invalid_mode_is_422():
    assert client.post("/adapt", data={"job_input": _JD, "mode": "all"}).status_code == 422


def test_uses_base_cv_when_no_file_or_token():
    with patch("src.routes.adapt.get_cv", return_value=_BASE), \
         patch("src.routes.adapt.run_pipeline", AsyncMock(return_value=(_ok_result(), None))) as rp, \
         patch("src.routes.adapt.history", **_HIST):
        client.post("/adapt", data={"job_input": _JD, "mode": "cv"})
    assert rp.call_args.kwargs["cv_text"] == _CV_TEXT


def test_no_cv_anywhere_is_400_and_not_charged():
    with patch("src.routes.adapt.get_cv", return_value=None), \
         patch("src.routes.adapt.decrement") as dec:
        res = client.post("/adapt", data={"job_input": _JD, "mode": "cv"})
    assert res.status_code == 400
    assert "Upload your CV first" in res.json()["detail"]
    dec.assert_not_called()


def test_url_input_is_fetched_and_returned_as_job_description():
    fetched = "Senior Python Engineer. " * 20
    with patch("src.routes.adapt.get_cv", return_value=_BASE), \
         patch("src.routes.adapt.fetch_job_text", AsyncMock(return_value=fetched)) as fetch, \
         patch("src.routes.adapt.run_pipeline", AsyncMock(return_value=(_ok_result(), None))) as rp, \
         patch("src.routes.adapt.history", **_HIST) as hist:
        res = client.post("/adapt", data={"job_input": "https://jobs.example/1", "mode": "cv"})
    assert res.status_code == 200
    fetch.assert_awaited_once_with("https://jobs.example/1")
    assert rp.call_args.kwargs["job_description"] == fetched
    assert res.json()["job_description"] == fetched
    assert hist.add.call_args.args[3] == "https://jobs.example/1"


def test_url_fetch_failure_is_422_and_not_charged():
    with patch("src.routes.adapt.get_cv", return_value=_BASE), \
         patch("src.routes.adapt.fetch_job_text", AsyncMock(side_effect=JobFetchError("blocked"))), \
         patch("src.routes.adapt.decrement") as dec:
        res = client.post("/adapt", data={"job_input": "https://www.linkedin.com/jobs/1", "mode": "cv"})
    assert res.status_code == 422
    assert "paste the job description" in res.json()["detail"]
    dec.assert_not_called()


def test_short_text_input_is_422():
    with patch("src.routes.adapt.get_cv", return_value=_BASE):
        assert client.post("/adapt", data={"job_input": "Too short", "mode": "cv"}).status_code == 422


def test_failed_status_restores_cost_and_skips_history():
    failed = AdaptationResult(run_id=str(uuid.uuid4()), status=PipelineStatus.FAILED_EXTRACT, error_message="x")
    with patch("src.routes.adapt.get_cv", return_value=_BASE), \
         patch("src.routes.adapt.run_pipeline", AsyncMock(return_value=(failed, None))), \
         patch("src.routes.adapt.restore") as rest, \
         patch("src.routes.adapt.history", **_HIST) as hist:
        res = client.post("/adapt", data={"job_input": _JD, "mode": "both"})
    assert res.status_code == 200
    rest.assert_called_once_with("test-user-id", 2)
    hist.add.assert_not_called()


def test_pipeline_exception_restores_cost():
    with patch("src.routes.adapt.get_cv", return_value=_BASE), \
         patch("src.routes.adapt.run_pipeline", AsyncMock(side_effect=RuntimeError("boom"))), \
         patch("src.routes.adapt.restore") as rest:
        res = client.post("/adapt", data={"job_input": _JD, "mode": "cover"})
    assert res.status_code == 500
    rest.assert_called_once_with("test-user-id", 1)


def test_history_failure_does_not_break_response():
    with patch("src.routes.adapt.get_cv", return_value=_BASE), \
         patch("src.routes.adapt.run_pipeline", AsyncMock(return_value=(_ok_result(), None))), \
         patch("src.routes.adapt.history", **_HIST) as hist:
        hist.add.side_effect = RuntimeError("db down")
        res = client.post("/adapt", data={"job_input": _JD, "mode": "cv"})
    assert res.status_code == 200
    assert res.json()["history_id"] is None
