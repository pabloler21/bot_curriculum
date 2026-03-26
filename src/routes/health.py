from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
def health():
    # verificamos que el servidor esta corriendo
    return {"status": "ok"}