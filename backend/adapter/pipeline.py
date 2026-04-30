# backend/adapter/pipeline.py
"""
Aurea adaptation pipeline orchestrator.

Runs the 3-stage pipeline with retry logic and structured logging.
This is the single public entry point — callers only need run_pipeline().

State machine:
    CREATED → EXTRACTING → ADAPTING → VALIDATING → COMPLETED
                   ↓             ↓            ↓
            FAILED_EXTRACT  FAILED_ADAPT   PARTIAL (with warning)

Retry budget:
    Stage 2 (adapt): max 2 retries (3 total attempts)
    Each retry injects feedback about which bullets failed validation
    If still failing after max retries → PARTIAL (bullets flagged in UI)

Credit policy (Phase 1a: no credits yet):
    Phase 1b will call decrement before ADAPTING and restore on FAILED_* states.
    The placeholder hooks are here so the interface doesn't change in 1b.
"""
import logging
import time
import uuid
from typing import Literal

from backend.adapter.cover_letter import generate_cover_letter
from backend.adapter.extractor import extract_schema
from backend.adapter.logger import PipelineLogger
from backend.adapter.renderer import render_pdf
from backend.adapter.validator import SIMILARITY_THRESHOLD, validate_adaptation
from backend.schemas import AdaptationResult, CVSchema, PipelineStatus

# Import here to allow easy mocking in tests
from backend.adapter.adapter import adapt_cv

logger = logging.getLogger(__name__)

_MAX_ADAPT_RETRIES = 2  # max 2 retries → 3 total attempts


async def run_pipeline(
    cv_text: str,
    job_description: str,
    output_language: Literal["es", "en"] = "en",
    user_id: str | None = None,
    similarity_threshold: float = SIMILARITY_THRESHOLD,
) -> tuple[AdaptationResult, bytes | None]:
    """
    Execute the full adaptation pipeline.

    Args:
        cv_text: raw text extracted from the uploaded CV
        job_description: raw JD text pasted by the user
        output_language: "es" or "en"
        user_id: placeholder for Phase 1b credit system
        similarity_threshold: cosine similarity floor for validation

    Returns:
        (AdaptationResult, pdf_bytes | None)
        pdf_bytes is None if adaptation failed or PDF rendering failed.
    """
    run_id = str(uuid.uuid4())
    pl = PipelineLogger(run_id=run_id, user_id=user_id)
    wall_start = time.monotonic()

    pl.start(
        cv_text_length=len(cv_text),
        jd_length=len(job_description),
        lang=output_language,
    )

    # ── Stage 1: Extract ──────────────────────────────────────────────────────
    pl.stage("extracting")
    try:
        original_schema: CVSchema = await extract_schema(cv_text)
    except Exception as exc:
        duration_ms = int((time.monotonic() - wall_start) * 1000)
        pl.end(
            status=PipelineStatus.FAILED_EXTRACT,
            error=str(exc),
            duration_ms=duration_ms,
        )
        return (
            AdaptationResult(
                run_id=run_id,
                status=PipelineStatus.FAILED_EXTRACT,
                error_message=str(exc),
            ),
            None,
        )

    # ── Stage 2+3: Adapt → Validate (with retries) ───────────────────────────
    adapted_schema: CVSchema | None = None
    gaps = []
    suspicious_bullets: list[str] = []
    retries = 0
    adapt_error: str | None = None

    for attempt in range(_MAX_ADAPT_RETRIES + 1):
        pl.stage("adapting", attempt=attempt)
        try:
            adapted_schema, gaps = await adapt_cv(
                schema=original_schema,
                job_description=job_description,
                output_language=output_language,
                retry_feedback=suspicious_bullets if attempt > 0 else None,
            )
        except Exception as exc:
            adapt_error = str(exc)
            logger.warning(
                "[pipeline] Adapt attempt %d/%d failed: %s",
                attempt + 1,
                _MAX_ADAPT_RETRIES + 1,
                exc,
            )
            if attempt < _MAX_ADAPT_RETRIES:
                retries += 1
                continue
            # All attempts exhausted
            duration_ms = int((time.monotonic() - wall_start) * 1000)
            pl.end(
                status=PipelineStatus.FAILED_ADAPT,
                retries=retries,
                error=adapt_error,
                duration_ms=duration_ms,
            )
            return (
                AdaptationResult(
                    run_id=run_id,
                    status=PipelineStatus.FAILED_ADAPT,
                    error_message=adapt_error,
                    retries=retries,
                ),
                None,
            )

        # Adaptation succeeded — now validate
        pl.stage("validating", attempt=attempt)
        suspicious_bullets = validate_adaptation(
            original_schema, adapted_schema, similarity_threshold
        )

        if not suspicious_bullets:
            # Perfect — no suspicious bullets
            break

        if attempt < _MAX_ADAPT_RETRIES:
            logger.info(
                "[pipeline] %d suspicious bullets, retrying adaptation (attempt %d/%d)",
                len(suspicious_bullets),
                attempt + 1,
                _MAX_ADAPT_RETRIES + 1,
            )
            retries += 1
            # Loop continues with retry_feedback populated
        # else: last attempt — deliver as PARTIAL

    # ── Stage 4: Cover letter (non-fatal) ────────────────────────────────────
    cover_letter: str | None = None
    if adapted_schema is not None:
        try:
            cover_letter = await generate_cover_letter(
                adapted_schema, job_description, output_language
            )
        except Exception as exc:
            logger.warning("[pipeline] Cover letter generation failed: %s", exc)
            # Non-fatal: deliver without cover letter

    # ── PDF rendering (non-fatal) ─────────────────────────────────────────────
    pdf_bytes: bytes | None = None
    if adapted_schema is not None:
        try:
            pdf_bytes = render_pdf(adapted_schema)
        except Exception as exc:
            logger.warning("[pipeline] PDF rendering failed: %s", exc)

    # ── Finalize ──────────────────────────────────────────────────────────────
    final_status = (
        PipelineStatus.PARTIAL if suspicious_bullets else PipelineStatus.COMPLETED
    )
    duration_ms = int((time.monotonic() - wall_start) * 1000)
    pl.end(
        status=final_status,
        retries=retries,
        duration_ms=duration_ms,
        suspicious_count=len(suspicious_bullets),
    )

    result = AdaptationResult(
        run_id=run_id,
        status=final_status,
        adapted_schema=adapted_schema,
        gaps=gaps,
        cover_letter=cover_letter,
        suspicious_bullets=suspicious_bullets,
        retries=retries,
    )
    return result, pdf_bytes
