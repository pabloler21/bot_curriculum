from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from backend.evaluator import evaluate_cv
from backend.extractor import extract_text

router = APIRouter()


@router.post("/evaluate")
async def evaluate_resume(file: UploadFile = File(...)):
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
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
