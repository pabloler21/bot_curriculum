"""backend/user_cv.py — CV base por usuario."""
from unittest.mock import MagicMock, patch

from backend.schemas import CVSchema, Education, WorkExperience
from backend.user_cv import delete_cv, get_cv, save_cv, save_evaluation, schema_to_text

UID = "u-1"


def test_get_cv_returns_row():
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(
        data=[{"user_id": UID, "cv_text": "x"}]
    )
    with patch("backend.user_cv._db", db):
        assert get_cv(UID)["cv_text"] == "x"
    db.table.assert_called_with("user_cvs")


def test_get_cv_none_when_missing_or_no_db():
    db = MagicMock()
    db.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])
    with patch("backend.user_cv._db", db):
        assert get_cv(UID) is None
    with patch("backend.user_cv._db", None):
        assert get_cv(UID) is None


def test_save_cv_upserts_and_resets_evaluation():
    db = MagicMock()
    with patch("backend.user_cv._db", db):
        save_cv(UID, "cv text", "cv.pdf", "upload")
    row = db.table.return_value.upsert.call_args.args[0]
    assert row["user_id"] == UID
    assert row["cv_text"] == "cv text"
    assert row["source"] == "upload"
    assert row["last_evaluation"] is None
    assert db.table.return_value.upsert.call_args.kwargs["on_conflict"] == "user_id"


def test_save_evaluation_updates_only_that_user():
    db = MagicMock()
    with patch("backend.user_cv._db", db):
        save_evaluation(UID, {"overall_score": 80})
    db.table.return_value.update.assert_called_once_with({"last_evaluation": {"overall_score": 80}})
    db.table.return_value.update.return_value.eq.assert_called_once_with("user_id", UID)


def test_delete_cv_filters_by_user():
    db = MagicMock()
    with patch("backend.user_cv._db", db):
        delete_cv(UID)
    db.table.return_value.delete.return_value.eq.assert_called_once_with("user_id", UID)


def test_noop_without_db():
    with patch("backend.user_cv._db", None):
        save_cv(UID, "x", None, "upload")
        save_evaluation(UID, {})
        delete_cv(UID)


def test_schema_to_text_includes_every_section():
    schema = CVSchema(
        candidate_name="Jane Doe",
        contact_info="jane@example.com",
        summary="Backend engineer",
        experiences=[WorkExperience(company="Acme", role="Dev", start_date="2020", bullets=["Built APIs"])],
        skills=["Python", "FastAPI"],
        education=[Education(institution="UBA", degree="BSc")],
        languages=["English"],
        certifications=["AWS SAA"],
    )
    text = schema_to_text(schema)
    for fragment in ["Jane Doe", "jane@example.com", "Backend engineer", "Dev — Acme", "Built APIs",
                     "Python, FastAPI", "BSc", "UBA", "English", "AWS SAA"]:
        assert fragment in text
