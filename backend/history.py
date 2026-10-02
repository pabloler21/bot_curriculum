"""Historial de generaciones por usuario (tabla generations → My Jobs)."""
import logging

from backend.db import client as _db

logger = logging.getLogger(__name__)

TABLE = "generations"
_LIST_FIELDS = "id,created_at,kind,job_title,company,job_url"


def job_title_from(job_description: str) -> str | None:
    """Primera línea no vacía de la JD, como título aproximado (sin gastar una llamada al LLM)."""
    for line in job_description.splitlines():
        if line.strip():
            return line.strip()[:120]
    return None


def add(user_id: str, kind: str, job_description: str, job_url: str | None, result: dict) -> str | None:
    if _db is None:
        return None
    res = _db.table(TABLE).insert(
        {
            "user_id": user_id,
            "kind": kind,
            "job_title": job_title_from(job_description),
            "company": None,
            "job_description": job_description,
            "job_url": job_url,
            "result": result,
        }
    ).execute()
    return res.data[0]["id"] if res.data else None


def list_for(user_id: str) -> list[dict]:
    if _db is None:
        return []
    res = (
        _db.table(TABLE)
        .select(_LIST_FIELDS)
        .eq("user_id", user_id)
        .order("created_at", desc=True)
        .limit(100)
        .execute()
    )
    return res.data or []


def get(user_id: str, gen_id: str) -> dict | None:
    if _db is None:
        return None
    res = _db.table(TABLE).select("*").eq("id", gen_id).eq("user_id", user_id).execute()
    return res.data[0] if res.data else None


def delete_all(user_id: str) -> None:
    if _db is None:
        return
    _db.table(TABLE).delete().eq("user_id", user_id).execute()
