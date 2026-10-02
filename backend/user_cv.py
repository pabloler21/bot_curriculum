# backend/user_cv.py
"""CV base por usuario (tabla user_cvs). No-op si no hay cliente de DB."""
import logging
from datetime import datetime, timezone

from backend.db import client as _db
from backend.schemas import CVSchema

logger = logging.getLogger(__name__)

TABLE = "user_cvs"


def get_cv(user_id: str) -> dict | None:
    if _db is None:
        return None
    res = _db.table(TABLE).select("*").eq("user_id", user_id).execute()
    return res.data[0] if res.data else None


def save_cv(user_id: str, cv_text: str, filename: str | None, source: str) -> None:
    """Crea o reemplaza el CV base. La evaluación anterior deja de valer: se borra."""
    if _db is None:
        return
    _db.table(TABLE).upsert(
        {
            "user_id": user_id,
            "cv_text": cv_text,
            "filename": filename,
            "source": source,
            "last_evaluation": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
        on_conflict="user_id",
    ).execute()
    logger.info("[user_cv] Saved base CV for %s (%s, %d chars)", user_id[:8], source, len(cv_text))


def save_evaluation(user_id: str, evaluation: dict) -> None:
    if _db is None:
        return
    _db.table(TABLE).update({"last_evaluation": evaluation}).eq("user_id", user_id).execute()


def delete_cv(user_id: str) -> None:
    if _db is None:
        return
    _db.table(TABLE).delete().eq("user_id", user_id).execute()


def schema_to_text(schema: CVSchema) -> str:
    """Texto plano del CVSchema, para guardarlo como CV base tras /improve."""
    lines = [schema.candidate_name]
    if schema.contact_info:
        lines.append(schema.contact_info)
    if schema.summary:
        lines += ["", "SUMMARY", schema.summary]
    if schema.experiences:
        lines += ["", "EXPERIENCE"]
        for exp in schema.experiences:
            end = exp.end_date or "Present"
            lines.append(f"{exp.role} — {exp.company} ({exp.start_date} – {end})")
            lines += [f"- {b}" for b in exp.bullets]
    if schema.skills:
        lines += ["", "SKILLS", ", ".join(schema.skills)]
    if schema.education:
        lines += ["", "EDUCATION"]
        for edu in schema.education:
            field = f" — {edu.field}" if edu.field else ""
            year = f" ({edu.year})" if edu.year else ""
            lines.append(f"{edu.degree}{field}, {edu.institution}{year}")
    if schema.languages:
        lines += ["", "LANGUAGES", ", ".join(schema.languages)]
    if schema.certifications:
        lines += ["", "CERTIFICATIONS"] + [f"- {c}" for c in schema.certifications]
    return "\n".join(lines)
