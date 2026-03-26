from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from backend.extractor import extract_text
from backend.evaluator import evaluate_cv

app = FastAPI(title="CV Evaluator API")

# permite que Streamlit (en otro puerto) se comunique con FastAPI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/evaluate")
async def evaluate_resume(file: UploadFile = File(...)):
    # leemos el archivo como bytes
    file_bytes = await file.read()

    # extraemos el texto con liteparse
    cv_text = extract_text(file_bytes, file.filename)

    # evaluamos con Claude
    result = evaluate_cv(cv_text)

    return result

@app.get("/health")
def health():
    return {"status": "ok"}