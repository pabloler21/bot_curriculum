# tests/conftest.py
import pytest
from fastapi.testclient import TestClient

from backend import sessions
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
