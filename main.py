from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from backend.extractor import extract_text
from backend.evaluator import evaluate_cv

app = FastAPI(title="CV Evaluator API")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/evaluate")
async def evaluate_resume(file: UploadFile = File(...)):
    
    file_bytes = await file.read()

    
    cv_text = extract_text(file_bytes, file.filename)

    
    result = evaluate_cv(cv_text)

    return result

@app.get("/health")
def health():
    return {"status": "ok"}