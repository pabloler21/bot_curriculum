# tests/test_models.py
"""Tests for backend/models.py — stage → model lookup and defaults."""
import importlib

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


def test_evaluator_uses_its_stage():
    from backend import evaluator
    assert evaluator.model.model == models._STAGE_MODELS["evaluate"]
    assert evaluator.model.max_tokens == 16000  # sale de model_for, no de un ChatAnthropic propio


def test_scorer_uses_its_stage():
    from backend import scorer
    assert scorer._model.model == models._STAGE_MODELS["score"]
    assert scorer._model.max_tokens == 16000


@pytest.mark.parametrize("module, attr", [
    ("backend.adapter.adapter", "_structured_model"),
    ("backend.adapter.extractor", "_structured_model"),
    ("backend.adapter.improver", "_chain"),
    ("backend.adapter.interview", "_structured_model"),
    ("backend.evaluator", "structured_model"),
    ("backend.evaluator", "translate_structured_model"),
    ("backend.scorer", "_structured_model"),
])
def test_structured_stages_use_structured_outputs(module, attr):
    # Con la tool forzada, Haiku 5.5 devolvía objetos anidados como string
    # (y Haiku 4.5 omitía campos): output_config.format restringe al schema.
    runnable = getattr(importlib.import_module(module), attr)
    kwargs = next(step.kwargs for step in runnable.steps if hasattr(step, "kwargs"))
    assert kwargs["output_config"]["format"]["type"] == "json_schema"


def test_unknown_stage_raises():
    with pytest.raises(KeyError):
        models.model_for("nope")
