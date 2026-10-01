# tests/conftest.py
import pytest
from fastapi.testclient import TestClient

from backend import sessions
from backend.auth import get_current_user, get_required_user
from src.main import app


@pytest.fixture(autouse=True)
def _in_memory_sessions(monkeypatch):
    """La suite nunca pega contra una Supabase real: sesiones siempre en memoria.

    Sin esto, tener SUPABASE_URL + SUPABASE_KEY en el entorno (CI) hace que
    backend/sessions.py use Postgres y los tests fallen si el proyecto está
    pausado o sin red.
    """
    monkeypatch.setattr(sessions, "_USE_SUPABASE", False)
    sessions.cv_sessions.clear()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _no_real_db(monkeypatch):
    """La suite nunca escribe en la Supabase real aunque el .env tenga la service role."""
    from backend import credits, db

    monkeypatch.setattr(db, "client", None)
    monkeypatch.setattr(credits, "_supabase", None)
    from backend import user_cv

    monkeypatch.setattr(user_cv, "_db", None)


USER_ID = "11111111-2222-3333-4444-555555555555"


@pytest.fixture
def as_user():
    """Autentica todas las requests como USER_ID sin tocar Supabase Auth."""
    # Referencias tomadas al importar: test_auth recarga backend.auth y las rutas conservan las viejas.
    app.dependency_overrides[get_required_user] = lambda: USER_ID
    app.dependency_overrides[get_current_user] = lambda: USER_ID
    yield USER_ID
    app.dependency_overrides.clear()
