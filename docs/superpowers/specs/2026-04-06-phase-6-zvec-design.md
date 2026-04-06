# Phase 6 — Zvec-based Job Ranking

**Date:** 2026-04-06  
**Branch:** `feature/phase-6-zvec` (from `develop`)

## Goal

Replace the current numpy-based job ranking system with Zvec (Alibaba's in-process vector DB). Job embeddings persist to disk, eliminating re-embedding on every cache refresh and server restart. Job limit increases from 20 to 100.

## What Changes

| Component | Before | After |
|---|---|---|
| `backend/ranker.py` | `rank_jobs()` + numpy loop | `get_jobs_collection()` + `upsert_job()` — `rank_jobs()` removed |
| `backend/jobs.py` | limit=20, embeds all jobs on each refresh, `Job.embedding` in memory | limit=100, embeds only new jobs, `Job.embedding` field removed |
| `src/routes/jobs.py` | `rank_jobs(cv_emb, jobs)` | `collection.query(cv_emb, topk=20)` |
| Storage | RAM only | `./zvec_jobs` on disk (persists across restarts) |
| Dependencies | numpy | zvec added; numpy stays for `cosine_similarity` |

## Architecture

### `backend/ranker.py`

**Remove:** `rank_jobs()`  
**Keep:** `embed_text()`, `cosine_similarity()`  
**Add:**

```python
def get_jobs_collection() -> zvec.Collection:
    """Open or create ./zvec_jobs. Singleton (lazy init)."""

def upsert_job(job: Job) -> None:
    """Embed job.description and insert into collection by job.id."""
```

`get_jobs_collection()` uses a module-level singleton (same pattern as `_model`). Schema: `name="jobs"`, vector field `"embedding"`, type `FP32`, dim `384`.

### `backend/jobs.py`

- `REMOTIVE_PARAMS["limit"]` → `100`
- `Job.embedding` field removed
- `fetch_jobs()`: replaces the `embed_text()` loop with `upsert_job(job)` for each job after mapping. The in-memory cache still holds full `Job` objects (without embeddings).

### `src/routes/jobs.py`

**`GET /jobs/ranked`:**
- Replaces `rank_jobs(session.cv_embedding, jobs)` with:
  ```python
  col = get_jobs_collection()
  results = col.query(
      vectors=zvec.VectorQuery("embedding", vector=cv_embedding),
      topk=20,
  )
  ```
- Cross-references result IDs against `{job.id: job}` dict built from cache. Uses `result.score` from each Zvec result as `similarity_score` (rounded to 2 decimals).
- Jobs in cache not returned by Zvec (not yet upserted) appended with `similarity_score=None`.

**`POST /jobs/score`:**
- Same Zvec query replaces `rank_jobs()` for top-N selection.
- LLM scoring logic, session cache, and parallelism unchanged.

## Data Flow

```
CV upload → extract_text() → embed_text() → CVSession.cv_embedding (RAM)

fetch_jobs() → map Job objects → upsert_job() → ./zvec_jobs (disk)
                              ↓
                         in-memory cache (Job objects, no embeddings)

GET /jobs/ranked:
  CVSession.cv_embedding → collection.query(topk=20) → ranked IDs
  ranked IDs × cache dict → Job objects with similarity_score
```

## Tests (TDD — written before implementation)

### `tests/test_ranker.py` — new tests

- `test_get_jobs_collection_creates_index(tmp_path)` — returns valid collection, creates directory
- `test_get_jobs_collection_reopens_existing(tmp_path)` — two calls to same path succeed without error
- `test_upsert_job_inserts_embedding(tmp_path)` — after upsert, `collection.query()` returns the job ID

### `tests/test_jobs.py` — new test

- `test_fetch_jobs_calls_upsert_for_each_job` — mocks `upsert_job`, verifies called N times after fetch

### `tests/test_ranker.py` — updated route tests

- `test_get_jobs_ranked_with_valid_token_uses_zvec_query` — mocks `collection.query` instead of `rank_jobs`
- Existing `rank_jobs` tests removed (function no longer exists)

## Conventions

- Strict TDD: tests first, then implementation
- Absolute imports from `backend.*` and `src.*`
- `logging.getLogger(__name__)` in every module
- `get_jobs_collection()` singleton initialized lazily (first call creates/opens the collection)
- Zvec disk path: `./zvec_jobs` (relative to working directory, same as where `uvicorn` is launched)

## Out of Scope

- Frontend changes (none required)
- Redis migration for sessions
- Zvec→RAM fallback if disk unavailable
- Changes to LLM scoring logic in `backend/scorer.py`
