# backend/jobs.py
import logging
from datetime import date, datetime
from html.parser import HTMLParser
from typing import Optional

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
    salary_range: Optional[str]
    description: str
    tags: list[str]
    url: str
    posted_at: date
