# backend/schemas.py
"""
Pydantic models for the Aurea adaptation pipeline.

CVSchema is the ground truth of a candidate's CV — extracted once, never invented.
AdaptationResult is the final output of the 3-stage pipeline.
"""
import hashlib
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Metric(BaseModel):
    value: str = Field(description="Numeric value, e.g. '30%', '$2M', '50+'")
    context: str = Field(description="What the metric refers to, e.g. 'increased revenue by'")


class WorkExperience(BaseModel):
    company: str
    role: str
    start_date: str
    end_date: str | None = None
    bullets: list[str] = Field(
        description="Achievement/responsibility bullets exactly as in the CV"
    )
    technologies: list[str] = Field(
        default_factory=list,
        description="Technologies explicitly mentioned in this role",
    )
    metrics: list[Metric] = Field(
        default_factory=list,
        description="Quantified achievements extracted from bullets",
    )


class Education(BaseModel):
    institution: str
    degree: str
    field: str | None = None
    year: str | None = None


class CVSchema(BaseModel):
    candidate_name: str
    contact_info: str | None = Field(
        None,
        description="Email, phone, LinkedIn, GitHub as found in the CV — verbatim",
    )
    summary: str | None = Field(None, description="Professional summary or objective, if present")
    experiences: list[WorkExperience]
    skills: list[str] = Field(description="All skills explicitly listed in the CV")
    education: list[Education]
    languages: list[str] = Field(
        default_factory=list,
        description="Natural languages with proficiency if stated, e.g. 'Spanish (native)'",
    )
    certifications: list[str] = Field(
        default_factory=list,
        description="Certifications and courses explicitly listed",
    )
    raw_text_hash: str = Field(
        default="",
        description="SHA-256 of the original CV text — set programmatically, leave empty",
    )


class Gap(BaseModel):
    jd_requirement: str = Field(description="JD requirement not covered by the CV")
    confidence: Literal["hard", "soft"] = Field(
        description="'hard' = explicitly required, 'soft' = nice to have"
    )
    suggestion: str = Field(description="Concrete action the candidate could take to address this")


class PipelineStatus(str, Enum):
    CREATED = "created"
    EXTRACTING = "extracting"
    ADAPTING = "adapting"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED_EXTRACT = "failed_extract"
    FAILED_ADAPT = "failed_adapt"
    PARTIAL = "partial"


class AdaptationResult(BaseModel):
    run_id: str
    status: PipelineStatus
    adapted_schema: CVSchema | None = None
    gaps: list[Gap] = Field(default_factory=list)
    cover_letter: str | None = None
    suspicious_bullets: list[str] = Field(
        default_factory=list,
        description="Bullets that failed similarity validation — shown with warning in UI",
    )
    error_message: str | None = None
    retries: int = 0


def compute_hash(text: str) -> str:
    """Return SHA-256 hex digest of text. Used as CV audit trail."""
    return hashlib.sha256(text.encode()).hexdigest()
