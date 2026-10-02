"""DELETE /account — borra todos los datos del usuario y su cuenta de Supabase Auth."""
from unittest.mock import MagicMock, call, patch


def test_requires_auth(client):
    assert client.delete("/account").status_code == 401


def test_503_without_db(client, as_user):
    with patch("src.routes.account.db.client", None):
        assert client.delete("/account").status_code == 503


def test_deletes_tables_then_auth_user_then_credits(client, as_user):
    db = MagicMock()
    with patch("src.routes.account.db.client", db):
        res = client.delete("/account")
    assert res.status_code == 204
    tables = [c.args[0] for c in db.table.call_args_list]
    assert tables == ["user_cvs", "generations", "waitlist", "credits"]
    for c in db.table.return_value.delete.return_value.eq.call_args_list:
        assert c.args == ("user_id", as_user)
    db.auth.admin.delete_user.assert_called_once_with(as_user)
    # credits va después de delete_user: si el delete de auth falla, ensure_user no debe recrear créditos
    names = [c[0] for c in db.mock_calls]
    first_credits = [i for i, c in enumerate(db.mock_calls) if c == call.table("credits")][0]
    assert names.index("auth.admin.delete_user") < first_credits
