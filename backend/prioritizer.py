# backend/prioritizer.py
"""
Prioridad de las keywords faltantes y las recomendaciones del evaluator, con Jev (TypeSafe).

Una pregunta Score por ítem, de 0 (optional) a 2 (essential); el orden y el nivel salen del score.
"""
import logging

from typesafe_sdk import Score

logger = logging.getLogger(__name__)

# Criterios de menor a mayor, como los pide Score. El ítem se referencia con un path del state.
KEYWORD_LEVELS = [
    "Optional: rarely asked for in these jobs; missing it barely changes the candidate's chances",
    "Important: often listed in these job posts; missing it lowers the match but does not rule the candidate out",
    "Essential: a core requirement; ATS filters and recruiters screen out candidates who lack it",
]
RECOMMENDATION_LEVELS = [
    "Optional: polish; a small wording or formatting tweak that barely changes how ATS or recruiters rank the CV",
    "Important: noticeably improves the keyword match or the clarity of the CV, "
    "but its absence does not rule the candidate out",
    "Essential: fixes something that makes ATS misread the CV or screen the candidate out, "
    "or adds a core requirement of the role",
]
_JOB = "If `job_description` is not null, judge against it."

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


def build_questions(n_keywords: int, n_recommendations: int) -> dict[str, Score]:
    questions = {
        f"kw_{i}": Score(
            instructions=f"How essential is the keyword `missing_keywords[{i}]` for someone applying "
            f"to `target_role` jobs? {_JOB}",
            criteria=KEYWORD_LEVELS,
        )
        for i in range(n_keywords)
    }
    questions.update({
        f"rec_{i}": Score(
            instructions=f"How much does applying the recommendation `recommendations[{i}]` improve the "
            f"chances of someone applying to `target_role` jobs? {_JOB}",
            criteria=RECOMMENDATION_LEVELS,
        )
        for i in range(n_recommendations)
    })
    return questions
