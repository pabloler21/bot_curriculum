"""POST /improve — aplica las recomendaciones del evaluator al CV base."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.schemas import CVSchema, WorkExperience

ORIGINAL = CVSchema(candidate_name="Jane", experiences=[WorkExperience(company="Acme", role="Dev",
                    start_date="2020", bullets=["Built APIs"])], skills=["Python"], education=[])
IMPROVED = ORIGINAL.model_copy(update={"summary": "Backend engineer focused on APIs"})
BASE = {"cv_text": "Jane Dev Acme Built APIs " * 10, "filename": "cv.pdf"}
BODY = {"recommendations": ["Add a summary", "Quantify impact"]}


@pytest.fixture
def pipeline_ok():
    with patch("src.routes.improve.extract_schema", AsyncMock(return_value=ORIGINAL)) as ex, \
         patch("src.routes.improve.improve_cv", AsyncMock(return_value=IMPROVED)) as imp, \
         patch("src.routes.improve.validate_adaptation", MagicMock(return_value=[])), \
         patch("src.routes.improve.render_pdf", MagicMock(return_value=b"%PDF")), \
         patch("src.routes.improve.ensure_user"), \
         patch("src.routes.improve.decrement") as dec, \
         patch("src.routes.improve.restore") as rest, \
         patch("src.routes.improve.save_cv") as save, \
         patch("src.routes.improve.history") as hist:
        hist.add.return_value = "hist-id"
        yield {"extract": ex, "improve": imp, "decrement": dec, "restore": rest, "save": save, "history": hist}


def test_requires_auth(client):
    assert client.post("/improve", json=BODY).status_code == 401


def test_improve_without_base_cv_is_400(client, as_user, pipeline_ok):
    with patch("src.routes.improve.get_cv", return_value=None):
        res = client.post("/improve", json=BODY)
    assert res.status_code == 400
    pipeline_ok["decrement"].assert_not_called()


def test_improve_happy_path(client, as_user, pipeline_ok):
    with patch("src.routes.improve.get_cv", return_value=BASE):
        res = client.post("/improve", json=BODY)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "completed"
    assert data["adapted_schema"]["summary"] == "Backend engineer focused on APIs"
    assert data["history_id"] == "hist-id"
    pipeline_ok["decrement"].assert_called_once_with(as_user, 1)
    pipeline_ok["improve"].assert_awaited_once_with(ORIGINAL, BODY["recommendations"])
    args = pipeline_ok["save"].call_args.args
    assert args[0] == as_user and args[2] == "cv.pdf" and args[3] == "improved"
    assert "Backend engineer focused on APIs" in args[1]
    assert pipeline_ok["history"].add.call_args.args[1] == "improve"


def test_save_failure_restores_credit(client, as_user, pipeline_ok):
    pipeline_ok["save"].side_effect = RuntimeError("db down")
    with patch("src.routes.improve.get_cv", return_value=BASE):
        res = client.post("/improve", json=BODY)
    assert res.status_code == 500
    pipeline_ok["restore"].assert_called_once_with(as_user, 1)


def test_improve_failure_restores_credit_and_keeps_base_cv(client, as_user, pipeline_ok):
    pipeline_ok["improve"].side_effect = RuntimeError("llm down")
    with patch("src.routes.improve.get_cv", return_value=BASE):
        res = client.post("/improve", json=BODY)
    assert res.status_code == 500
    pipeline_ok["restore"].assert_called_once_with(as_user, 1)
    pipeline_ok["save"].assert_not_called()


def test_no_credits_is_402(client, as_user, pipeline_ok):
    from backend.credits import InsufficientCredits
    pipeline_ok["decrement"].side_effect = InsufficientCredits("none")
    with patch("src.routes.improve.get_cv", return_value=BASE):
        res = client.post("/improve", json=BODY)
    assert res.status_code == 402
    assert res.json()["code"] == "no_credits"


@pytest.mark.parametrize("recs", [[], ["x"] * 21, ["x" * 501]])
def test_recommendation_limits(client, as_user, recs):
    assert client.post("/improve", json={"recommendations": recs}).status_code == 422


def test_flagged_bullets_make_it_partial(client, as_user, pipeline_ok):
    with patch("src.routes.improve.get_cv", return_value=BASE), \
         patch("src.routes.improve.validate_adaptation", MagicMock(return_value=["Built APIs"])):
        data = client.post("/improve", json=BODY).json()
    assert data["status"] == "partial"
    assert data["suspicious_bullets"] == ["Built APIs"]
    pipeline_ok["save"].assert_not_called()
    pipeline_ok["history"].add.assert_called_once()
