# src/routes/history.py
"""GET /history — My Jobs: lo que generó el usuario, con PDFs regenerables."""
import uuid

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from backend import history
from backend.adapter.renderer import render_pdf
from backend.auth import RequiredUser
from backend.schemas import CVSchema

router = APIRouter()


def _get_owned(user_id: str, gen_id: str) -> dict:
    try:
        uuid.UUID(gen_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid id")
    row = history.get(user_id, gen_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return row


@router.get("/history")
def list_history(user_id: RequiredUser):
    return history.list_for(user_id)


@router.get("/history/{gen_id}")
def read_history(gen_id: str, user_id: RequiredUser):
    return _get_owned(user_id, gen_id)


@router.get("/history/{gen_id}/pdf")
def history_pdf(gen_id: str, user_id: RequiredUser):
    row = _get_owned(user_id, gen_id)
    schema = (row.get("result") or {}).get("adapted_schema")
    if not schema:
        raise HTTPException(status_code=404, detail="This item has no CV")
    pdf = render_pdf(CVSchema.model_validate(schema))
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="aurea_cv.pdf"'},
    )
