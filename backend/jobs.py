# backend/jobs.py
import logging
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from typing import Optional

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self._parts.append(data)

    def get_text(self) -> str:
        return "".join(self._parts)


def strip_html(html: str) -> str:
    """Strip HTML tags from a string, returning plain text."""
    if not html:
        return html
    stripper = _HTMLStripper()
    stripper.feed(html)
    return stripper.get_text()


class Job(BaseModel):
    id: str
    title: str
    company: str
    location: str
    employment_type: str
    salary_range: Optional[str] = None
    description: str
    tags: list[str]
    url: str
    posted_at: date


REMOTIVE_URL = "https://remotive.com/api/remote-jobs"
REMOTIVE_PARAMS = {"category": "software-dev", "limit": 100}
CACHE_TTL_SECONDS = 900  # 15 minutes

# Module-level cache: {"data": (list[Job], datetime) | None}
_cache: dict = {"data": None}


def _parse_date(value: str) -> date:
    """Parse ISO datetime or date string to date."""
    try:
        return datetime.fromisoformat(value).date()
    except (ValueError, AttributeError):
        return date.today()


def _map_job(raw: dict) -> Job:
    return Job(
        id=str(raw["id"]),
        title=raw.get("title", ""),
        company=raw.get("company_name", ""),
        location=raw.get("candidate_required_location", "Remote"),
        employment_type=raw.get("job_type", "full_time"),
        salary_range=raw.get("salary") or None,
        description=strip_html(raw.get("description", "")),
        tags=raw.get("tags", []),
        url=raw.get("url", ""),
        posted_at=_parse_date(raw.get("publication_date", "")),
    )


async def fetch_jobs() -> list[Job]:
    """Return cached job list, fetching from Remotive if stale."""
    cached = _cache["data"]
    if cached is not None:
        jobs, ts = cached
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        if age < CACHE_TTL_SECONDS:
            logger.debug("[jobs] Returning %d cached jobs (age=%.0fs)", len(jobs), age)
            return jobs

    logger.info("[jobs] Fetching fresh job listings from Remotive")
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(REMOTIVE_URL, params=REMOTIVE_PARAMS)
        response.raise_for_status()
        data = response.json()

    jobs = [_map_job(raw) for raw in data.get("jobs", [])]

    from backend.ranker import upsert_job as _upsert_job  # noqa: PLC0415 lazy
    for job in jobs:
        try:
            _upsert_job(job)
        except Exception:
            logger.warning(  # noqa: TRY400
                "[jobs] Failed to upsert job %s into Zvec", job.id, exc_info=True
            )

    _cache["data"] = (jobs, datetime.now(timezone.utc))
    logger.info("[jobs] Cached %d jobs", len(jobs))
    return jobs
