# backend/models.py
"""
Centralized model configuration for every stage that calls Claude.

Each stage resolves its model from an env var, defaulting to claude-haiku-5-5.
"""
import os

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

load_dotenv()

_DEFAULT = "claude-haiku-5-5"
# Explícito: langchain-anthropic no conoce Haiku 5.5 y usaría 4096, poco para un CV
# en JSON. Por encima de ~21k el SDK de Anthropic exige streaming.
_MAX_TOKENS = 16000

_STAGE_MODELS = {
    "extract": os.getenv("AUREA_EXTRACT_MODEL", _DEFAULT),
    "adapt": os.getenv("AUREA_ADAPT_MODEL", _DEFAULT),
    "cover": os.getenv("AUREA_COVER_MODEL", _DEFAULT),
    "interview": os.getenv("AUREA_INTERVIEW_MODEL", _DEFAULT),
    "improve": os.getenv("AUREA_IMPROVE_MODEL", _DEFAULT),
    "evaluate": os.getenv("AUREA_EVALUATE_MODEL", _DEFAULT),
    "score": os.getenv("AUREA_SCORE_MODEL", _DEFAULT),
}


def model_for(stage: str) -> ChatAnthropic:
    """Return the ChatAnthropic client configured for the given pipeline stage."""
    return ChatAnthropic(model=_STAGE_MODELS[stage], max_tokens=_MAX_TOKENS)
