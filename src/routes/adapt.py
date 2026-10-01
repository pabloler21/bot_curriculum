# src/routes/adapt.py
"""
POST /adapt  — adapta el CV a una oferta. Modos: cv (1🪙), cover (1🪙), both (2🪙).
GET  /adapt/{run_id}/pdf — descarga el PDF generado.

CV: archivo > token de sesión > CV base del usuario. La JD puede ser texto o una URL,
que se descarga con backend.job_fetch ANTES de cobrar.

PDF storage: dict en memoria acotado. Los PDFs del historial se regeneran (GET /history/{id}/pdf).
"""
import logging
import uuid
from collections import OrderedDict
from typing import Literal, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend import history
from backend.adapter.pipeline import run_pipeline
from backend.auth import RequiredUser
from backend.credits import InsufficientCredits, decrement, ensure_user, restore
from backend.job_fetch import JobFetchError, fetch_job_text, is_url
from backend.schemas import PipelineStatus
from backend.user_cv import get_cv
from src.routes.cv_input import read_session, read_upload

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

# ── In-memory PDF store ───────────────────────────────────────────────────────
# Bounded to avoid unbounded memory growth. Evicts oldest entry on overflow.
_PDF_STORE_MAX = 50
_pdf_store: OrderedDict[str, bytes] = OrderedDict()

COSTS = {"cv": 1, "cover": 1, "both": 2}
MIN_JD_CHARS = 50
MIN_CV_CHARS = 100
_FAILED = (PipelineStatus.FAILED_EXTRACT, PipelineStatus.FAILED_ADAPT)


def _store_pdf(run_id: str, pdf_bytes: bytes) -> None:
    if len(_pdf_store) >= _PDF_STORE_MAX:
        _pdf_store.popitem(last=False)  # evict oldest
    _pdf_store[run_id] = pdf_bytes


# ── POST /adapt ───────────────────────────────────────────────────────────────

@router.post("/adapt")
@limiter.limit("3/minute")
async def adapt_resume(
    request: Request,
    user_id: RequiredUser,
    job_input: str = Form(..., max_length=20000, description="Job description text or a job posting URL"),
    mode: Literal["cv", "cover", "both"] = Form("both"),
    output_language: str = Form("en", pattern="^(es|en)$", description="Output language: 'es' or 'en'"),
    file: Optional[UploadFile] = File(None),
):
    # ── JD: texto o URL (se descarga antes de cobrar) ─────────────────────────
    job_url: str | None = None
    if is_url(job_input):
        job_url = job_input.strip()
        try:
            job_description = await fetch_job_text(job_url)
        except JobFetchError as exc:
            logger.info("[adapt] Job link unreadable: %s", exc)
            raise HTTPException(
                status_code=422,
                detail="We couldn't read that link — paste the job description instead.",
            ) from exc
    else:
        job_description = job_input.strip()
    if len(job_description) < MIN_JD_CHARS:
        raise HTTPException(status_code=422, detail="Job description is too short (min 50 characters).")

    # ── CV: archivo > token de sesión > CV base ───────────────────────────────
    cv_text: str | None = None
    if file is not None:
        cv_text = await read_upload(file)
    elif token := request.headers.get("X-CV-Session-Token"):
        cv_text = read_session(token)
    elif base := get_cv(user_id):
        cv_text = base["cv_text"]
    if not cv_text or not cv_text.strip():
        raise HTTPException(status_code=400, detail="No CV found. Upload your CV first.")
    if len(cv_text.strip()) < MIN_CV_CHARS:
        raise HTTPException(
            status_code=422,
            detail="Extracted CV text is too short. The file may be image-only or corrupted.",
        )

    # ── Créditos ──────────────────────────────────────────────────────────────
    cost = COSTS[mode]
    ensure_user(user_id)
    try:
        decrement(user_id, cost)
    except InsufficientCredits:
        return JSONResponse(status_code=402, content={"detail": "No credits remaining", "code": "no_credits"})

    # ── Pipeline ──────────────────────────────────────────────────────────────
    logger.info(
        "[adapt] mode=%s cv_len=%d jd_len=%d lang=%s", mode, len(cv_text), len(job_description), output_language
    )
    try:
        result, pdf_bytes = await run_pipeline(
            cv_text=cv_text,
            job_description=job_description,
            output_language=output_language,
            user_id=user_id,
            mode=mode,
        )
    except Exception as exc:
        restore(user_id, cost)
        logger.exception("[adapt] Unexpected pipeline error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Pipeline error: {exc}") from exc

    content = result.model_dump(mode="json")
    history_id: str | None = None
    if result.status in _FAILED:
        restore(user_id, cost)
    else:
        try:
            history_id = history.add(user_id, mode, job_description, job_url, content)
        except Exception as exc:  # el usuario ya tiene su resultado: no romper por el historial
            logger.warning("[adapt] Could not save history: %s", exc)

    if pdf_bytes:
        _store_pdf(result.run_id, pdf_bytes)

    return JSONResponse(
        status_code=200,
        content={**content, "job_description": job_description, "history_id": history_id},
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
