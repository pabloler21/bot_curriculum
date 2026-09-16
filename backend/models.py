# backend/models.py
"""
Centralized model configuration for the adaptation pipeline.

Each stage resolves its model from an env var, defaulting to claude-haiku-4-5.
"""
import os

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

load_dotenv()

_DEFAULT = "claude-haiku-4-5"

_STAGE_MODELS = {
    "extract": os.getenv("AUREA_EXTRACT_MODEL", _DEFAULT),
    "adapt": os.getenv("AUREA_ADAPT_MODEL", _DEFAULT),
    "cover": os.getenv("AUREA_COVER_MODEL", _DEFAULT),
    "interview": os.getenv("AUREA_INTERVIEW_MODEL", _DEFAULT),
}


def model_for(stage: str) -> ChatAnthropic:
    """Return the ChatAnthropic client configured for the given pipeline stage."""
    return ChatAnthropic(model=_STAGE_MODELS[stage])
