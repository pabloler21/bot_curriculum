# src/routes/adapt.py
"""
POST /adapt  — run the adaptation pipeline on a CV + JD
GET  /adapt/{run_id}/pdf — download the generated PDF

Phase 1a: no auth, no credits. Rate limited 3/min per IP.
Phase 1b: add auth dependency + credit check before run_pipeline().

PDF storage: lightweight in-memory dict with a fixed max size.
In Phase 1b this moves to Supabase Storage.
"""
import logging
import uuid
from collections import OrderedDict
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.adapter.pipeline import run_pipeline
from backend.extractor import extract_text
from backend.sessions import get_session

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

# ── In-memory PDF store ───────────────────────────────────────────────────────
# Bounded to avoid unbounded memory growth. Evicts oldest entry on overflow.
_PDF_STORE_MAX = 50
_pdf_store: OrderedDict[str, bytes] = OrderedDict()

MAX_FILE_BYTES = 5 * 1024 * 1024  # 5 MB


def _store_pdf(run_id: str, pdf_bytes: bytes) -> None:
    if len(_pdf_store) >= _PDF_STORE_MAX:
        _pdf_store.popitem(last=False)  # evict oldest
    _pdf_store[run_id] = pdf_bytes


# ── POST /adapt ───────────────────────────────────────────────────────────────

@router.post("/adapt")
@limiter.limit("3/minute")
async def adapt_resume(
    request: Request,
    job_description: str = Form(..., min_length=50, description="Full job description text"),
    output_language: str = Form("en", pattern="^(es|en)$", description="Output language: 'es' or 'en'"),
    file: Optional[UploadFile] = File(None),
):
    """
    Run the 3-stage adaptation pipeline on a CV + job description.

    CV source (in priority order):
    1. `file` upload in this request
    2. `X-CV-Session-Token` header pointing to an existing session

    Returns AdaptationResult as JSON, with `run_id` to download the PDF.
    """
    # ── Resolve CV text ───────────────────────────────────────────────────────
    cv_text: str | None = None

    if file is not None:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")
        if len(file_bytes) > MAX_FILE_BYTES:
            raise HTTPException(status_code=413, detail="File exceeds 5 MB limit")
        try:
            cv_text = extract_text(file_bytes, file.filename)
        except Exception as exc:
            logger.warning("[adapt] Text extraction failed: %s", exc)
            raise HTTPException(
                status_code=422,
                detail="Could not extract text from the CV. Use a PDF with selectable text or DOCX.",
            ) from exc

    if not cv_text:
        token = request.headers.get("X-CV-Session-Token")
        if token:
            try:
                uuid.UUID(token)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid session token format")
            session = get_session(token)
            if session is None:
                raise HTTPException(status_code=400, detail="Session not found or expired")
            cv_text = session.cv_text

    if not cv_text or not cv_text.strip():
        raise HTTPException(status_code=400, detail="No CV provided. Upload a file or supply X-CV-Session-Token.")

    if len(cv_text.strip()) < 100:
        raise HTTPException(
            status_code=422,
            detail="Extracted CV text is too short. The file may be image-only or corrupted.",
        )

    # ── Run pipeline ──────────────────────────────────────────────────────────
    logger.info(
        "[adapt] Starting pipeline, cv_len=%d, jd_len=%d, lang=%s",
        len(cv_text),
        len(job_description),
        output_language,
    )

    try:
        result, pdf_bytes = await run_pipeline(
            cv_text=cv_text,
            job_description=job_description,
            output_language=output_language,
        )
    except Exception as exc:
        logger.exception("[adapt] Unexpected pipeline error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}") from exc

    if pdf_bytes:
        _store_pdf(result.run_id, pdf_bytes)

    return JSONResponse(
        status_code=200,
        content=result.model_dump(mode="json"),
    )


# ── GET /adapt/{run_id}/pdf ───────────────────────────────────────────────────

@router.get("/adapt/{run_id}/pdf")
async def download_adapted_pdf(run_id: str):
    """
    Download the PDF generated for a pipeline run.

    The PDF is stored in memory for the lifetime of the server process.
    Phase 1b: stored in Supabase Storage, accessible by authenticated user.
    """
    try:
        uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id format")

    pdf_bytes = _pdf_store.get(run_id)
    if pdf_bytes is None:
        raise HTTPException(
            status_code=404,
            detail="PDF not found. It may have expired — re-run the adapter to generate a new one.",
        )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="aurea_adapted_cv.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
