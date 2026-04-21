# tests/test_scorer.py
import io
import uuid
from datetime import date
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.jobs import Job
from backend.scorer import JobMatch, score_job
from backend.sessions import cv_sessions
from src.main import app
from src.routes.jobs import limiter as jobs_limiter
from src.routes.session import limiter as session_limiter

scorer_client = TestClient(app)


def make_job(job_id: str) -> Job:
    return Job(
        id=job_id,
        title="Python Developer",
        company="Test Co",
        location="Remote",
        employment_type="full_time",
        salary_range=None,
        description="Python FastAPI developer needed",
        tags=["python", "fastapi"],
        url=f"https://example.com/{job_id}",
        posted_at=date(2025, 1, 1),
    )


def make_job_match() -> dict:
    return {
        "score": 82,
        "match_level": "strong",
        "matched_skills": ["Python", "FastAPI"],
        "missing_skills": ["Docker"],
        "one_line_summary": "Strong Python match with FastAPI experience needed",
    }


def test_job_match_validates_correctly():
    match = JobMatch(
        score=75,
        match_level="good",
        matched_skills=["Python"],
        missing_skills=["Go"],
        one_line_summary="Good Python match with some gaps",
    )
    assert match.score == 75
    assert match.match_level == "good"


def test_job_match_score_range():
    # score must be 0-100
    match = JobMatch(
        score=0,
        match_level="weak",
        matched_skills=[],
        missing_skills=["everything"],
        one_line_summary="No match found at all",
    )
    assert match.score == 0


@pytest.mark.asyncio
async def test_score_job_returns_job_match():
    job = make_job("1")
    mock_match = JobMatch(**make_job_match())
    with patch("backend.scorer.chain") as mock_chain:
        mock_chain.ainvoke = AsyncMock(return_value=mock_match)
        result = await score_job("Python developer with FastAPI", job)
    assert isinstance(result, JobMatch)
    assert result.score == 82


def setup_function():
    cv_sessions.clear()
    app.state.limiter.reset()
    session_limiter.reset()
    jobs_limiter.reset()


def test_post_jobs_score_no_session_returns_400():
    fake_token = str(uuid.uuid4())
    response = scorer_client.post(
        "/jobs/score",
        json={"token": fake_token, "limit": 5},
    )
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "no_session"


def test_post_jobs_score_malformed_token_returns_400():
    response = scorer_client.post(
        "/jobs/score",
        json={"token": "not-a-uuid", "limit": 5},
    )
    assert response.status_code == 400


def test_post_jobs_score_with_valid_session_returns_results():
    from unittest.mock import MagicMock

    cv_sessions.clear()
    with patch("src.routes.session.extract_text", return_value="Python developer"):
        post_res = scorer_client.post(
            "/session",
            files={"file": ("cv.pdf", io.BytesIO(b"data"), "application/pdf")},
        )
    token = post_res.json()["token"]

    test_jobs = [make_job("1"), make_job("2"), make_job("3")]
    mock_match = JobMatch(**make_job_match())

    mock_results = [MagicMock(id=j.id) for j in test_jobs]
    mock_col = MagicMock()
    mock_col.query.return_value = mock_results

    patch_fetch = patch(
        "src.routes.jobs.fetch_jobs", new_callable=AsyncMock, return_value=test_jobs
    )
    patch_score = patch(
        "src.routes.jobs.score_job", new_callable=AsyncMock, return_value=mock_match
    )
    patch_col = patch("src.routes.jobs.get_jobs_collection", return_value=mock_col)
    with patch_fetch, patch_score, patch_col:
        response = scorer_client.post(
            "/jobs/score",
            json={"token": token, "limit": 3},
        )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 3
    assert data[0]["score"] == 82


def test_post_jobs_score_caches_results():
    from unittest.mock import MagicMock

    cv_sessions.clear()
    with patch("src.routes.session.extract_text", return_value="Python developer"):
        post_res = scorer_client.post(
            "/session",
            files={"file": ("cv.pdf", io.BytesIO(b"data"), "application/pdf")},
        )
    token = post_res.json()["token"]

    test_jobs = [make_job("1")]
    mock_match = JobMatch(**make_job_match())

    mock_col = MagicMock()
    mock_col.query.return_value = [MagicMock(id="1")]

    patch_fetch = patch(
        "src.routes.jobs.fetch_jobs", new_callable=AsyncMock, return_value=test_jobs
    )
    patch_score = patch(
        "src.routes.jobs.score_job", new_callable=AsyncMock, return_value=mock_match
    )
    patch_col = patch("src.routes.jobs.get_jobs_collection", return_value=mock_col)
    with patch_fetch, patch_score as mock_score, patch_col:
        # First call
        scorer_client.post("/jobs/score", json={"token": token, "limit": 1})
        # Second call — should use cache, score_job not called again
        scorer_client.post("/jobs/score", json={"token": token, "limit": 1})
    assert mock_score.call_count == 1  # only called once due to caching


