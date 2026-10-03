# src/routes/account.py
"""DELETE /account — borra los datos del usuario y su usuario de Supabase Auth."""
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from backend import db
from backend.auth import RequiredUser

logger = logging.getLogger(__name__)
router = APIRouter()

_USER_TABLES = ("user_cvs", "generations", "waitlist")


@router.delete("/account", status_code=204)
def delete_account(user_id: RequiredUser):
    if db.client is None:
        raise HTTPException(status_code=503, detail="Account service unavailable")
    for table in _USER_TABLES:
        db.client.table(table).delete().eq("user_id", user_id).execute()
    db.client.auth.admin.delete_user(user_id)
    # credits cae en cascada con auth.users; va al final para que un fallo de auth no deje
    # que ensure_user recree el saldo.
    db.client.table("credits").delete().eq("user_id", user_id).execute()
    logger.info("[account] Deleted user %s", user_id[:8])
    return Response(status_code=204)
