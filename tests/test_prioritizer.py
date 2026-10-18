# tests/test_prioritizer.py
"""Tests for backend/prioritizer.py — prioridad de keywords y recomendaciones con Jev."""
import asyncio
import time
from unittest.mock import AsyncMock, patch

import pytest
from typesafe_sdk import TypeSafeAPIConnectionError, TypeSafeAPITimeoutError, TypeSafeError

from backend import prioritizer
from backend.prioritizer import (
    KEYWORD_LEVELS,
    RECOMMENDATION_LEVELS,
    build_questions,
    level_for,
    prioritize,
    rank,
)


def test_level_thresholds():
    # Calibrados con 3 CVs reales (4.21): Jev deja casi todo entre 0.8 y 1.7, y con 1.5/0.5 todo era "important".
    assert [level_for(s) for s in (2.0, 1.3, 1.29, 0.95, 0.94, 0.0)] == [
        "essential", "essential", "important", "important", "optional", "optional"]


def test_rank_orders_by_score_and_keeps_ties_stable():
    items, levels = rank(["a", "b", "c", "d"], [0.2, 1.8, 0.2, 1.0])
    assert items == ["b", "d", "a", "c"]
    assert levels == ["essential", "important", "optional", "optional"]


def test_rank_keeps_duplicates_paired_with_their_scores():
    items, levels = rank(["SQL", "Excel", "SQL"], [0.1, 1.0, 1.9])
    assert items == ["SQL", "Excel", "SQL"] and levels == ["essential", "important", "optional"]


def test_build_questions_one_score_per_item():
    qs = build_questions(2, 3)
    assert sorted(qs) == ["kw_0", "kw_1", "rec_0", "rec_1", "rec_2"]
    assert "`missing_keywords[1]`" in qs["kw_1"].instructions
    assert "`recommendations[2]`" in qs["rec_2"].instructions
    assert list(qs["kw_0"].criteria) == KEYWORD_LEVELS and len(KEYWORD_LEVELS) == 3
    assert list(qs["rec_0"].criteria) == RECOMMENDATION_LEVELS
    assert KEYWORD_LEVELS[0].startswith("Optional") and KEYWORD_LEVELS[2].startswith("Essential")


EV = {"target_role": "Data Analyst", "keywords_missing": ["Looker", "SQL"],
      "recommendations": ["Use a pipe separator", "Add SQL"], "summary": "CV text must not leak"}
SCORES = {"kw_0": 0.2, "kw_1": 1.9, "rec_0": 0.3, "rec_1": 1.6}
ASK = "backend.prioritizer._ask_jev"


async def test_prioritize_orders_both_lists_and_adds_levels(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test")
    with patch(ASK, new_callable=AsyncMock, return_value=SCORES):
        result = await prioritize(EV)
    assert result["keywords_missing"] == ["SQL", "Looker"]
    assert result["keywords_missing_priority"] == ["essential", "optional"]
    assert result["recommendations"] == ["Add SQL", "Use a pipe separator"]
    assert result["recommendations_priority"] == ["essential", "optional"]
    assert EV["keywords_missing"] == ["Looker", "SQL"]  # devuelve una copia


async def test_prioritize_sends_only_the_lists_and_the_role(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test")
    with patch(ASK, new_callable=AsyncMock, return_value=SCORES) as ask:
        await prioritize(EV, job_context="Senior Data Analyst at Acme")
    state = ask.await_args.args[0]
    assert set(state) == {"target_role", "job_description", "missing_keywords", "recommendations"}
    assert state["job_description"] == "Senior Data Analyst at Acme"
    assert "CV text must not leak" not in str(state)


async def test_prioritize_without_key_is_a_noop():
    with patch(ASK, new_callable=AsyncMock) as ask:
        assert await prioritize(EV) == EV
    ask.assert_not_awaited()


async def test_prioritize_skips_jev_when_both_lists_are_empty(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test")
    empty = {**EV, "keywords_missing": [], "recommendations": []}
    with patch(ASK, new_callable=AsyncMock) as ask:
        assert await prioritize(empty) == empty
    ask.assert_not_awaited()


@pytest.mark.parametrize(
    "error", [TypeSafeAPITimeoutError(5.0), TypeSafeAPIConnectionError("down"), TypeSafeError("boom")])
async def test_prioritize_returns_the_evaluation_untouched_when_jev_fails(monkeypatch, error):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test")
    with patch(ASK, new_callable=AsyncMock, side_effect=error):
        assert await prioritize(EV) == EV


async def test_prioritize_treats_a_missing_answer_as_a_failure(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test")
    with patch(ASK, new_callable=AsyncMock, return_value={"kw_0": 1.0}):
        assert await prioritize(EV) == EV


class _FakeClient:
    """Reemplaza a AsyncTypeSafeClient: guarda cómo se construyó y tarda `delay` en responder."""
    kwargs: dict = {}
    delay = 0.0

    def __init__(self, **kwargs):
        _FakeClient.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def system_one(self, state, questions):
        await asyncio.sleep(self.delay)
        raise TypeSafeError("fake")


async def test_prioritize_gives_up_on_a_hung_jev_within_the_deadline(monkeypatch):
    monkeypatch.setenv("TYPESAFE_API_KEY", "test")
    monkeypatch.setattr(prioritizer, "_TIMEOUT", 0.05)
    monkeypatch.setattr(_FakeClient, "delay", 3.0)
    monkeypatch.setattr(prioritizer, "AsyncTypeSafeClient", _FakeClient)
    started = time.monotonic()
    assert await prioritize(EV) == EV
    assert time.monotonic() - started < 1.0


async def test_prioritize_does_not_let_the_sdk_retry(monkeypatch):
    # Los reintentos por defecto del SDK (2, con backoff) estiraban el tope de 5 s a ~16 s.
    monkeypatch.setenv("TYPESAFE_API_KEY", "test")
    monkeypatch.setattr(prioritizer, "AsyncTypeSafeClient", _FakeClient)
    await prioritize(EV)
    assert _FakeClient.kwargs["retry"].max_retries == 0
