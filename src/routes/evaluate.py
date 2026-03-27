import logging

from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from backend.extractor import extract_text
from backend.evaluator import evaluate_cv

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

# máximo 10 requests por minuto por IP
@router.post("/evaluate")
@limiter.limit("3/minute")
async def evaluate_resume(request: Request, file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()
        logger.info("[evaluate] File received: %s (%d bytes)", file.filename, len(file_bytes))

        if not file_bytes:
            raise HTTPException(status_code=400, detail="File is empty")

        cv_text = extract_text(file_bytes, file.filename)
        logger.info("[evaluate] Text extracted: %d chars", len(cv_text))

        if not cv_text or cv_text.strip() == "":
            raise HTTPException(
                status_code=422,
                detail=(
                    "Could not extract text. "
                    "Scanned PDFs may not be readable."
                ),
            )

        result = evaluate_cv(cv_text)
        logger.info("[evaluate] Evaluation complete for: %s", file.filename)

        return JSONResponse(status_code=200, content=result)

    except HTTPException:
        raise

    except Exception as e:
        logger.exception("[evaluate] Unexpected error processing %s: %s", file.filename, e)
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        )