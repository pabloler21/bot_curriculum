# backend/adapter/improver.py
"""
"Apply to my CV": aplica las recomendaciones del evaluator al CVSchema.

Mismo contrato anti-alucinación que adapter.py: el schema original es la whitelist.
El caller valida el resultado con validate_adaptation().
"""
import json
import logging
import pathlib

from langchain_core.prompts import ChatPromptTemplate

from backend.models import model_for
from backend.schemas import CVSchema

logger = logging.getLogger(__name__)

_PROMPT_PATH = pathlib.Path(__file__).parent.parent / "prompts" / "improve_cv.md"
with open(_PROMPT_PATH, encoding="utf-8") as f:
    _SYSTEM_TEMPLATE = f.read()

_chain = ChatPromptTemplate.from_messages(
    [
        ("system", _SYSTEM_TEMPLATE),
        ("human", "Apply the recommendations and return the improved CV schema."),
    ]
) | model_for("improve").with_structured_output(CVSchema)


async def improve_cv(schema: CVSchema, recommendations: list[str]) -> CVSchema:
    logger.info("[improver] Applying %d recommendations", len(recommendations))
    improved: CVSchema = await _chain.ainvoke(
        {
            "original_schema": json.dumps(schema.model_dump(), ensure_ascii=False, indent=2),
            "recommendations": "\n".join(f"- {r}" for r in recommendations),
        }
    )
    improved.raw_text_hash = schema.raw_text_hash
    return improved
