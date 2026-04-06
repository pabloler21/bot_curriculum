# tests/test_ranker.py
import io
import os
import uuid
from datetime import date
from unittest.mock import AsyncMock, patch

import zvec
from fastapi.testclient import TestClient

from backend.jobs import Job
from backend.ranker import cosine_similarity, embed_text, get_jobs_collection, rank_jobs
from backend.sessions import cv_sessions
from src.main import app


def test_embed_text_returns_list_of_floats():
    result = embed_text("Python developer with FastAPI experience")
    assert isinstance(result, list)
    assert len(result) > 0
    assert all(isinstance(x, float) for x in result)


def test_embed_text_consistent_length():
    a = embed_text("hello world")
    b = embed_text("completely different sentence about machine learning")
    assert len(a) == len(b)


def test_cosine_similarity_identical_vectors():
    v = [1.0, 0.0, 0.5]
    assert abs(cosine_similarity(v, v) - 1.0) < 1e-6


def test_cosine_similarity_orthogonal_vectors():
    a = [1.0, 0.0]
    b = [0.0, 1.0]
    assert abs(cosine_similarity(a, b)) < 1e-6


def test_rank_jobs_returns_sorted_by_similarity():
    cv_embedding = embed_text("Python FastAPI developer")
    jobs = [
        Job(id="1", title="Java Developer", company="Co", location="Remote",
            employment_type="full_time", salary_range=None,
            description="Java Spring Boot microservices", tags=[],
            url="https://example.com/1", posted_at=date(2025, 1, 1)),
        Job(id="2", title="Python Backend", company="Co", location="Remote",
            employment_type="full_time", salary_range=None,
            description="Python FastAPI REST API development", tags=[],
            url="https://example.com/2", posted_at=date(2025, 1, 1)),
    ]
    results = rank_jobs(cv_embedding, jobs)
    assert len(results) == 2
    # Python job should rank higher than Java job
    assert results[0][0].id == "2"
    # Scores are between 0 and 1
    assert all(0.0 <= score <= 1.0 for _, score in results)
    # Sorted descending
    assert results[0][1] >= results[1][1]


jobs_client = TestClient(app)


def make_test_job(job_id: str, description: str) -> Job:
    return Job(
        id=job_id,
        title=f"Job {job_id}",
        company="Test Co",
        location="Remote",
        employment_type="full_time",
        salary_range=None,
        description=description,
        tags=[],
        url=f"https://example.com/{job_id}",
        posted_at=date(2025, 1, 1),
    )


def test_get_jobs_ranked_without_token_returns_unranked():
    test_jobs = [
        make_test_job("1", "Python FastAPI developer"),
        make_test_job("2", "Java Spring developer"),
    ]
    fetch_patch = patch(
        "src.routes.jobs.fetch_jobs", new_callable=AsyncMock, return_value=test_jobs
    )
    with fetch_patch:
        response = jobs_client.get("/jobs/ranked")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(job["similarity_score"] is None for job in data)


def test_get_jobs_ranked_with_valid_token_returns_ranked():
    cv_sessions.clear()
    test_jobs = [
        make_test_job("1", "Java Spring Boot microservices developer"),
        make_test_job("2", "Python FastAPI REST API senior engineer"),
    ]
    fetch_patch = patch(
        "src.routes.jobs.fetch_jobs", new_callable=AsyncMock, return_value=test_jobs
    )
    extract_patch = patch(
        "src.routes.session.extract_text", return_value="Python FastAPI developer"
    )
    with fetch_patch, extract_patch:
        post_res = jobs_client.post(
            "/session",
            files={"file": ("cv.pdf", io.BytesIO(b"data"), "application/pdf")},
        )
    token = post_res.json()["token"]

    with fetch_patch:
        response = jobs_client.get(f"/jobs/ranked?token={token}")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert all(job["similarity_score"] is not None for job in data)
    # Python job should rank higher (or at least scores are present)
    scores = [job["similarity_score"] for job in data]
    assert all(0.0 <= s <= 1.0 for s in scores)
    # Sorted descending
    assert scores[0] >= scores[1]


def test_get_jobs_ranked_with_malformed_token_returns_400():
    fetch_patch = patch(
        "src.routes.jobs.fetch_jobs", new_callable=AsyncMock, return_value=[]
    )
    with fetch_patch:
        response = jobs_client.get("/jobs/ranked?token=not-a-valid-uuid")
    assert response.status_code == 400
    data = response.json()
    assert data["code"] == "invalid_token"


def test_get_jobs_ranked_with_expired_token_returns_unranked():
    test_jobs = [make_test_job("1", "Python developer")]
    # Use a valid UUID that doesn't exist as a session
    fake_token = str(uuid.uuid4())
    fetch_patch = patch(
        "src.routes.jobs.fetch_jobs", new_callable=AsyncMock, return_value=test_jobs
    )
    with fetch_patch:
        response = jobs_client.get(f"/jobs/ranked?token={fake_token}")
    assert response.status_code == 200
    data = response.json()
    assert all(job["similarity_score"] is None for job in data)


def test_get_jobs_collection_creates_directory(tmp_path, monkeypatch):
    path = str(tmp_path / "test_zvec")
    monkeypatch.setattr("backend.ranker._ZVEC_PATH", path)
    monkeypatch.setattr("backend.ranker._collection", None)
    col = get_jobs_collection()
    assert col is not None
    assert os.path.exists(path)


def test_get_jobs_collection_reopens_existing(tmp_path, monkeypatch):
    import gc

    import backend.ranker as ranker_module

    path = str(tmp_path / "test_zvec")
    monkeypatch.setattr("backend.ranker._ZVEC_PATH", path)
    monkeypatch.setattr("backend.ranker._collection", None)
    col1 = get_jobs_collection()
    # Release the file lock: clear the module-level reference first, then GC
    ranker_module._collection = None
    del col1
    gc.collect()
    # Reset singleton so get_jobs_collection() will reopen
    monkeypatch.setattr("backend.ranker._collection", None)
    col2 = get_jobs_collection()
    assert col2 is not None


def test_get_jobs_collection_returns_singleton(tmp_path, monkeypatch):
    path = str(tmp_path / "test_zvec")
    monkeypatch.setattr("backend.ranker._ZVEC_PATH", path)
    monkeypatch.setattr("backend.ranker._collection", None)
    col1 = get_jobs_collection()
    col2 = get_jobs_collection()
    assert col1 is col2
