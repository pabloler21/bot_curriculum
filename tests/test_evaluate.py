import io
from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
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


def test_resume_evaluation_has_target_role():
    assert "target_role" in ResumeEvaluation.model_fields


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


def test_evaluate_returns_and_saves_the_prioritized_evaluation(client, as_user):
    prioritized = {**_EVAL, "recommendations_priority": ["essential"]}
    token = _session_token()
    with _patch("src.routes.evaluate.evaluate_cv", return_value=_EVAL), \
         _patch("src.routes.evaluate.prioritize", new_callable=AsyncMock, return_value=prioritized) as prio, \
         _patch("src.routes.evaluate.save_evaluation") as save:
        res = client.post("/evaluate", headers={"X-CV-Session-Token": token}, data={})
    assert res.json()["recommendations_priority"] == ["essential"]
    save.assert_called_once_with(as_user, prioritized)
    assert prio.await_args.args[0] == _EVAL


def test_evaluate_passes_the_job_context_to_prioritize():
    jobs_cache["data"] = ([make_job("42")], datetime.now(timezone.utc))
    with patch("src.routes.evaluate.evaluate_cv", return_value=MOCK_EVAL), \
         patch("src.routes.evaluate.extract_text", return_value="My Python CV"), \
         patch("src.routes.evaluate.prioritize", new_callable=AsyncMock, return_value=MOCK_EVAL) as prio:
        eval_client.post("/evaluate", data={"job_id": "42"},
                         files={"file": ("cv.pdf", io.BytesIO(b"data"), "application/pdf")})
    assert "Python FastAPI developer" in prio.await_args.args[1]


# ── Task 4.22: el análisis sale en el idioma de la página ─────────────────────
from backend.evaluator import EvaluationText, evaluate_cv, translate_evaluation


def _fake_evaluation(**overrides) -> ResumeEvaluation:
    fields = {
        "candidate_name": "Jane", "target_role": "Data Analyst", "overall_score": 70, "approved": False,
        "formatting_issues": [], "keywords_found": [], "keywords_missing": [], "recommendations": [],
        "strengths": [], "weaknesses": [], "summary": "ok",
    }
    return ResumeEvaluation(**{**fields, **overrides})


def test_evaluate_passes_the_page_language(client):
    token = _session_token()
    with _patch("src.routes.evaluate.evaluate_cv", return_value=_EVAL) as ev:
        res = client.post("/evaluate", headers={"X-CV-Session-Token": token}, data={"output_language": "es"})
    assert res.status_code == 200
    assert ev.call_args.kwargs["output_language"] == "es"


def test_evaluate_defaults_to_english(client):
    token = _session_token()
    with _patch("src.routes.evaluate.evaluate_cv", return_value=_EVAL) as ev:
        client.post("/evaluate", headers={"X-CV-Session-Token": token}, data={})
    assert ev.call_args.kwargs["output_language"] == "en"


def test_evaluate_rejects_an_unknown_language(client):
    token = _session_token()
    res = client.post("/evaluate", headers={"X-CV-Session-Token": token}, data={"output_language": "fr"})
    assert res.status_code == 422


def test_evaluate_cv_asks_for_the_language_and_tags_the_result():
    from backend import evaluator
    assert "output_language" in evaluator.prompt_template.input_variables
    with _patch("backend.evaluator.chain") as chain:
        chain.invoke.return_value = _fake_evaluation()
        out = evaluate_cv("My CV", output_language="es")
    assert chain.invoke.call_args.args[0]["output_language"] == "es"
    assert out["language"] == "es"
    assert out["evaluated_at"]  # empareja una evaluación con su traducción

_SAVED = {
    **_EVAL, "keywords_missing": ["Docker"], "keywords_missing_priority": ["essential"],
    "recommendations_priority": ["important"], "formatting_issues": ["Odd date"],
    "language": "en", "evaluated_at": "2026-10-20T10:00:00+00:00",
}
_SPANISH = EvaluationText(
    summary="bien", keywords_found=[], keywords_missing=["Docker"], recommendations=["Agregá métricas"],
    strengths=["Estructura clara"], weaknesses=["Sin métricas"], formatting_issues=["Fecha rara"],
)


def test_translate_evaluation_translates_the_text_and_keeps_the_rest():
    with _patch("backend.evaluator.translate_chain") as chain:
        chain.invoke.return_value = _SPANISH
        out = translate_evaluation(_SAVED, "es")
    assert chain.invoke.call_args.args[0]["output_language"] == "es"
    assert out["recommendations"] == ["Agregá métricas"] and out["summary"] == "bien"
    # Lo que no es texto no cambia: mismo puntaje, misma prioridad, misma evaluación.
    assert out["overall_score"] == 72
    assert out["recommendations_priority"] == ["important"]
    assert out["evaluated_at"] == _SAVED["evaluated_at"]
    assert out["language"] == "es"


def test_translate_evaluation_rejects_a_list_that_changed_length():
    # Las prioridades van en listas paralelas: una traducción con otro largo las desalinearía.
    with _patch("backend.evaluator.translate_chain") as chain:
        chain.invoke.return_value = _SPANISH.model_copy(update={"recommendations": ["Uno", "Dos"]})
        with pytest.raises(ValueError):
            translate_evaluation(_SAVED, "es")


def test_translate_route_returns_the_translated_evaluation(client):
    translated = {**_SAVED, "language": "es"}
    with _patch("src.routes.evaluate.translate_evaluation", return_value=translated) as tr:
        res = client.post("/evaluate/translate", json={"evaluation": _SAVED, "output_language": "es"})
    assert res.status_code == 200
    assert res.json()["language"] == "es"
    sent, lang = tr.call_args.args
    assert lang == "es" and sent["recommendations"] == _SAVED["recommendations"]


def test_translate_route_saves_the_translation_when_logged_in(client, as_user):
    translated = {**_SAVED, "language": "es"}
    with _patch("src.routes.evaluate.translate_evaluation", return_value=translated), \
         _patch("src.routes.evaluate.save_evaluation") as save:
        client.post("/evaluate/translate", json={"evaluation": _SAVED, "output_language": "es"})
    save.assert_called_once_with(as_user, translated)


def test_translate_route_does_not_save_when_anonymous(client):
    with _patch("src.routes.evaluate.translate_evaluation", return_value=_SAVED), \
         _patch("src.routes.evaluate.save_evaluation") as save:
        client.post("/evaluate/translate", json={"evaluation": _SAVED, "output_language": "es"})
    save.assert_not_called()


def test_translate_route_rejects_an_unknown_language(client):
    res = client.post("/evaluate/translate", json={"evaluation": _SAVED, "output_language": "fr"})
    assert res.status_code == 422


def test_translate_route_rejects_an_oversized_evaluation(client):
    # Es anónimo y llama al modelo: no puede ser un traductor gratis de textos arbitrarios.
    huge = {**_SAVED, "recommendations": ["x" * 50] * 200}
    res = client.post("/evaluate/translate", json={"evaluation": huge, "output_language": "es"})
    assert res.status_code == 422


def test_translate_route_is_502_when_the_translation_fails(client):
    with _patch("src.routes.evaluate.translate_evaluation", side_effect=ValueError("length")):
        res = client.post("/evaluate/translate", json={"evaluation": _SAVED, "output_language": "es"})
    assert res.status_code == 502
