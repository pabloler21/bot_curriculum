import logging
from typing import Annotated, Literal, Optional

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.auth import OptionalUser
from backend.evaluator import evaluate_cv, translate_evaluation
from backend.extractor import extract_text
from backend.jobs import _cache as jobs_cache
from backend.prioritizer import prioritize
from backend.user_cv import get_cv, save_evaluation
from src.routes.cv_input import read_session

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


# máximo 3 requests por minuto por IP
@router.post("/evaluate")
@limiter.limit("3/minute")
async def evaluate_resume(
    request: Request,
    user_id: OptionalUser,
    file: Optional[UploadFile] = File(None),
    job_id: Optional[str] = Form(None),
    output_language: str = Form("en", pattern="^(es|en)$"),
):
    try:
        file_bytes = await file.read() if file is not None else b""
        if file is not None:
            logger.info(
                "[evaluate] File received: %s (%d bytes)", file.filename, len(file_bytes)
            )

        cv_session_token = request.headers.get("X-CV-Session-Token")

        # Fuente del CV: archivo > token de sesión > CV base del usuario logueado
        if file_bytes and file is not None:
            cv_text = extract_text(file_bytes, file.filename)
            logger.info("[evaluate] Text extracted from file: %d chars", len(cv_text))
        elif cv_session_token:
            cv_text = read_session(cv_session_token)
            logger.info("[evaluate] CV text loaded from session: %d chars", len(cv_text))
        elif user_id and (base := get_cv(user_id)):
            cv_text = base["cv_text"]
            logger.info("[evaluate] CV text loaded from base CV: %d chars", len(cv_text))
        else:
            raise HTTPException(status_code=400, detail="No CV provided")

        if not cv_text or cv_text.strip() == "":
            raise HTTPException(
                status_code=422,
                detail=(
                    "Could not extract text. "
                    "Scanned PDFs may not be readable."
                ),
            )

        # Resolve job context if job_id provided
        job_context = None
        if job_id:
            cached = jobs_cache.get("data")
            if cached:
                jobs_list, _ = cached
                job = next((j for j in jobs_list if j.id == str(job_id)), None)
                if job:
                    job_context = (
                        f"Title: {job.title}\nCompany: {job.company}"
                        f"\n\n{job.description}"
                    )
                    logger.info(
                        "[evaluate] Job context injected for job_id=%s", job_id
                    )
                else:
                    logger.info(
                        "[evaluate] job_id=%s not found in cache, "
                        "proceeding without job context",
                        job_id,
                    )

        result = evaluate_cv(cv_text, job_context=job_context, output_language=output_language)
        result = await prioritize(result, job_context)
        logger.info("[evaluate] Evaluation complete")

        if user_id:
            try:
                save_evaluation(user_id, result)
            except Exception as exc:  # no romper la respuesta por un fallo de persistencia
                logger.warning("[evaluate] Could not save evaluation: %s", exc)

        return JSONResponse(status_code=200, content=result)

    except HTTPException:
        raise

    except Exception as e:
        logger.exception("[evaluate] Unexpected error: %s", e)
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        )


# Una evaluación como la devuelve /evaluate, con topes: el endpoint es anónimo y llama al modelo,
# no puede servir para traducir textos arbitrarios.
_Text = Annotated[str, Field(max_length=600)]
_Items = Annotated[list[_Text], Field(max_length=60)]
_Levels = Optional[Annotated[list[Literal["essential", "important", "optional"]], Field(max_length=60)]]


class SavedEvaluation(BaseModel):
    candidate_name: str = Field("", max_length=200)
    target_role: str = Field("", max_length=200)
    overall_score: Optional[int] = Field(None, ge=0, le=100)
    approved: bool = False
    summary: str = Field("", max_length=3000)
    formatting_issues: _Items = []
    keywords_found: _Items = []
    keywords_missing: _Items = []
    recommendations: _Items = []
    strengths: _Items = []
    weaknesses: _Items = []
    keywords_missing_priority: _Levels = None
    recommendations_priority: _Levels = None
    language: Optional[str] = Field(None, max_length=8)
    evaluated_at: Optional[str] = Field(None, max_length=64)


class TranslateRequest(BaseModel):
    evaluation: SavedEvaluation
    output_language: Literal["es", "en"]


@router.post("/evaluate/translate")
@limiter.limit("10/minute")
def translate_saved_evaluation(request: Request, payload: TranslateRequest, user_id: OptionalUser):
    """Pasa una evaluación ya hecha al idioma de la página: mismo puntaje, mismas prioridades."""
    try:
        result = translate_evaluation(payload.evaluation.model_dump(), payload.output_language)
    except Exception as e:
        logger.exception("[evaluate] Translation failed: %s", e)
        raise HTTPException(status_code=502, detail="Could not translate the evaluation")

    if user_id:
        try:
            save_evaluation(user_id, result)
        except Exception as exc:  # no romper la respuesta por un fallo de persistencia
            logger.warning("[evaluate] Could not save translated evaluation: %s", exc)

    return result
