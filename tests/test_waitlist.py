# tests/test_waitlist.py
"""Tests for POST /waitlist endpoint."""
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def _sb_ok():
    mock = MagicMock()
    mock.table.return_value.upsert.return_value.execute.return_value = MagicMock(data=[])
    return mock


class TestPostWaitlist:
    def test_valid_email_returns_201(self):
        with patch("src.routes.waitlist._supabase", _sb_ok()):
            response = client.post("/waitlist", json={"email": "test@example.com"})
        assert response.status_code == 201
        assert response.json() == {"status": "ok"}

    def test_invalid_email_returns_422(self):
        response = client.post("/waitlist", json={"email": "not-an-email"})
        assert response.status_code == 422

    def test_email_is_lowercased(self):
        mock = _sb_ok()
        with patch("src.routes.waitlist._supabase", mock):
            client.post("/waitlist", json={"email": "Test@Example.COM"})
        call_args = mock.table.return_value.upsert.call_args[0][0]
        assert call_args["email"] == "test@example.com"

    def test_upsert_called_with_correct_args(self):
        mock = _sb_ok()
        with patch("src.routes.waitlist._supabase", mock):
            client.post("/waitlist", json={"email": "user@test.com"})
        mock.table.assert_called_with("waitlist")
        mock.table.return_value.upsert.assert_called_once()
        call_kwargs = mock.table.return_value.upsert.call_args[1]
        assert call_kwargs["on_conflict"] == "email"
        assert call_kwargs["ignore_duplicates"] is True

    def test_supabase_unavailable_still_returns_201(self):
        with patch("src.routes.waitlist._supabase", None):
            response = client.post("/waitlist", json={"email": "user@test.com"})
        assert response.status_code == 201

    def test_authenticated_user_id_stored(self):
        mock = _sb_ok()
        fake_user_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        fake_user = MagicMock()
        fake_user.id = fake_user_id
        fake_response = MagicMock()
        fake_response.user = fake_user
        auth_mock = MagicMock()
        auth_mock.auth.get_user.return_value = fake_response

        with patch("src.routes.waitlist._supabase", mock), \
             patch("backend.auth._supabase", auth_mock):
            client.post(
                "/waitlist",
                json={"email": "user@test.com"},
                headers={"Authorization": "Bearer valid.token"},
            )
        call_args = mock.table.return_value.upsert.call_args[0][0]
        assert call_args["user_id"] == fake_user_id

    def test_supabase_error_still_returns_201(self):
        mock = _sb_ok()
        mock.table.return_value.upsert.return_value.execute.side_effect = Exception("db error")
        with patch("src.routes.waitlist._supabase", mock):
            response = client.post("/waitlist", json={"email": "user@test.com"})
        assert response.status_code == 201
