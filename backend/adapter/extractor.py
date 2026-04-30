# backend/adapter/extractor.py
"""
Pipeline Stage 1 — Structured extraction.

Takes raw CV text → returns CVSchema (ground truth of the candidate's experience).
Uses LangChain + claude-haiku-4-5 with structured output.
Nothing is invented — only what is in the text is extracted.
"""
import logging
import pathlib

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate

from backend.schemas import CVSchema, compute_hash

load_dotenv()

logger = logging.getLogger(__name__)

_PROMPT_PATH = pathlib.Path(__file__).parent.parent / "prompts" / "extract_schema.md"
with open(_PROMPT_PATH, encoding="utf-8") as f:
    _SYSTEM_PROMPT = f.read()

_model = ChatAnthropic(model="claude-haiku-4-5")
_structured_model = _model.with_structured_output(CVSchema)

_chain = ChatPromptTemplate.from_messages(
    [
        ("system", _SYSTEM_PROMPT),
        ("human", "Extract the structured schema from this CV:\n\n{cv_text}"),
    ]
) | _structured_model


async def extract_schema(cv_text: str) -> CVSchema:
    """
    Extract CVSchema from raw CV text.

    The returned schema is the pipeline's ground truth (whitelist).
    raw_text_hash is set here, not by the LLM.
    Raises on LLM failure — caller handles retry logic.
    """
    logger.info("[extractor] Invoking extraction, cv_text_length=%d", len(cv_text))
    schema: CVSchema = await _chain.ainvoke({"cv_text": cv_text})
    # Set hash programmatically — LLM should leave it empty
    schema.raw_text_hash = compute_hash(cv_text)
    logger.info(
        "[extractor] Extracted schema: candidate=%s, experiences=%d, skills=%d",
        schema.candidate_name,
        len(schema.experiences),
        len(schema.skills),
    )
    return schema
