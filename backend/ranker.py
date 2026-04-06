# backend/ranker.py
import logging
import os

import numpy as np
import zvec
from sentence_transformers import SentenceTransformer

from backend.jobs import Job

logger = logging.getLogger(__name__)

_MODEL_NAME = "all-MiniLM-L6-v2"
_model: SentenceTransformer | None = None

_ZVEC_PATH = "./zvec_jobs"
_collection: zvec.Collection | None = None
_ZVEC_SCHEMA = zvec.CollectionSchema(
    name="jobs",
    vectors=zvec.VectorSchema("embedding", zvec.DataType.VECTOR_FP32, 384),
)


def get_jobs_collection() -> zvec.Collection:
    """Open or create the Zvec jobs collection. Singleton (lazy init)."""
    global _collection
    if _collection is None:
        if os.path.exists(_ZVEC_PATH):
            logger.info("[ranker] Opening existing Zvec collection at %s", _ZVEC_PATH)
            _collection = zvec.open(_ZVEC_PATH)
        else:
            logger.info("[ranker] Creating new Zvec collection at %s", _ZVEC_PATH)
            _collection = zvec.create_and_open(path=_ZVEC_PATH, schema=_ZVEC_SCHEMA)
    return _collection


_inserted_ids: set[str] = set()


def upsert_job(job: Job) -> None:
    """Embed job.description and insert into Zvec collection.

    Idempotent: safe to call across server restarts. If the job already exists
    in the on-disk collection (e.g. from a previous run), the insert returns a
    non-ok status — we log it and carry on rather than raising.
    """
    if job.id in _inserted_ids:
        return
    col = get_jobs_collection()
    embedding = embed_text(job.description)
    status = col.insert(zvec.Doc(id=job.id, vectors={"embedding": embedding}))
    if status.ok():
        logger.debug("[ranker] Upserted job %s into Zvec", job.id)
    else:
        logger.debug("[ranker] Job %s already in Zvec collection, skipping insert", job.id)
    # Always track in-memory so we skip the embed + insert attempt next time
    _inserted_ids.add(job.id)


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
        job_emb = embed_text(job.description)
        score = max(0.0, min(1.0, cosine_similarity(cv_embedding, job_emb)))
        scored.append((job, round(score, 2)))
    scored.sort(key=lambda x: x[1], reverse=True)
    return scored
