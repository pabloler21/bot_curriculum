# src/routes/session.py
import logging

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response

from backend.extractor import extract_text
from backend.sessions import delete_session, get_session, store_session

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB


@router.post("/session")
async def create_session(file: UploadFile = File(...)):
    file_bytes = await file.read()

    if not file_bytes:
        raise HTTPException(status_code=400, detail="File is empty")

    if len(file_bytes) > MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds 5 MB limit")

    cv_text = extract_text(file_bytes, file.filename)
    if not cv_text or not cv_text.strip():
        raise HTTPException(
            status_code=422,
            detail="Could not extract text. Scanned PDFs may not be readable.",
        )

    token = store_session(cv_text, file.filename)
    logger.info("[session] Created session for %s", file.filename)
    return {"token": token, "filename": file.filename, "char_count": len(cv_text)}


@router.get("/session/{token}")
async def read_session(token: str):
    session = get_session(token)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found or expired")
    return {
        "exists": True,
        "filename": session.filename,
        "uploaded_at": session.uploaded_at.isoformat(),
    }


@router.delete("/session/{token}", status_code=204)
async def remove_session(token: str):
    delete_session(token)
    return Response(status_code=204)