def test_score_jobs_uses_zvec_for_top_n(client):
    import io
    from datetime import date
    from unittest.mock import AsyncMock, MagicMock, patch

    from backend.jobs import Job

    test_jobs = [
        Job(
            id="j1",
            title="Python Dev",
            company="Co",
            location="Remote",
            employment_type="full_time",
            description="Python FastAPI",
            tags=[],
            url="https://example.com/j1",
            posted_at=date(2025, 1, 1),
        ),
        Job(
            id="j2",
            title="Java Dev",
            company="Co",
            location="Remote",
            employment_type="full_time",
            description="Java Spring",
            tags=[],
            url="https://example.com/j2",
            posted_at=date(2025, 1, 1),
        ),
    ]

    mock_zvec_result = MagicMock()
    mock_zvec_result.id = "j1"
    mock_col = MagicMock()
    mock_col.query.return_value = [mock_zvec_result]

    mock_match = MagicMock()
    mock_match.model_dump.return_value = {
        "score": 82,
        "match_level": "good",
        "matched_skills": ["Python"],
        "missing_skills": [],
        "one_line_summary": "Good match",
    }

    extract_patch = patch(
        "src.routes.session.extract_text", return_value="Python dev"
    )
    fetch_patch = patch(
        "src.routes.jobs.fetch_jobs",
        new_callable=AsyncMock,
        return_value=test_jobs,
    )
    col_patch = patch(
        "src.routes.jobs.get_jobs_collection", return_value=mock_col
    )
    score_patch = patch(
        "src.routes.jobs.score_job",
        new_callable=AsyncMock,
        return_value=mock_match,
    )

    with extract_patch, fetch_patch:
        post_res = client.post(
            "/session",
            files={"file": ("cv.pdf", io.BytesIO(b"data"), "application/pdf")},
        )
    token = post_res.json()["token"]

    with fetch_patch, col_patch, score_patch:
        response = client.post("/jobs/score", json={"token": token, "limit": 1})

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["job_id"] == "j1"
    assert data[0]["score"] == 82
    assert mock_col.query.called


def test_score_jobs_returns_400_when_no_embedding(client):
    import uuid
    from datetime import datetime, timezone

    from backend.sessions import CVSession, cv_sessions

    # Create a session with no embedding
    token = str(uuid.uuid4())
    session = CVSession(
        token=token,
        cv_text="some text",
        filename="cv.pdf",
        uploaded_at=datetime.now(timezone.utc),
        cv_embedding=[],
    )
    cv_sessions[token] = session

    try:
        response = client.post("/jobs/score", json={"token": token, "limit": 1})
        assert response.status_code == 400
        assert response.json()["code"] == "no_embedding"
    finally:
        cv_sessions.pop(token, None)


def test_post_jobs_score_handles_partial_failure():
    from unittest.mock import MagicMock

    cv_sessions.clear()
    with patch("src.routes.session.extract_text", return_value="Python developer"):
        post_res = scorer_client.post(
            "/session",
            files={"file": ("cv.pdf", io.BytesIO(b"data"), "application/pdf")},
        )
    token = post_res.json()["token"]

    test_jobs = [make_job("1"), make_job("2")]
    mock_match = JobMatch(**make_job_match())

    async def score_side_effect(cv_text, job):
        if job.id == "1":
            raise Exception("LLM failed")
        return mock_match

    mock_col = MagicMock()
    mock_col.query.return_value = [MagicMock(id=j.id) for j in test_jobs]

    patch_fetch = patch(
        "src.routes.jobs.fetch_jobs", new_callable=AsyncMock, return_value=test_jobs
    )
    patch_score = patch("src.routes.jobs.score_job", side_effect=score_side_effect)
    patch_col = patch("src.routes.jobs.get_jobs_collection", return_value=mock_col)
    with patch_fetch, patch_score, patch_col:
        response = scorer_client.post(
            "/jobs/score",
            json={"token": token, "limit": 2},
        )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Job 1 failed → null score
    job1_result = next(r for r in data if r["job_id"] == "1")
    assert job1_result["score"] is None
    # Job 2 succeeded
    job2_result = next(r for r in data if r["job_id"] == "2")
    assert job2_result["score"] == 82
