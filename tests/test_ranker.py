# tests/test_ranker.py
from datetime import date

from backend.jobs import Job
from backend.ranker import cosine_similarity, embed_text, rank_jobs


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
