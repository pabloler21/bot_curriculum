# tests/test_interview_route.py
"""Tests for POST /interview."""
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.schemas import InterviewQuestion
from src.main import app
from src.routes.interview import MAX_PAYLOAD_CHARS
from src.routes.interview import limiter as interview_limiter

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_limiters():
    """Reset rate limiters before every test — 3/min would trip the suite itself."""
    app.state.limiter.reset()
    interview_limiter.reset()

_USER_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
_JD = "We are looking for a backend engineer with strong Python and API design skills."

_SCHEMA = {
    "candidate_name": "Jane Doe",
    "experiences": [
        {
            "company": "Acme Corp",
            "role": "Software Engineer",
            "start_date": "Jan 2020",
            "bullets": ["Built REST API"],
            "technologies": ["Python"],
            "metrics": [],
        }
    ],
    "skills": ["Python"],
    "education": [],
}

_QUESTION = InterviewQuestion(
    question="Walk me through the REST API you built.",
    kind="technical",
    why_asked="The JD asks for API design.",
    suggested_answer="At Acme Corp I…",
    based_on="Software Engineer at Acme Corp",
)


def body(**overrides):
    payload = {
        "adapted_schema": _SCHEMA,
        "job_description": _JD,
        "gaps": [],
        "output_language": "en",
    }
    payload.update(overrides)
    return payload


class TestAuth:
    def test_unauthenticated_returns_401(self):
        response = client.post("/interview", json=body())
        assert response.status_code == 401


class TestHappyPath:
    def test_returns_questions(self):
        with patch("backend.auth.get_current_user", return_value=_USER_ID), \
             patch(
                 "src.routes.interview.generate_interview_prep",
                 new=AsyncMock(return_value=[_QUESTION]),
             ):
            response = client.post(
                "/interview",
                json=body(),
                headers={"Authorization": "Bearer valid.token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert len(data["questions"]) == 1
        assert data["questions"][0]["kind"] == "technical"
        assert data["questions"][0]["question"].startswith("Walk me through")

    def test_gaps_are_forwarded_to_the_generator(self):
        gap = {
            "jd_requirement": "Kubernetes",
            "confidence": "hard",
            "suggestion": "Deploy something to a cluster",
        }
        mock_gen = AsyncMock(return_value=[_QUESTION])
        with patch("backend.auth.get_current_user", return_value=_USER_ID), \
             patch("src.routes.interview.generate_interview_prep", new=mock_gen):
            client.post(
                "/interview",
                json=body(gaps=[gap]),
                headers={"Authorization": "Bearer valid.token"},
            )

        forwarded_gaps = mock_gen.call_args.kwargs["gaps"]
        assert len(forwarded_gaps) == 1
        assert forwarded_gaps[0].jd_requirement == "Kubernetes"


class TestValidation:
    def test_short_job_description_returns_422(self):
        with patch("backend.auth.get_current_user", return_value=_USER_ID):
            response = client.post(
                "/interview",
                json=body(job_description="too short"),
                headers={"Authorization": "Bearer valid.token"},
            )
        assert response.status_code == 422

    def test_oversized_payload_returns_413(self):
        huge_bullet = "x" * (MAX_PAYLOAD_CHARS + 1)
        schema = {**_SCHEMA}
        schema["experiences"] = [
            {**_SCHEMA["experiences"][0], "bullets": [huge_bullet]}
        ]
        with patch("backend.auth.get_current_user", return_value=_USER_ID):
            response = client.post(
                "/interview",
                json=body(adapted_schema=schema),
                headers={"Authorization": "Bearer valid.token"},
            )
        assert response.status_code == 413


class TestFailures:
    def test_generator_failure_returns_502(self):
        with patch("backend.auth.get_current_user", return_value=_USER_ID), \
             patch(
                 "src.routes.interview.generate_interview_prep",
                 new=AsyncMock(side_effect=RuntimeError("API down")),
             ):
            response = client.post(
                "/interview",
                json=body(),
                headers={"Authorization": "Bearer valid.token"},
            )
        assert response.status_code == 502
