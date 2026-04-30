# tests/test_adapter_schemas.py
"""Tests for backend/schemas.py — Pydantic model validations."""
import pytest
from pydantic import ValidationError

from backend.schemas import (
    AdaptationResult,
    CVSchema,
    Education,
    Gap,
    Metric,
    PipelineStatus,
    WorkExperience,
    compute_hash,
)


def make_work_experience(**kwargs):
    defaults = {
        "company": "Acme Corp",
        "role": "Software Engineer",
        "start_date": "Jan 2021",
        "end_date": "Dec 2023",
        "bullets": ["Built REST API with FastAPI", "Reduced latency by 40%"],
        "technologies": ["Python", "FastAPI"],
        "metrics": [],
    }
    defaults.update(kwargs)
    return WorkExperience(**defaults)


def make_cv_schema(**kwargs):
    defaults = {
        "candidate_name": "Jane Doe",
        "experiences": [make_work_experience()],
        "skills": ["Python", "FastAPI"],
        "education": [],
    }
    defaults.update(kwargs)
    return CVSchema(**defaults)


class TestMetric:
    def test_valid_metric(self):
        m = Metric(value="30%", context="increased revenue by")
        assert m.value == "30%"
        assert m.context == "increased revenue by"


class TestWorkExperience:
    def test_valid_experience(self):
        exp = make_work_experience()
        assert exp.company == "Acme Corp"
        assert len(exp.bullets) == 2

    def test_optional_end_date(self):
        exp = make_work_experience(end_date=None)
        assert exp.end_date is None

    def test_empty_bullets_allowed(self):
        exp = make_work_experience(bullets=[])
        assert exp.bullets == []


class TestCVSchema:
    def test_valid_schema(self):
        schema = make_cv_schema()
        assert schema.candidate_name == "Jane Doe"
        assert len(schema.experiences) == 1

    def test_optional_fields_default_none(self):
        schema = make_cv_schema()
        assert schema.summary is None
        assert schema.contact_info is None

    def test_default_empty_lists(self):
        schema = make_cv_schema(languages=[], certifications=[])
        assert schema.languages == []
        assert schema.certifications == []

    def test_raw_text_hash_defaults_empty(self):
        schema = make_cv_schema()
        assert schema.raw_text_hash == ""


class TestGap:
    def test_valid_gap_hard(self):
        gap = Gap(
            jd_requirement="3+ years Docker experience",
            confidence="hard",
            suggestion="Add Docker projects to your GitHub",
        )
        assert gap.confidence == "hard"

    def test_valid_gap_soft(self):
        gap = Gap(
            jd_requirement="Familiarity with Kubernetes",
            confidence="soft",
            suggestion="Take a Kubernetes basics course",
        )
        assert gap.confidence == "soft"

    def test_invalid_confidence_raises(self):
        with pytest.raises(ValidationError):
            Gap(
                jd_requirement="X",
                confidence="maybe",  # type: ignore
                suggestion="Y",
            )


class TestPipelineStatus:
    def test_all_statuses_exist(self):
        statuses = [s.value for s in PipelineStatus]
        assert "completed" in statuses
        assert "failed_extract" in statuses
        assert "failed_adapt" in statuses
        assert "partial" in statuses


class TestAdaptationResult:
    def test_minimal_result(self):
        schema = make_cv_schema()
        result = AdaptationResult(
            run_id="run-123",
            status=PipelineStatus.COMPLETED,
            adapted_schema=schema,
        )
        assert result.run_id == "run-123"
        assert result.gaps == []
        assert result.suspicious_bullets == []

    def test_partial_result_has_suspicious_bullets(self):
        schema = make_cv_schema()
        result = AdaptationResult(
            run_id="run-456",
            status=PipelineStatus.PARTIAL,
            adapted_schema=schema,
            suspicious_bullets=["Built a rocket ship with AI"],
        )
        assert len(result.suspicious_bullets) == 1

    def test_failed_result_no_schema(self):
        result = AdaptationResult(
            run_id="run-789",
            status=PipelineStatus.FAILED_EXTRACT,
            error_message="PDF is image-only",
        )
        assert result.adapted_schema is None
        assert result.error_message == "PDF is image-only"


class TestComputeHash:
    def test_returns_64_char_hex(self):
        h = compute_hash("hello world")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_deterministic(self):
        assert compute_hash("abc") == compute_hash("abc")

    def test_different_inputs_different_hashes(self):
        assert compute_hash("abc") != compute_hash("abcd")
