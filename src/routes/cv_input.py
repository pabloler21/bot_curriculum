# src/routes/cv_input.py
"""Lectura del CV desde un upload o un token de sesión, compartida por /cv, /adapt y /evaluate."""
import logging
import uuid

from fastapi import HTTPException, UploadFile

from backend.extractor import extract_text
from backend.sessions import get_session

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB


async def read_upload(file: UploadFile) -> str:
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(file_bytes) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 5 MB limit")
    try:
        return extract_text(file_bytes, file.filename)
    except Exception as exc:
        logger.warning("[cv_input] Text extraction failed: %s", exc)
        raise HTTPException(
            status_code=422,
            detail="Could not extract text from the CV. Use a PDF with selectable text or DOCX.",
        ) from exc


def read_session(token: str) -> str:
    try:
        uuid.UUID(token)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session token format")
    session = get_session(token)
    if session is None:
        raise HTTPException(status_code=400, detail="Session not found or expired")
    return session.cv_text
