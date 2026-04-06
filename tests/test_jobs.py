# tests/test_jobs.py
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import httpx
import respx

from backend.jobs import Job, strip_html


def test_strip_html_removes_tags():
    assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"


def test_strip_html_plain_text_unchanged():
    assert strip_html("plain text") == "plain text"


def test_strip_html_empty():
    assert strip_html("") == ""


def test_strip_html_nested_tags():
    assert strip_html("<div><ul><li>item</li></ul></div>") == "item"


def test_job_model_fields():
    job = Job(
        id="123",
        title="Backend Engineer",
        company="Acme Corp",
        location="Remote",
        employment_type="full_time",
        salary_range=None,
        description="Python dev needed.",
        tags=["python", "fastapi"],
        url="https://example.com/job/123",
        posted_at=date(2025, 1, 15),
    )
    assert job.id == "123"
    assert job.tags == ["python", "fastapi"]
    assert job.salary_range is None


def test_job_model_serializable():
    import json
    job = Job(
        id="1",
        title="SWE",
        company="Co",
        location="Remote",
        employment_type="contract",
        salary_range="$80k-$100k",
        description="desc",
        tags=[],
        url="https://example.com",
        posted_at=date(2025, 3, 1),
    )
    data = job.model_dump(mode="json")
    assert data["posted_at"] == "2025-03-01"
    json.dumps(data)  # must not raise


REMOTIVE_SAMPLE = {
    "jobs": [
        {
            "id": 1,
            "title": "Python Developer",
            "company_name": "TechCorp",
            "candidate_required_location": "Worldwide",
            "job_type": "full_time",
            "salary": "$80k - $110k",
            "description": "<p>We need a <b>Python</b> dev.</p>",
            "tags": ["python", "django"],
            "url": "https://remotive.com/job/1",
            "publication_date": "2025-03-15T10:00:00",
        }
    ]
}


@respx.mock
async def test_fetch_jobs_returns_normalized_jobs():
    from backend.jobs import _cache, fetch_jobs
    _cache["data"] = None  # clear cache

    respx.get("https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(200, json=REMOTIVE_SAMPLE)
    )

    jobs = await fetch_jobs()
    assert len(jobs) == 1
    assert jobs[0].title == "Python Developer"
    assert jobs[0].company == "TechCorp"
    assert jobs[0].description == "We need a Python dev."  # HTML stripped
    assert jobs[0].tags == ["python", "django"]
    assert jobs[0].posted_at == date(2025, 3, 15)
    assert jobs[0].url == "https://remotive.com/job/1"


@respx.mock
async def test_fetch_jobs_uses_cache():
    from backend.jobs import Job, _cache, fetch_jobs
    # Prime cache with a recent timestamp
    _cache["data"] = (
        [
            Job(
                id="99", title="Cached Job", company="CacheCo",
                location="Remote", employment_type="full_time",
                description="cached", tags=[],
                url="https://example.com", posted_at=date(2025, 1, 1),
            )
        ],
        datetime.now(timezone.utc),
    )

    # No HTTP mock — if fetch_jobs makes a real call it will raise
    jobs = await fetch_jobs()
    assert jobs[0].title == "Cached Job"


@respx.mock
async def test_fetch_jobs_invalidates_stale_cache():
    from backend.jobs import _cache, fetch_jobs
    old_time = datetime.now(timezone.utc) - timedelta(minutes=20)
    _cache["data"] = ([], old_time)

    respx.get("https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(200, json=REMOTIVE_SAMPLE)
    )

    jobs = await fetch_jobs()
    assert len(jobs) == 1
    assert jobs[0].title == "Python Developer"


@respx.mock
async def test_fetch_jobs_raises_on_http_error():
    from backend.jobs import _cache, fetch_jobs
    _cache["data"] = None

    respx.get("https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(503)
    )

    try:
        await fetch_jobs()
        assert False, "Should have raised"
    except httpx.HTTPStatusError:
        pass


def test_get_jobs_returns_200(client):
    sample_jobs = [
        Job(
            id="1", title="Dev", company="Co", location="Remote",
            employment_type="full_time",
            description="desc", tags=["python"],
            url="https://example.com", posted_at=date(2025, 3, 1),
        )
    ]
    with patch("src.routes.jobs.fetch_jobs", new=AsyncMock(return_value=sample_jobs)):
        response = client.get("/jobs")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["title"] == "Dev"
    assert data[0]["posted_at"] == "2025-03-01"


def test_get_jobs_returns_502_on_upstream_error(client):
    import httpx as _httpx

    async def boom():
        raise _httpx.RequestError("connection failed")

    with patch("src.routes.jobs.fetch_jobs", new=boom):
        response = client.get("/jobs")
    assert response.status_code == 502
    body = response.json()
    assert body["code"] == "upstream_error"


def test_get_jobs_returns_500_on_unexpected_error(client):
    async def explode():
        raise ValueError("unexpected bug")

    with patch("src.routes.jobs.fetch_jobs", new=explode):
        response = client.get("/jobs")
    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"


@respx.mock
async def test_fetch_jobs_calls_upsert_for_each_job():
    from unittest.mock import patch

    from backend.jobs import _cache, fetch_jobs
    _cache["data"] = None

    respx.get("https://remotive.com/api/remote-jobs").mock(
        return_value=httpx.Response(200, json=REMOTIVE_SAMPLE)
    )

    with patch("backend.ranker.upsert_job") as mock_upsert:
        jobs = await fetch_jobs()

    assert mock_upsert.call_count == len(jobs)
    called_ids = {c.args[0].id for c in mock_upsert.call_args_list}
    assert jobs[0].id in called_ids
