# tests/test_auth.py
"""Tests for backend/auth.py — JWT validation dependency."""
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from src.main import app
from src.routes.adapt import limiter as adapt_limiter

client = TestClient(app)

_JD = "We are looking for a Python developer with FastAPI and PostgreSQL experience"


def _make_request(token: str | None = None) -> dict:
    """POST /adapt and return the captured user_id by inspecting pipeline call."""
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    # We don't care about the pipeline result here — just that the route
    # resolves the dependency correctly without crashing.
    return headers


class TestGetCurrentUser:
    """Unit tests for the get_current_user dependency."""

    def test_no_auth_header_returns_none(self):
        from fastapi import Request

        from backend.auth import get_current_user

        mock_request = MagicMock(spec=Request)
        mock_request.headers = {}
        assert get_current_user(mock_request) is None

    def test_invalid_jwt_returns_none(self):
        from fastapi import Request

        from backend.auth import get_current_user

        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"Authorization": "Bearer invalid.token.here"}

        with patch("backend.auth._supabase") as mock_sb:
            mock_sb.auth.get_user.side_effect = Exception("invalid JWT")
            result = get_current_user(mock_request)

        assert result is None

    def test_valid_jwt_returns_user_id(self):
        from fastapi import Request

        from backend.auth import get_current_user

        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"Authorization": "Bearer valid.token.here"}

        fake_user = MagicMock()
        fake_user.id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        fake_response = MagicMock()
        fake_response.user = fake_user

        with patch("backend.auth._supabase") as mock_sb:
            mock_sb.auth.get_user.return_value = fake_response
            result = get_current_user(mock_request)

        assert result == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    def test_missing_bearer_prefix_returns_none(self):
        from fastapi import Request

        from backend.auth import get_current_user

        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"Authorization": "Token some-token"}
        assert get_current_user(mock_request) is None

    def test_no_supabase_client_returns_none(self):
        from fastapi import Request

        from backend.auth import get_current_user

        mock_request = MagicMock(spec=Request)
        mock_request.headers = {"Authorization": "Bearer valid.token"}

        with patch("backend.auth._supabase", None):
            result = get_current_user(mock_request)

        assert result is None


class TestAdaptRouteWithAuth:
    """/adapt requires a valid JWT — returns 401 otherwise."""

    def setup_method(self):
        app.state.limiter.reset()
        adapt_limiter.reset()

    def test_adapt_without_auth_header_returns_401(self):
        response = client.post(
            "/adapt",
            data={"job_description": _JD},
            files={"file": ("cv.pdf", b"fake", "application/pdf")},
        )
        assert response.status_code == 401

    def test_adapt_with_invalid_jwt_returns_401(self):
        with patch("backend.auth._supabase") as mock_sb:
            mock_sb.auth.get_user.side_effect = Exception("bad token")
            response = client.post(
                "/adapt",
                headers={"Authorization": "Bearer bad.token"},
                data={"job_description": _JD},
                files={"file": ("cv.pdf", b"fake", "application/pdf")},
            )
        assert response.status_code == 401

    def test_adapt_passes_user_id_to_pipeline(self):
        from unittest.mock import AsyncMock

        from backend.schemas import AdaptationResult, PipelineStatus

        result = AdaptationResult(
            run_id="aaaaaaaa-0000-0000-0000-000000000000",
            status=PipelineStatus.COMPLETED,
        )
        fake_user_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        fake_user = MagicMock()
        fake_user.id = fake_user_id
        fake_auth_response = MagicMock()
        fake_auth_response.user = fake_user

        _run_patch = patch("src.routes.adapt.run_pipeline", new_callable=AsyncMock, return_value=(result, None))
        with patch("src.routes.adapt.extract_text", return_value="x" * 150), \
             _run_patch as mock_pipeline, \
             patch("backend.auth._supabase") as mock_sb, \
             patch("src.routes.adapt.ensure_user"), \
             patch("src.routes.adapt.decrement"):
            mock_sb.auth.get_user.return_value = fake_auth_response
            client.post(
                "/adapt",
                headers={"Authorization": "Bearer valid.token"},
                data={"job_description": _JD},
                files={"file": ("cv.pdf", b"fake", "application/pdf")},
            )

        call_kwargs = mock_pipeline.call_args.kwargs
        assert call_kwargs.get("user_id") == fake_user_id


class TestQueClaveUsaElCliente:
    """El cliente de auth no debe depender de SUPABASE_KEY.

    SUPABASE_KEY está reservada para sessions.py, que la usa para decidir si los
    CVs van a Postgres. Producción la deja sin setear a propósito porque la tabla
    cv_sessions tiene RLS deshabilitada. Cuando auth.py dependía de esa misma
    variable, esa omisión deliberada dejaba _supabase en None y get_current_user
    devolvía None siempre: nadie podía autenticarse nunca.

    Para validar un JWT alcanza la anon key, que además ya se publica en /config.
    """

    def _recargar_auth(self, monkeypatch, **env):
        import importlib

        from backend import auth

        for nombre in ("SUPABASE_URL", "SUPABASE_KEY", "SUPABASE_ANON_KEY"):
            monkeypatch.delenv(nombre, raising=False)
        for nombre, valor in env.items():
            monkeypatch.setenv(nombre, valor)
        return importlib.reload(auth)

    def test_se_inicializa_solo_con_anon_key(self, monkeypatch):
        with patch("supabase.create_client", return_value=MagicMock()) as mock_create:
            auth = self._recargar_auth(
                monkeypatch,
                SUPABASE_URL="https://proyecto.supabase.co",
                SUPABASE_ANON_KEY="anon-123",
            )
        assert auth._supabase is not None, (
            "sin SUPABASE_KEY el cliente quedó en None: nadie puede autenticarse"
        )
        mock_create.assert_called_once_with("https://proyecto.supabase.co", "anon-123")

    def test_sigue_andando_con_la_variable_vieja(self, monkeypatch):
        with patch("supabase.create_client", return_value=MagicMock()) as mock_create:
            auth = self._recargar_auth(
                monkeypatch,
                SUPABASE_URL="https://proyecto.supabase.co",
                SUPABASE_KEY="service-456",
            )
        assert auth._supabase is not None
        mock_create.assert_called_once_with("https://proyecto.supabase.co", "service-456")

    def test_sin_ninguna_clave_queda_en_none(self, monkeypatch):
        auth = self._recargar_auth(monkeypatch, SUPABASE_URL="https://proyecto.supabase.co")
        assert auth._supabase is None
