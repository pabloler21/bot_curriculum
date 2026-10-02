# src/routes/cv.py
"""GET /cv y PUT /cv — CV base del usuario autenticado."""
import logging
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Request, UploadFile

from backend.auth import RequiredUser
from backend.sessions import get_session
from backend.user_cv import get_cv, save_cv
from src.routes.cv_input import read_session, read_upload

logger = logging.getLogger(__name__)
router = APIRouter()

MIN_CV_CHARS = 100


@router.get("/cv")
def read_cv(user_id: RequiredUser):
    row = get_cv(user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No CV uploaded yet")
    return {
        "filename": row.get("filename"),
        "source": row.get("source"),
        "last_evaluation": row.get("last_evaluation"),
        "updated_at": row.get("updated_at"),
    }


@router.put("/cv")
async def replace_cv(request: Request, user_id: RequiredUser, file: Optional[UploadFile] = File(None)):
    """Reemplaza el CV base con un archivo, o reclama el CV de un token de sesión anónimo."""
    token = request.headers.get("X-CV-Session-Token")
    if file is not None:
        cv_text, filename = await read_upload(file), file.filename
    elif token:
        cv_text = read_session(token)
        filename = get_session(token).filename
    else:
        raise HTTPException(status_code=400, detail="Upload a file or supply X-CV-Session-Token.")

    if len(cv_text.strip()) < MIN_CV_CHARS:
        raise HTTPException(
            status_code=422,
            detail="Extracted CV text is too short. The file may be image-only or corrupted.",
        )

    save_cv(user_id, cv_text, filename, "upload")
    return {"filename": filename, "source": "upload"}
