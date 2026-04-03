# backend/ranker.py
import logging

import numpy as np
from sentence_transformers import SentenceTransformer

from backend.jobs import Job

logger = logging.getLogger(__name__)

_MODEL_NAME = "all-MiniLM-L6-v2"
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info("[ranker] Loading SentenceTransformer model: %s", _MODEL_NAME)
        _model = SentenceTransformer(_MODEL_NAME)
        logger.info("[ranker] Model loaded")
    return _model


def embed_text(text: str) -> list[float]:
    """Embed text and return as list of floats."""
    model = _get_model()
    embedding = model.encode(text, convert_to_numpy=True)
    return embedding.tolist()


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    norm_a = np.linalg.norm(va)
    norm_b = np.linalg.norm(vb)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(va, vb) / (norm_a * norm_b))


def rank_jobs(cv_embedding: list[float], jobs: list[Job]) -> list[tuple[Job, float]]:
    """Return jobs sorted by cosine similarity to cv_embedding, descending.

    Uses pre-computed job.embedding when available; falls back to embedding
    job.description on the fly.
    """
    scored = []
    for job in jobs:
        job_emb = job.embedding if job.embedding else embed_text(job.description)
        score = max(0.0, min(1.0, cosine_similarity(cv_embedding, job_emb)))
        scored.append((job, round(score, 2)))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
