from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
from backend.extractor import extract_text
from backend.evaluator import evaluate_cv

limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

# máximo 10 requests por minuto por IP
@router.post("/evaluate")
@limiter.limit("10/minute")
async def evaluate_resume(request: Request, file: UploadFile = File(...)):
    try:
        file_bytes = await file.read()

        if not file_bytes:
            raise HTTPException(status_code=400, detail="File is empty")

        cv_text = extract_text(file_bytes, file.filename)

        if not cv_text or cv_text.strip() == "":
            raise HTTPException(
                status_code=422,
                detail=(
                    "Could not extract text. "
                    "Scanned PDFs may not be readable."
                ),
            )

        result = evaluate_cv(cv_text)

        return JSONResponse(status_code=200, content=result)

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Internal server error: {str(e)}"
        )