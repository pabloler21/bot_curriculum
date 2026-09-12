# src/routes/credits.py
"""GET /credits — return authenticated user's credit balance."""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.auth import RequiredUser
from backend.credits import get_balance

router = APIRouter()


@router.get("/credits")
def get_credits(user_id: RequiredUser):
    """Return the current credit balance for the authenticated user."""
    balance = get_balance(user_id)
    return JSONResponse({"balance": balance})
