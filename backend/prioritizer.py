# backend/prioritizer.py
"""
Prioridad de las keywords faltantes y las recomendaciones del evaluator, con Jev (TypeSafe).

Una pregunta Score por ítem, de 0 (optional) a 2 (essential); el orden y el nivel salen del score.
"""
import logging
import os

from typesafe_sdk import AsyncTypeSafeClient, Score, TypeSafeError

logger = logging.getLogger(__name__)

_TIMEOUT = 5.0  # si Jev tarda más, la evaluación sale sin prioridades

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


async def _ask_jev(state: dict, questions: dict[str, Score]) -> dict[str, float]:
    async with AsyncTypeSafeClient(timeout=_TIMEOUT) as client:
        response = await client.system_one(state, questions)
    return {name: response.scores[name].score for name in questions}


async def prioritize(evaluation: dict, job_context: str | None = None) -> dict:
    """Copia de la evaluación con las listas ordenadas y sus niveles; sin cambios si Jev no está o falla."""
    keywords = evaluation.get("keywords_missing") or []
    recommendations = evaluation.get("recommendations") or []
    if not os.getenv("TYPESAFE_API_KEY") or not (keywords or recommendations):
        return evaluation

    # El CV no va: es input no confiable y, según la doc de Jev, el contenido de más distrae.
    state = {
        "target_role": evaluation.get("target_role", ""),
        "job_description": job_context,
        "missing_keywords": keywords,
        "recommendations": recommendations,
    }
    try:
        scores = await _ask_jev(state, build_questions(len(keywords), len(recommendations)))
        keyword_scores = [scores[f"kw_{i}"] for i in range(len(keywords))]
        recommendation_scores = [scores[f"rec_{i}"] for i in range(len(recommendations))]
    except (TypeSafeError, KeyError) as exc:
        logger.warning("[prioritizer] Jev failed, evaluation goes out without priorities: %r", exc)
        return evaluation

    result = dict(evaluation)
    result["keywords_missing"], result["keywords_missing_priority"] = rank(keywords, keyword_scores)
    result["recommendations"], result["recommendations_priority"] = rank(recommendations, recommendation_scores)
    return result
