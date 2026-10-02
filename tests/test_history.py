"""backend/history.py — generaciones por usuario (My Jobs)."""
from unittest.mock import MagicMock, patch

from backend import history

UID = "u-1"


def test_job_title_is_first_non_empty_line_truncated():
    assert history.job_title_from("\n\n  Senior Python Engineer  \nWe need...") == "Senior Python Engineer"
    assert len(history.job_title_from("x" * 500)) == 120
    assert history.job_title_from("") is None


def test_add_inserts_row_and_returns_id():
    db = MagicMock()
    db.table.return_value.insert.return_value.execute.return_value = MagicMock(data=[{"id": "g-1"}])
    with patch("backend.history._db", db):
        gen_id = history.add(UID, "both", "Senior Dev\nmore", "https://x.io/1", {"run_id": "r"})
    assert gen_id == "g-1"
    row = db.table.return_value.insert.call_args.args[0]
    assert row == {"user_id": UID, "kind": "both", "job_title": "Senior Dev", "company": None,
                   "job_description": "Senior Dev\nmore", "job_url": "https://x.io/1", "result": {"run_id": "r"}}
    db.table.assert_called_with("generations")


def test_list_for_filters_by_user_newest_first():
    db = MagicMock()
    chain = db.table.return_value.select.return_value.eq.return_value.order.return_value.limit.return_value
    chain.execute.return_value = MagicMock(data=[{"id": "g-1"}])
    with patch("backend.history._db", db):
        assert history.list_for(UID) == [{"id": "g-1"}]
    db.table.return_value.select.return_value.eq.assert_called_once_with("user_id", UID)
    db.table.return_value.select.return_value.eq.return_value.order.assert_called_once_with("created_at", desc=True)


def test_get_filters_by_id_and_user():
    db = MagicMock()
    eq2 = db.table.return_value.select.return_value.eq.return_value.eq
    eq2.return_value.execute.return_value = MagicMock(data=[])
    with patch("backend.history._db", db):
        assert history.get(UID, "g-other") is None
    db.table.return_value.select.return_value.eq.assert_called_once_with("id", "g-other")
    eq2.assert_called_once_with("user_id", UID)


def test_noop_without_db():
    with patch("backend.history._db", None):
        assert history.add(UID, "cv", "jd", None, {}) is None
        assert history.list_for(UID) == []
        assert history.get(UID, "g") is None
        history.delete_all(UID)
