# tests/test_credits_route.py
"""Tests for GET /credits endpoint."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)

_USER_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


class TestGetCredits:
    def test_unauthenticated_returns_401(self):
        response = client.get("/credits")
        assert response.status_code == 401

    def test_authenticated_returns_balance(self):
        with patch("backend.auth.get_current_user", return_value=_USER_ID), \
             patch("src.routes.credits.get_balance", return_value=2):
            response = client.get(
                "/credits",
                headers={"Authorization": "Bearer valid.token"},
            )
        assert response.status_code == 200
        assert response.json() == {"balance": 2}

    def test_balance_reflects_actual_value(self):
        with patch("backend.auth.get_current_user", return_value=_USER_ID), \
             patch("src.routes.credits.get_balance", return_value=0):
            response = client.get(
                "/credits",
                headers={"Authorization": "Bearer valid.token"},
            )
        assert response.status_code == 200
        assert response.json()["balance"] == 0

    def test_get_balance_called_with_user_id(self):
        with patch("backend.auth.get_current_user", return_value=_USER_ID), \
             patch("src.routes.credits.get_balance", return_value=1) as mock_gb:
            client.get(
                "/credits",
                headers={"Authorization": "Bearer valid.token"},
            )
        mock_gb.assert_called_once_with(_USER_ID)
