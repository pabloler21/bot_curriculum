# tests/test_adapter_adapter.py
"""Tests for backend/adapter/adapter.py — Stage 2 adaptation."""
import pytest
from unittest.mock import AsyncMock, patch

from backend.adapter.adapter import adapt_cv, _AdaptationOutput
from backend.schemas import CVSchema, Gap, WorkExperience


def make_schema() -> CVSchema:
    return CVSchema(
        candidate_name="Jane Doe",
        experiences=[
            WorkExperience(
                company="Acme Corp",
                role="Software Engineer",
                start_date="Jan 2020",
                bullets=["Built REST API", "Reduced latency by 40%"],
                technologies=["Python", "FastAPI"],
            )
        ],
        skills=["Python", "FastAPI"],
        education=[],
        raw_text_hash="abc123",
    )


def make_adaptation_output(schema=None, gaps=None):
    s = schema or make_schema()
    s.raw_text_hash = ""  # LLM doesn't set hash
    return _AdaptationOutput(
        adapted_schema=s,
        gaps=gaps or [
            Gap(
                jd_requirement="Docker experience",
                confidence="hard",
                suggestion="Add Docker projects to GitHub",
            )
        ],
    )


@pytest.mark.asyncio
async def test_adapt_cv_returns_schema_and_gaps():
    original = make_schema()
    mock_output = make_adaptation_output()

    with patch("backend.adapter.adapter._chain") as mock_chain:
        mock_chain.ainvoke = AsyncMock(return_value=mock_output)
        adapted, gaps = await adapt_cv(original, "Job description here", "en")

    assert isinstance(adapted, CVSchema)
    assert isinstance(gaps, list)
    assert len(gaps) == 1
    assert gaps[0].confidence == "hard"


@pytest.mark.asyncio
async def test_adapt_cv_preserves_original_hash():
    """The adapted schema should keep the original CV's hash for audit trail."""
    original = make_schema()
    original.raw_text_hash = "original_hash_abc"
    mock_output = make_adaptation_output()

    with patch("backend.adapter.adapter._chain") as mock_chain:
        mock_chain.ainvoke = AsyncMock(return_value=mock_output)
        adapted, _ = await adapt_cv(original, "JD text", "en")

    assert adapted.raw_text_hash == "original_hash_abc"


@pytest.mark.asyncio
async def test_adapt_cv_injects_retry_feedback():
    """When retry_feedback is provided, it must appear in the prompt."""
    original = make_schema()
    mock_output = make_adaptation_output()
    captured_inputs = {}

    async def capture(inputs):
        captured_inputs.update(inputs)
        return mock_output

    with patch("backend.adapter.adapter._chain") as mock_chain:
        mock_chain.ainvoke = capture
        await adapt_cv(
            original,
            "JD text",
            "en",
            retry_feedback=["Invented bullet about ML"],
        )

    assert "retry_section" in captured_inputs
    assert "Invented bullet about ML" in captured_inputs["retry_section"]


@pytest.mark.asyncio
async def test_adapt_cv_no_retry_section_on_first_attempt():
    """Without retry_feedback, the retry_section should be empty string."""
    original = make_schema()
    mock_output = make_adaptation_output()
    captured_inputs = {}

    async def capture(inputs):
        captured_inputs.update(inputs)
        return mock_output

    with patch("backend.adapter.adapter._chain") as mock_chain:
        mock_chain.ainvoke = capture
        await adapt_cv(original, "JD text", "en", retry_feedback=None)

    assert captured_inputs.get("retry_section") == ""


@pytest.mark.asyncio
async def test_adapt_cv_passes_language():
    original = make_schema()
    mock_output = make_adaptation_output()
    captured_inputs = {}

    async def capture(inputs):
        captured_inputs.update(inputs)
        return mock_output

    with patch("backend.adapter.adapter._chain") as mock_chain:
        mock_chain.ainvoke = capture
        await adapt_cv(original, "JD", "es")

    assert captured_inputs.get("output_language") == "es"


@pytest.mark.asyncio
async def test_adapt_cv_propagates_llm_errors():
    original = make_schema()
    with patch("backend.adapter.adapter._chain") as mock_chain:
        mock_chain.ainvoke = AsyncMock(side_effect=RuntimeError("LLM overloaded"))
        with pytest.raises(RuntimeError, match="LLM overloaded"):
            await adapt_cv(original, "JD text", "en")
