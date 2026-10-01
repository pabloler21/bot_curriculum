"""Rutas de historial (My Jobs)."""
import uuid
from unittest.mock import patch

from tests.test_improve import IMPROVED

GEN_ID = str(uuid.uuid4())


def test_history_requires_auth(client):
    assert client.get("/history").status_code == 401


def test_list(client, as_user):
    rows = [{"id": GEN_ID, "kind": "both", "job_title": "Dev", "company": None,
             "job_url": None, "created_at": "2026-09-30T00:00:00Z"}]
    with patch("src.routes.history.history.list_for", return_value=rows) as lf:
        assert client.get("/history").json() == rows
    lf.assert_called_once_with(as_user)


def test_detail_404_for_other_users_rows(client, as_user):
    with patch("src.routes.history.history.get", return_value=None) as g:
        assert client.get(f"/history/{GEN_ID}").status_code == 404
    g.assert_called_once_with(as_user, GEN_ID)


def test_detail_rejects_bad_id(client, as_user):
    assert client.get("/history/not-a-uuid").status_code == 400


def test_pdf_is_regenerated_from_result(client, as_user):
    row = {"id": GEN_ID, "kind": "cv", "result": {"adapted_schema": IMPROVED.model_dump(mode="json")}}
    with patch("src.routes.history.history.get", return_value=row), \
         patch("src.routes.history.render_pdf", return_value=b"%PDF-1.4") as rp:
        res = client.get(f"/history/{GEN_ID}/pdf")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert rp.call_args.args[0].summary == IMPROVED.summary


def test_pdf_404_for_cover_only(client, as_user):
    row = {"id": GEN_ID, "kind": "cover", "result": {"adapted_schema": None, "cover_letter": "Dear"}}
    with patch("src.routes.history.history.get", return_value=row):
        assert client.get(f"/history/{GEN_ID}/pdf").status_code == 404
