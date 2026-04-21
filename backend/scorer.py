# backend/scorer.py
import logging
from typing import Literal

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from backend.jobs import Job

load_dotenv()

logger = logging.getLogger(__name__)


class JobMatch(BaseModel):
    score: int = Field(description="Match score 0-100")
    match_level: Literal["strong", "good", "partial", "weak"] = Field(
        description="Overall match level"
    )
    matched_skills: list[str] = Field(description="Skills found in both CV and job")
    missing_skills: list[str] = Field(
        description="Skills required by job but not in CV"
    )
    one_line_summary: str = Field(
        description="One-line summary of the match, max 15 words"
    )


_model = ChatAnthropic(model="claude-haiku-4-5")
_structured_model = _model.with_structured_output(JobMatch)

_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        """You are a technical recruiter evaluating CV-to-job fit.
Analyze the CV and job description. Be concise and accurate.
Score 0-100, identify matched and missing skills, summarize in max 15 words.""",
    ),
    (
        "human",
        """CV:
{cv_text}

Job Title: {job_title}
Company: {company}
Job Description:
{job_description}

Evaluate the match.""",
    ),
])

chain = _prompt | _structured_model


async def score_job(cv_text: str, job: Job) -> JobMatch:
    """Score a CV against a job using Claude. Returns JobMatch."""
    logger.info("[scorer] Scoring job %s (%s)", job.id, job.title)
    result = await chain.ainvoke({
        "cv_text": cv_text,
        "job_title": job.title,
        "company": job.company,
        "job_description": job.description,
    })
    logger.info(
        "[scorer] Job %s scored: %d (%s)", job.id, result.score, result.match_level
    )
    return result
