# backend/adapter/interview.py
"""
Interview prep generator.

Takes the adapted CVSchema + JD + detected gaps → returns 8-10 interview questions,
each with a draft answer grounded in the schema.

Runs on demand from POST /interview, not as part of run_pipeline(): most users
download the PDF and leave, so generating this eagerly would burn tokens for nothing.

ponytail: no similarity validation on the answers (the cover letter stage has none
either). The prompt constrains answers to the schema and the UI shows `based_on` so
the user can eyeball provenance. Add backend/adapter/validator.py-style embedding
checks here if answers start drifting from the CV in practice.
"""
import json
import logging
import pathlib
from typing import Literal

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from backend.models import model_for
from backend.schemas import CVSchema, Gap, InterviewQuestion

load_dotenv()

logger = logging.getLogger(__name__)

_PROMPT_PATH = pathlib.Path(__file__).parent.parent / "prompts" / "interview_prep.md"
with open(_PROMPT_PATH, encoding="utf-8") as f:
    _SYSTEM_TEMPLATE = f.read()


class _InterviewOutput(BaseModel):
    questions: list[InterviewQuestion] = Field(default_factory=list)


_model = model_for("interview")
_structured_model = _model.with_structured_output(_InterviewOutput)

_chain = ChatPromptTemplate.from_messages(
    [
        ("system", _SYSTEM_TEMPLATE),
        ("human", "Write the interview questions and draft answers now."),
    ]
) | _structured_model


def _format_gaps(gaps: list[Gap]) -> str:
    """Render gaps as prompt text. Never returns an empty string."""
    if not gaps:
        return "None detected. Use all slots for technical and behavioral questions."
    return "\n".join(
        f"- [{gap.confidence}] {gap.jd_requirement}\n"
        f"  Suggested next step: {gap.suggestion}"
        for gap in gaps
    )


async def generate_interview_prep(
    adapted_schema: CVSchema,
    job_description: str,
    gaps: list[Gap],
    output_language: Literal["es", "en"] = "en",
) -> list[InterviewQuestion]:
    """
    Generate interview questions with draft answers.

    Raises on LLM failure — the caller decides how to surface it.
    """
    logger.info(
        "[interview] Generating prep, gaps=%d, lang=%s", len(gaps), output_language
    )

    result = await _chain.ainvoke(
        {
            "output_language": output_language,
            "adapted_schema": json.dumps(
                adapted_schema.model_dump(exclude={"raw_text_hash"}),
                ensure_ascii=False,
                indent=2,
            ),
            "job_description": job_description,
            "gaps_section": _format_gaps(gaps),
        }
    )

    logger.info("[interview] Generated %d questions", len(result.questions))
    return result.questions
