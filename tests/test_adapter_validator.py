# tests/test_adapter_validator.py
"""Tests for backend/adapter/validator.py — similarity-based validation."""
from unittest.mock import patch

from backend.adapter.validator import validate_adaptation
from backend.schemas import CVSchema, WorkExperience


def make_schema(bullets: list[str]) -> CVSchema:
    return CVSchema(
        candidate_name="Test User",
        experiences=[
            WorkExperience(
                company="Acme",
                role="Dev",
                start_date="2020",
                bullets=bullets,
            )
        ],
        skills=[],
        education=[],
    )


class TestValidateAdaptation:
    def test_empty_original_returns_no_suspicious(self):
        """No original bullets → skip validation, return empty list."""
        original = make_schema([])
        adapted = make_schema(["Invented bullet"])
        result = validate_adaptation(original, adapted)
        assert result == []

    def test_empty_adapted_returns_no_suspicious(self):
        original = make_schema(["Real bullet from original CV"])
        adapted = make_schema([])
        result = validate_adaptation(original, adapted)
        assert result == []

    def test_high_similarity_bullet_passes(self):
        """Bullets almost identical to originals should pass."""
        bullet = "Built REST API with FastAPI and Python"
        original = make_schema([bullet])
        # Slightly rephrased — should have high similarity
        adapted = make_schema(["Developed REST API using FastAPI and Python"])

        with patch("backend.adapter.validator.embed_text") as mock_embed, \
             patch("backend.adapter.validator.cosine_similarity") as mock_sim:
            # Simulate high similarity
            mock_embed.return_value = [0.1] * 384
            mock_sim.return_value = 0.90

            result = validate_adaptation(original, adapted)
            assert result == []

    def test_low_similarity_bullet_flagged(self):
        """Bullets semantically far from all originals should be flagged."""
        original = make_schema(["Maintained legacy PHP codebase"])
        adapted = make_schema(["Led ML infrastructure on AWS with Kubernetes"])

        with patch("backend.adapter.validator.embed_text") as mock_embed, \
             patch("backend.adapter.validator.cosine_similarity") as mock_sim:
            mock_embed.return_value = [0.1] * 384
            mock_sim.return_value = 0.30  # below threshold

            result = validate_adaptation(original, adapted)
            assert "Led ML infrastructure on AWS with Kubernetes" in result

    def test_threshold_is_respected(self):
        """Custom threshold changes what passes vs what fails."""
        original = make_schema(["Python dev"])
        adapted = make_schema(["Python dev variation"])

        with patch("backend.adapter.validator.embed_text") as mock_embed, \
             patch("backend.adapter.validator.cosine_similarity") as mock_sim:
            mock_embed.return_value = [0.1] * 384
            mock_sim.return_value = 0.70  # above default 0.65, below custom 0.80

            # With default threshold (0.65): passes
            result_default = validate_adaptation(original, adapted, threshold=0.65)
            assert result_default == []

            # With stricter threshold: fails
            result_strict = validate_adaptation(original, adapted, threshold=0.80)
            assert len(result_strict) == 1

    def test_multiple_original_bullets_uses_max_similarity(self):
        """The max similarity across all originals is used per adapted bullet."""
        original = make_schema(["Bullet A", "Bullet B"])
        adapted = make_schema(["Close to Bullet B"])

        similarities = [0.30, 0.85]  # low vs A, high vs B
        call_count = [0]

        def fake_sim(a, b):
            val = similarities[call_count[0] % 2]
            call_count[0] += 1
            return val

        with patch("backend.adapter.validator.embed_text") as mock_embed, \
             patch("backend.adapter.validator.cosine_similarity", side_effect=fake_sim):
            mock_embed.return_value = [0.1] * 384
            result = validate_adaptation(original, adapted)
            # max(0.30, 0.85) = 0.85 → passes
            assert result == []
