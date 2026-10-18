# tests/test_prioritizer.py
"""Tests for backend/prioritizer.py — prioridad de keywords y recomendaciones con Jev."""
from backend.prioritizer import (
    KEYWORD_LEVELS,
    RECOMMENDATION_LEVELS,
    build_questions,
    level_for,
    rank,
)


def test_level_thresholds():
    assert [level_for(s) for s in (2.0, 1.5, 1.49, 0.5, 0.49, 0.0)] == [
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
