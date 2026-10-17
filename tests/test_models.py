# tests/test_models.py
"""Tests for backend/models.py — stage → model lookup and defaults."""
import pytest

from backend import models


def test_defaults_are_haiku():
    assert models._STAGE_MODELS == {
        "extract": "claude-haiku-5-5",
        "adapt": "claude-haiku-5-5",
        "cover": "claude-haiku-5-5",
        "interview": "claude-haiku-5-5",
        "improve": "claude-haiku-5-5",
        "evaluate": "claude-haiku-5-5",
        "score": "claude-haiku-5-5",
    }


@pytest.mark.parametrize("stage", ["extract", "adapt", "cover", "interview", "improve", "evaluate", "score"])
def test_model_for_returns_configured_model(monkeypatch, stage):
    monkeypatch.setitem(models._STAGE_MODELS, stage, "claude-sonnet-4-5")
    assert models.model_for(stage).model == "claude-sonnet-4-5"


def test_model_for_sets_max_tokens():
    # langchain-anthropic no conoce claude-haiku-5-5 y caería en 4096: un CV largo
    # en JSON se cortaría. Más de ~21k el SDK exige streaming.
    assert models.model_for("extract").max_tokens == 16000


def test_unknown_stage_raises():
    with pytest.raises(KeyError):
        models.model_for("nope")
