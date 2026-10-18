# tests/test_prioritizer.py
"""Tests for backend/prioritizer.py — prioridad de keywords y recomendaciones con Jev."""
from backend.prioritizer import level_for, rank


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
