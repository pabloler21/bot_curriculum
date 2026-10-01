"""backend/db.py — cliente con service role compartido por el backend."""
import importlib


def test_client_is_none_without_service_role_key(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setattr("dotenv.load_dotenv", lambda *a, **k: None)
    import backend.db as db
    db = importlib.reload(db)
    assert db.client is None


def test_credits_uses_the_shared_client():
    import backend.credits as credits
    import backend.db as db
    assert credits._supabase is db.client
