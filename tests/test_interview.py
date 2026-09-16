# tests/test_interview.py
"""Tests for backend/adapter/interview.py — interview prep generation."""
from unittest.mock import AsyncMock, patch

import pytest

from backend.adapter.interview import _InterviewOutput, generate_interview_prep
from backend.schemas import CVSchema, Gap, InterviewQuestion, WorkExperience


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


def make_gap() -> Gap:
    return Gap(
        jd_requirement="Kubernetes experience",
        confidence="hard",
        suggestion="Deploy a side project to a managed cluster",
    )


def make_output(questions=None) -> _InterviewOutput:
    return _InterviewOutput(
        questions=questions
        or [
            InterviewQuestion(
                question="Walk me through how you reduced latency by 40%.",
                kind="technical",
                why_asked="The JD emphasizes performance work.",
                suggested_answer="At Acme Corp I profiled the API and…",
                based_on="Software Engineer at Acme Corp",
            )
        ]
    )


@pytest.mark.asyncio
async def test_returns_list_of_questions():
    with patch("backend.adapter.interview._chain") as mock_chain:
        mock_chain.ainvoke = AsyncMock(return_value=make_output())
        questions = await generate_interview_prep(make_schema(), "JD text", [make_gap()])

    assert isinstance(questions, list)
    assert len(questions) == 1
    assert isinstance(questions[0], InterviewQuestion)
    assert questions[0].kind == "technical"


@pytest.mark.asyncio
async def test_gaps_are_injected_into_the_prompt():
    with patch("backend.adapter.interview._chain") as mock_chain:
        mock_chain.ainvoke = AsyncMock(return_value=make_output())
        await generate_interview_prep(make_schema(), "JD text", [make_gap()])

    payload = mock_chain.ainvoke.call_args[0][0]
    assert "Kubernetes experience" in payload["gaps_section"]
    assert "managed cluster" in payload["gaps_section"]


@pytest.mark.asyncio
async def test_no_gaps_still_produces_a_gaps_section():
    with patch("backend.adapter.interview._chain") as mock_chain:
        mock_chain.ainvoke = AsyncMock(return_value=make_output())
        await generate_interview_prep(make_schema(), "JD text", [])

    payload = mock_chain.ainvoke.call_args[0][0]
    assert payload["gaps_section"].strip() != ""


@pytest.mark.asyncio
async def test_schema_and_language_reach_the_prompt():
    with patch("backend.adapter.interview._chain") as mock_chain:
        mock_chain.ainvoke = AsyncMock(return_value=make_output())
        await generate_interview_prep(make_schema(), "JD text", [], output_language="es")

    payload = mock_chain.ainvoke.call_args[0][0]
    assert payload["output_language"] == "es"
    assert "Acme Corp" in payload["adapted_schema"]
    assert payload["job_description"] == "JD text"


@pytest.mark.asyncio
async def test_llm_failure_propagates():
    with patch("backend.adapter.interview._chain") as mock_chain:
        mock_chain.ainvoke = AsyncMock(side_effect=RuntimeError("API down"))
        with pytest.raises(RuntimeError, match="API down"):
            await generate_interview_prep(make_schema(), "JD text", [])


@pytest.mark.asyncio
async def test_gap_question_keeps_its_kind():
    output = make_output(
        [
            InterviewQuestion(
                question="You have not used Kubernetes. How would you ramp up?",
                kind="gap",
                why_asked="The JD lists Kubernetes as a hard requirement.",
                suggested_answer="I have not run Kubernetes in production. I have…",
                based_on=None,
            )
        ]
    )
    with patch("backend.adapter.interview._chain") as mock_chain:
        mock_chain.ainvoke = AsyncMock(return_value=output)
        questions = await generate_interview_prep(make_schema(), "JD text", [make_gap()])

    assert questions[0].kind == "gap"
    assert questions[0].based_on is None
