# backend/prioritizer.py
"""
Prioridad de las keywords faltantes y las recomendaciones del evaluator, con Jev (TypeSafe).

Una pregunta Score por ítem, de 0 (optional) a 2 (essential); el orden y el nivel salen del score.
"""
import logging

logger = logging.getLogger(__name__)

# ponytail: umbrales fijos sobre el score 0–2; si Jev cambia de calibración, ajustarlos con CVs reales
_ESSENTIAL = 1.5
_IMPORTANT = 0.5


def level_for(score: float) -> str:
    if score >= _ESSENTIAL:
        return "essential"
    if score >= _IMPORTANT:
        return "important"
    return "optional"


def rank(items: list[str], scores: list[float]) -> tuple[list[str], list[str]]:
    """Ítems de mayor a menor score (estable: en un empate queda el orden de Haiku) y sus niveles."""
    order = sorted(range(len(items)), key=lambda i: scores[i], reverse=True)
    return [items[i] for i in order], [level_for(scores[i]) for i in order]
