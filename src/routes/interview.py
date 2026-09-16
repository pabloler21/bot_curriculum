# src/routes/interview.py
"""
POST /interview — generate interview questions for an adaptation the user already ran.

Stateless by design: the browser already holds the full AdaptationResult in
localStorage, so it posts the pieces back instead of the server persisting runs.
The in-memory PDF store in adapt.py is bounded and dies on restart, so it cannot
serve a result the user restored from the "View result" banner days later.

No credit is charged: this is bundled with the adaptation the user already paid a
credit for. Abuse is bounded by the rate limit.
"""
import logging
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.adapter.interview import generate_interview_prep
from backend.auth import RequiredUser
from backend.schemas import CVSchema, Gap, InterviewQuestion

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)
router = APIRouter()

# Guards the LLM bill against a client-controlled body. A real CV schema plus a JD
# lands well under this; anything above it is not a resume.
MAX_PAYLOAD_CHARS = 60_000


class InterviewRequest(BaseModel):
    adapted_schema: CVSchema
    job_description: str = Field(..., min_length=50, max_length=20_000)
    gaps: list[Gap] = Field(default_factory=list)
    output_language: Literal["es", "en"] = "en"


class InterviewResponse(BaseModel):
    questions: list[InterviewQuestion]


@router.post("/interview", response_model=InterviewResponse)
@limiter.limit("3/minute")
async def interview_prep(
    request: Request,
    user_id: RequiredUser,
    payload: InterviewRequest,
):
    """Return 8-10 interview questions with draft answers grounded in the adapted CV."""
    if len(payload.model_dump_json()) > MAX_PAYLOAD_CHARS:
        raise HTTPException(status_code=413, detail="Payload too large")

    try:
        questions = await generate_interview_prep(
            adapted_schema=payload.adapted_schema,
            job_description=payload.job_description,
            gaps=payload.gaps,
            output_language=payload.output_language,
        )
    except Exception as exc:
        logger.warning("[interview] Generation failed for user %s: %s", user_id[:8], exc)
        raise HTTPException(
            status_code=502, detail="Could not generate interview prep. Please try again."
        )

    return InterviewResponse(questions=questions)
