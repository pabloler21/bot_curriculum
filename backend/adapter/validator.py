# backend/adapter/validator.py
"""
Pipeline Stage 3 — Post-generation validation.

Each bullet in the adapted schema is compared against all bullets in the original
schema using cosine similarity on fastembed embeddings.

If a bullet has max similarity < threshold, it's considered suspicious
(potentially hallucinated or too far from the original wording).

The pipeline uses this list to decide whether to retry Stage 2 or deliver as PARTIAL.
"""
import logging

from backend.ranker import cosine_similarity, embed_text
from backend.schemas import CVSchema

logger = logging.getLogger(__name__)

SIMILARITY_THRESHOLD = 0.65


def validate_adaptation(
    original: CVSchema,
    adapted: CVSchema,
    threshold: float = SIMILARITY_THRESHOLD,
) -> list[str]:
    """
    Return list of adapted bullets that don't have sufficient similarity
    to any bullet in the original schema (potential hallucinations).

    Strategy:
        - Pre-compute embeddings for all original bullets (one batch)
        - For each adapted bullet, compute its embedding and find max
          cosine similarity against all original embeddings
        - If max_similarity < threshold → suspicious

    Args:
        original: the extracted CVSchema (ground truth)
        adapted: the adapted CVSchema from Stage 2
        threshold: minimum acceptable cosine similarity (default 0.65)

    Returns:
        List of suspicious adapted bullet strings. Empty list = all clear.
    """
    original_bullets = [
        bullet
        for exp in original.experiences
        for bullet in exp.bullets
    ]

    if not original_bullets:
        logger.warning("[validator] No original bullets found — skipping validation")
        return []

    adapted_bullets = [
        bullet
        for exp in adapted.experiences
        for bullet in exp.bullets
    ]

    if not adapted_bullets:
        return []

    logger.info(
        "[validator] Validating %d adapted bullets against %d original bullets, threshold=%.2f",
        len(adapted_bullets),
        len(original_bullets),
        threshold,
    )

    # Pre-compute original embeddings (reused for each adapted bullet)
    original_embeddings = [embed_text(b) for b in original_bullets]

    suspicious: list[str] = []

    for bullet in adapted_bullets:
        adapted_emb = embed_text(bullet)
        max_sim = max(
            cosine_similarity(adapted_emb, orig_emb)
            for orig_emb in original_embeddings
        )
        if max_sim < threshold:
            logger.debug(
                "[validator] Suspicious bullet (sim=%.3f): %.80s…", max_sim, bullet
            )
            suspicious.append(bullet)

    if suspicious:
        logger.warning(
            "[validator] %d/%d bullets suspicious", len(suspicious), len(adapted_bullets)
        )
    else:
        logger.info("[validator] All %d bullets passed validation", len(adapted_bullets))

    return suspicious
