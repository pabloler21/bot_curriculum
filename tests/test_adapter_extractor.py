# tests/test_adapter_extractor.py
"""Tests for backend/adapter/extractor.py — Stage 1 extraction."""
import pytest
from unittest.mock import AsyncMock, patch

from backend.adapter.extractor import extract_schema
from backend.schemas import CVSchema, WorkExperience, Education


def make_mock_schema() -> CVSchema:
    return CVSchema(
        candidate_name="Jane Doe",
        contact_info="jane@example.com | linkedin.com/in/jane",
        summary="Senior Python developer with 5 years experience",
        experiences=[
            WorkExperience(
                company="Acme Corp",
                role="Senior Software Engineer",
                start_date="Jan 2020",
                end_date=None,
                bullets=["Built FastAPI microservices", "Reduced API latency by 40%"],
                technologies=["Python", "FastAPI", "PostgreSQL"],
            )
        ],
        skills=["Python", "FastAPI", "Docker", "PostgreSQL"],
        education=[
            Education(institution="UTN", degree="Computer Engineering", field="Software", year="2019")
        ],
        languages=["Spanish (native)", "English (B2)"],
        certifications=["AWS Certified Developer"],
    )


@pytest.mark.asyncio
async def test_extract_schema_returns_cv_schema():
    """extract_schema should return a CVSchema with the hash set."""
    mock_schema = make_mock_schema()

    with patch("backend.adapter.extractor._chain") as mock_chain:
        mock_chain.ainvoke = AsyncMock(return_value=mock_schema)
        result = await extract_schema("Full CV text here with content about Jane Doe...")

    assert isinstance(result, CVSchema)
    assert result.candidate_name == "Jane Doe"


@pytest.mark.asyncio
async def test_extract_schema_sets_raw_text_hash():
    """Hash must be set programmatically after extraction, not by LLM."""
    cv_text = "My CV content is here"
    mock_schema = make_mock_schema()
    mock_schema.raw_text_hash = ""  # LLM leaves it empty

    with patch("backend.adapter.extractor._chain") as mock_chain:
        mock_chain.ainvoke = AsyncMock(return_value=mock_schema)
        result = await extract_schema(cv_text)

    assert len(result.raw_text_hash) == 64  # SHA-256 hex = 64 chars
    assert result.raw_text_hash != ""


@pytest.mark.asyncio
async def test_extract_schema_propagates_llm_errors():
    """LLM failures should bubble up so pipeline can handle them."""
    with patch("backend.adapter.extractor._chain") as mock_chain:
        mock_chain.ainvoke = AsyncMock(side_effect=Exception("LLM timeout"))

        with pytest.raises(Exception, match="LLM timeout"):
            await extract_schema("Some CV text")


@pytest.mark.asyncio
async def test_extract_schema_passes_cv_text_to_chain():
    """The CV text must be passed to the chain, not truncated or modified."""
    cv_text = "Unique CV content: Python dev, 5 years, FastAPI specialist"
    mock_schema = make_mock_schema()
    captured_input = {}

    async def capture_invoke(inputs):
        captured_input.update(inputs)
        return mock_schema

    with patch("backend.adapter.extractor._chain") as mock_chain:
        mock_chain.ainvoke = capture_invoke
        await extract_schema(cv_text)

    assert captured_input.get("cv_text") == cv_text
