# backend/adapter/adapter.py
"""
Pipeline Stage 2 — CV adaptation with whitelist enforcement.

Takes CVSchema (ground truth) + JD text → returns adapted CVSchema + gaps.
The LLM can only reformulate/reorder content from the original schema.
Retry feedback is injected into the prompt when validation finds suspicious bullets.
"""
import json
import logging
import pathlib
from typing import Literal

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from backend.schemas import CVSchema, Gap

load_dotenv()

logger = logging.getLogger(__name__)

_PROMPT_PATH = pathlib.Path(__file__).parent.parent / "prompts" / "adapt_cv.md"
with open(_PROMPT_PATH, encoding="utf-8") as f:
    _SYSTEM_TEMPLATE = f.read()

# Internal model that bundles adapted schema + gaps in a single structured output
class _AdaptationOutput(BaseModel):
    adapted_schema: CVSchema
    gaps: list[Gap] = Field(default_factory=list)


_model = ChatAnthropic(model="claude-haiku-4-5")
_structured_model = _model.with_structured_output(_AdaptationOutput)

_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", _SYSTEM_TEMPLATE),
        ("human", "Adapt the CV for this job. Return adapted_schema and gaps."),
    ]
)

_chain = _prompt | _structured_model


async def adapt_cv(
    schema: CVSchema,
    job_description: str,
    output_language: Literal["es", "en"] = "en",
    retry_feedback: list[str] | None = None,
) -> tuple[CVSchema, list[Gap]]:
    """
    Adapt the CVSchema to the JD.

    Args:
        schema: original CVSchema — the whitelist.
        job_description: raw JD text.
        output_language: target language for the adapted schema.
        retry_feedback: list of suspicious bullets from the previous attempt.
                        Injected into the prompt so the model can fix them.

    Returns:
        (adapted_schema, gaps)

    Raises on LLM failure. Retry logic is the caller's responsibility (pipeline.py).
    """
    retry_section = ""
    if retry_feedback:
        bullets_str = "\n".join(f"  - {b}" for b in retry_feedback)
        retry_section = (
            f"\n\n### ⚠️ RETRY FEEDBACK — Fix these bullets\n"
            f"The following bullets from your previous attempt were flagged as potentially "
            f"hallucinated (low similarity to original). Rewrite them to stay closer to "
            f"the original wording while still being relevant to the JD:\n{bullets_str}"
        )

    logger.info(
        "[adapter] Invoking adaptation, lang=%s, retry=%s",
        output_language,
        bool(retry_feedback),
    )

    result: _AdaptationOutput = await _chain.ainvoke(
        {
            "output_language": output_language,
            "original_schema": json.dumps(schema.model_dump(), ensure_ascii=False, indent=2),
            "job_description": job_description,
            "retry_section": retry_section,
        }
    )

    # Preserve the original hash — adapted schema traces back to same source
    result.adapted_schema.raw_text_hash = schema.raw_text_hash

    logger.info(
        "[adapter] Adapted: experiences=%d, skills=%d, gaps=%d",
        len(result.adapted_schema.experiences),
        len(result.adapted_schema.skills),
        len(result.gaps),
    )
    return result.adapted_schema, result.gaps
