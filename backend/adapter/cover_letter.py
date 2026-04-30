# backend/adapter/cover_letter.py
"""
Cover letter generator.

Takes the adapted CVSchema + JD → returns 3-paragraph plain text.
Uses free-form text generation (no structured output) since the output is prose.
Only references experience that exists in the adapted schema — no hallucination.
"""
import json
import logging
import pathlib
from typing import Literal

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate

from backend.schemas import CVSchema

load_dotenv()

logger = logging.getLogger(__name__)

_PROMPT_PATH = pathlib.Path(__file__).parent.parent / "prompts" / "cover_letter.md"
with open(_PROMPT_PATH, encoding="utf-8") as f:
    _SYSTEM_TEMPLATE = f.read()

# Plain text output — no structured output needed
_model = ChatAnthropic(model="claude-haiku-4-5")

_chain = ChatPromptTemplate.from_messages(
    [
        ("system", _SYSTEM_TEMPLATE),
        ("human", "Write the cover letter now."),
    ]
) | _model


async def generate_cover_letter(
    adapted_schema: CVSchema,
    job_description: str,
    output_language: Literal["es", "en"] = "en",
) -> str:
    """
    Generate a 3-paragraph cover letter from the adapted CV schema + JD.

    Returns plain text (no markdown). Raises on LLM failure.
    The pipeline treats cover letter failure as non-fatal (delivers without it).
    """
    logger.info("[cover_letter] Generating cover letter, lang=%s", output_language)

    result = await _chain.ainvoke(
        {
            "output_language": output_language,
            "adapted_schema": json.dumps(
                adapted_schema.model_dump(exclude={"raw_text_hash"}),
                ensure_ascii=False,
                indent=2,
            ),
            "job_description": job_description,
        }
    )

    text = result.content if hasattr(result, "content") else str(result)
    logger.info("[cover_letter] Generated %d chars", len(text))
    return text.strip()
