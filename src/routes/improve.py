# src/routes/improve.py
"""POST /improve — "Apply to my CV": aplica las recomendaciones al CV base (1🪙)."""
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StringConstraints
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend import history
from backend.adapter.extractor import extract_schema
from backend.adapter.improver import improve_cv
from backend.adapter.renderer import render_pdf
from backend.adapter.validator import validate_adaptation
from backend.auth import RequiredUser
from backend.credits import InsufficientCredits, decrement, ensure_user, restore
from backend.schemas import AdaptationResult, PipelineStatus
from backend.user_cv import get_cv, save_cv, schema_to_text
from src.routes.adapt import _store_pdf

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

COST = 1


class ImproveRequest(BaseModel):
    # Vienen del cliente: se tratan como input no confiable (topes acá, encuadre en el prompt).
    recommendations: list[
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    ] = Field(min_length=1, max_length=20)


@router.post("/improve")
@limiter.limit("3/minute")
async def improve_resume(request: Request, body: ImproveRequest, user_id: RequiredUser):
    base = get_cv(user_id)
    if base is None:
        raise HTTPException(status_code=400, detail="No CV found. Upload your CV first.")

    ensure_user(user_id)
    try:
        decrement(user_id, COST)
    except InsufficientCredits:
        return JSONResponse(status_code=402, content={"detail": "No credits remaining", "code": "no_credits"})

    run_id = str(uuid.uuid4())
    try:
        original = await extract_schema(base["cv_text"])
        improved = await improve_cv(original, body.recommendations)
        suspicious = validate_adaptation(original, improved)
        pdf_bytes = render_pdf(improved)
    except Exception as exc:
        restore(user_id, COST)
        logger.exception("[improve] Failed: %s", exc)
        raise HTTPException(status_code=500, detail="Could not improve your CV. Your credit was restored.") from exc

    result = AdaptationResult(
        run_id=run_id,
        status=PipelineStatus.PARTIAL if suspicious else PipelineStatus.COMPLETED,
        adapted_schema=improved,
        suspicious_bullets=suspicious,
    )
    _store_pdf(run_id, pdf_bytes)
    save_cv(user_id, schema_to_text(improved), base.get("filename"), "improved")

    content = result.model_dump(mode="json")
    history_id = None
    try:
        history_id = history.add(user_id, "improve", "", None, content)
    except Exception as exc:
        logger.warning("[improve] Could not save history: %s", exc)

    return JSONResponse(status_code=200, content={**content, "history_id": history_id})
