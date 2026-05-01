# tests/test_adapter_pipeline.py
"""Tests for backend/adapter/pipeline.py — orchestrator integration."""
from unittest.mock import AsyncMock, patch

import pytest

from backend.schemas import (
    CVSchema,
    PipelineStatus,
    WorkExperience,
)


def make_schema(bullets=None) -> CVSchema:
    return CVSchema(
        candidate_name="Jane Doe",
        experiences=[
            WorkExperience(
                company="Acme",
                role="Dev",
                start_date="2020",
                bullets=bullets or ["Real bullet from original CV"],
            )
        ],
        skills=["Python"],
        education=[],
        raw_text_hash="abc123",
    )


@pytest.mark.asyncio
async def test_pipeline_happy_path_returns_completed():
    """Full happy path: extract → adapt → validate (all pass) → cover letter → done."""
    original = make_schema()
    adapted = make_schema(["Adapted but still close to original bullet"])

    with patch("backend.adapter.pipeline.extract_schema", new_callable=AsyncMock) as mock_extract, \
         patch("backend.adapter.pipeline.adapt_cv", new_callable=AsyncMock) as mock_adapt, \
         patch("backend.adapter.pipeline.validate_adaptation") as mock_validate, \
         patch("backend.adapter.pipeline.generate_cover_letter", new_callable=AsyncMock) as mock_cover, \
         patch("backend.adapter.pipeline.render_pdf") as mock_render:

        mock_extract.return_value = original
        mock_adapt.return_value = (adapted, [])
        mock_validate.return_value = []  # no suspicious bullets
        mock_cover.return_value = "Dear Hiring Manager, I am excited..."
        mock_render.return_value = b"%PDF-1.4"

        result, pdf = await __import__("backend.adapter.pipeline", fromlist=["run_pipeline"]).run_pipeline(
            cv_text="Jane Doe's CV content...",
            job_description="We are looking for a Python developer with FastAPI experience.",
        )

    assert result.status == PipelineStatus.COMPLETED
    assert result.adapted_schema is not None
    assert result.cover_letter is not None
    assert pdf == b"%PDF-1.4"
    assert result.suspicious_bullets == []
    assert result.retries == 0


@pytest.mark.asyncio
async def test_pipeline_failed_extract_returns_error():
    """Stage 1 failure → FAILED_EXTRACT, no credit consumed."""
    with patch("backend.adapter.pipeline.extract_schema", new_callable=AsyncMock) as mock_extract:
        mock_extract.side_effect = RuntimeError("PDF is image-only")

        from backend.adapter.pipeline import run_pipeline
        result, pdf = await run_pipeline("bad cv", "some jd")

    assert result.status == PipelineStatus.FAILED_EXTRACT
    assert "image-only" in result.error_message
    assert pdf is None


@pytest.mark.asyncio
async def test_pipeline_failed_adapt_after_all_retries():
    """Stage 2 fails all 3 attempts → FAILED_ADAPT."""
    original = make_schema()

    with patch("backend.adapter.pipeline.extract_schema", new_callable=AsyncMock) as mock_extract, \
         patch("backend.adapter.pipeline.adapt_cv", new_callable=AsyncMock) as mock_adapt:

        mock_extract.return_value = original
        mock_adapt.side_effect = RuntimeError("LLM structured output failed")

        from backend.adapter.pipeline import run_pipeline
        result, pdf = await run_pipeline("cv text", "jd text")

    assert result.status == PipelineStatus.FAILED_ADAPT
    assert result.retries == 2  # 2 retries after initial failure
    assert pdf is None


@pytest.mark.asyncio
async def test_pipeline_partial_after_retry_still_suspicious():
    """If suspicious bullets remain after max retries → PARTIAL with warning."""
    original = make_schema()
    adapted = make_schema(["Suspicious invented bullet"])

    with patch("backend.adapter.pipeline.extract_schema", new_callable=AsyncMock) as mock_extract, \
         patch("backend.adapter.pipeline.adapt_cv", new_callable=AsyncMock) as mock_adapt, \
         patch("backend.adapter.pipeline.validate_adaptation") as mock_validate, \
         patch("backend.adapter.pipeline.generate_cover_letter", new_callable=AsyncMock) as mock_cover, \
         patch("backend.adapter.pipeline.render_pdf") as mock_render:

        mock_extract.return_value = original
        mock_adapt.return_value = (adapted, [])
        mock_validate.return_value = ["Suspicious invented bullet"]  # always suspicious
        mock_cover.return_value = "Cover letter text"
        mock_render.return_value = b"%PDF"

        from backend.adapter.pipeline import run_pipeline
        result, pdf = await run_pipeline("cv", "jd")

    assert result.status == PipelineStatus.PARTIAL
    assert "Suspicious invented bullet" in result.suspicious_bullets
    assert result.retries == 2  # retried max times


@pytest.mark.asyncio
async def test_pipeline_retries_adapt_with_feedback():
    """After validation failure, adapt_cv is called again with retry_feedback."""
    original = make_schema()
    adapted = make_schema(["Adapted bullet"])
    suspicious = ["Adapted bullet"]
    adapt_calls: list[dict] = []

    async def mock_adapt_fn(schema, job_description, output_language, retry_feedback=None):
        adapt_calls.append({"retry_feedback": retry_feedback})
        return (adapted, [])

    with patch("backend.adapter.pipeline.extract_schema", new_callable=AsyncMock) as mock_extract, \
         patch("backend.adapter.pipeline.adapt_cv", side_effect=mock_adapt_fn), \
         patch("backend.adapter.pipeline.validate_adaptation") as mock_validate, \
         patch("backend.adapter.pipeline.generate_cover_letter", new_callable=AsyncMock, return_value="cover"), \
         patch("backend.adapter.pipeline.render_pdf", return_value=b""):

        mock_extract.return_value = original
        # First validation: suspicious; second: all clear
        mock_validate.side_effect = [suspicious, []]

        from backend.adapter.pipeline import run_pipeline
        result, _ = await run_pipeline("cv text", "jd text")

    # adapt_cv called twice: initial + 1 retry
    assert len(adapt_calls) == 2
    # First call: no retry_feedback
    assert adapt_calls[0]["retry_feedback"] is None
    # Second call: feedback contains suspicious bullets
    assert adapt_calls[1]["retry_feedback"] == suspicious
    assert result.status == PipelineStatus.COMPLETED



@pytest.mark.asyncio
async def test_pipeline_cover_letter_failure_is_non_fatal():
    """Cover letter generation failure should not fail the pipeline."""
    original = make_schema()
    adapted = make_schema(["Real adapted bullet"])

    with patch("backend.adapter.pipeline.extract_schema", new_callable=AsyncMock) as mock_extract, \
         patch("backend.adapter.pipeline.adapt_cv", new_callable=AsyncMock) as mock_adapt, \
         patch("backend.adapter.pipeline.validate_adaptation") as mock_validate, \
         patch("backend.adapter.pipeline.generate_cover_letter", new_callable=AsyncMock) as mock_cover, \
         patch("backend.adapter.pipeline.render_pdf") as mock_render:

        mock_extract.return_value = original
        mock_adapt.return_value = (adapted, [])
        mock_validate.return_value = []
        mock_cover.side_effect = RuntimeError("Cover letter LLM timeout")
        mock_render.return_value = b"%PDF"

        from backend.adapter.pipeline import run_pipeline
        result, pdf = await run_pipeline("cv", "jd")

    assert result.status == PipelineStatus.COMPLETED
    assert result.cover_letter is None  # not delivered but not a failure
    assert pdf is not None
