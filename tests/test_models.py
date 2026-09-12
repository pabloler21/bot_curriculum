# tests/test_models.py
"""Tests for backend/models.py — stage → model lookup and defaults."""
import pytest

from backend import models


def test_defaults_are_haiku():
    assert models._STAGE_MODELS == {
        "extract": "claude-haiku-4-5",
        "adapt": "claude-haiku-4-5",
        "cover": "claude-haiku-4-5",
    }


@pytest.mark.parametrize("stage", ["extract", "adapt", "cover"])
def test_model_for_returns_configured_model(monkeypatch, stage):
    monkeypatch.setitem(models._STAGE_MODELS, stage, "claude-sonnet-4-5")
    assert models.model_for(stage).model == "claude-sonnet-4-5"


def test_unknown_stage_raises():
    with pytest.raises(KeyError):
        models.model_for("nope")
