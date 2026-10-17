# tests/test_cover_letter.py
"""Tests for backend/adapter/cover_letter.py."""
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage

from backend.adapter.cover_letter import generate_cover_letter
from backend.schemas import CVSchema

_SCHEMA = CVSchema(candidate_name="Jane", experiences=[], skills=["Python"], education=[])


@pytest.mark.asyncio
async def test_cover_letter_skips_thinking_blocks():
    # Haiku 5.5 piensa por defecto: la respuesta llega como lista de bloques.
    reply = AIMessage(content=[
        {"type": "thinking", "thinking": "", "signature": "sig"},
        {"type": "text", "text": "  Dear team  "},
    ])
    with patch("backend.adapter.cover_letter._chain") as chain:
        chain.ainvoke = AsyncMock(return_value=reply)
        assert await generate_cover_letter(_SCHEMA, "Data Analyst at Acme") == "Dear team"
