# tests/test_jobs.py
import pytest
from datetime import date
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
