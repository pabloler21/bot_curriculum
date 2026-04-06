# src/routes/jobs.py
import asyncio
import logging
import uuid

import httpx
import zvec
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel as PydanticBaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.jobs import Job, fetch_jobs
from backend.ranker import get_jobs_collection
from backend.scorer import score_job
from backend.sessions import get_session

logger = logging.getLogger(__name__)
limiter = Limiter(key_func=get_remote_address)
router = APIRouter()


@router.get("/jobs/ranked")
async def get_ranked_jobs(token: str | None = Query(default=None)):
    # UUID validation
    if token is not None:
        try:
            uuid.UUID(token)
        except ValueError:
            return JSONResponse(
                status_code=400,
                content={
                    "detail": "Invalid session token format",
                    "code": "invalid_token",
                },
            )

    try:
        jobs = await fetch_jobs()
    except httpx.HTTPError as e:
        logger.warning("[jobs] Upstream fetch failed: %s", e)
        return JSONResponse(
            status_code=502,
            content={
                "detail": "Could not fetch job listings",
                "code": "upstream_error",
            },
        )
    except Exception as e:
        logger.exception("[jobs] Unexpected error fetching jobs for ranking: %s", e)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "code": "internal_error"},
        )

    # Try to get session embedding for ranking
    session = get_session(token) if token else None

    if session and session.cv_embedding:
        col = get_jobs_collection()
        results = col.query(
            vectors=zvec.VectorQuery("embedding", vector=session.cv_embedding),
            topk=20,
        )
        jobs_by_id = {job.id: job for job in jobs}
        ranked_ids = {r.id for r in results}

        result = []
        for r in results:
            job = jobs_by_id.get(r.id)
            if job:
                job_dict = job.model_dump(mode="json")
                job_dict["similarity_score"] = round(r.score, 2)
                result.append(job_dict)

        # Jobs in cache not yet indexed by Zvec → append with no score
        for job in jobs:
            if job.id not in ranked_ids:
                job_dict = job.model_dump(mode="json")
                job_dict["similarity_score"] = None
                result.append(job_dict)

        return result
    else:
        # Graceful fallback: return unranked with similarity_score null
        result = []
        for job in jobs:
            job_dict = job.model_dump(mode="json")
            job_dict["similarity_score"] = None
            result.append(job_dict)
        return result


@router.get("/jobs")
async def get_jobs():
    try:
        jobs = await fetch_jobs()
        return [job.model_dump(mode="json") for job in jobs]
    # NOTE: Using JSONResponse directly (not HTTPException) to include both
    # "detail" and "code" fields, which HTTPException does not support natively.
    except httpx.HTTPError as e:
        logger.warning("[jobs] Upstream fetch failed: %s", e)
        return JSONResponse(
            status_code=502,
            content={
                "detail": "Could not fetch job listings",
                "code": "upstream_error",
            },
        )
    except Exception as e:
        logger.exception("[jobs] Unexpected error: %s", e)
        return JSONResponse(
            status_code=500,
            content={
                "detail": "Internal server error",
                "code": "internal_error",
            },
        )


class ScoreRequest(PydanticBaseModel):
    token: str
    limit: int = 8


@router.post("/jobs/score")
@limiter.limit("3/minute")
async def score_jobs(request: Request, body: ScoreRequest):
    # UUID validation
    try:
        uuid.UUID(body.token)
    except ValueError:
        return JSONResponse(
            status_code=400,
            content={"detail": "Invalid session token format", "code": "invalid_token"},
        )

    # Validate limit
    limit = min(max(body.limit, 1), 12)

    session = get_session(body.token)
    if session is None:
        return JSONResponse(
            status_code=400,
            content={"detail": "No active CV session", "code": "no_session"},
        )

    try:
        jobs = await fetch_jobs()
    except Exception as e:
        logger.exception("[jobs/score] Failed to fetch jobs: %s", e)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "code": "internal_error"},
        )

    # Select top N via Zvec
    col = get_jobs_collection()
    zvec_results = col.query(
        vectors=zvec.VectorQuery("embedding", vector=session.cv_embedding or []),
        topk=limit,
    )
    jobs_by_id = {job.id: job for job in jobs}
    top_jobs = [jobs_by_id[r.id] for r in zvec_results if r.id in jobs_by_id]

    # Score in parallel, using cache when available
    async def score_one(job: Job):
        if job.id in session.scored_jobs:
            cached = session.scored_jobs[job.id]
            # Return cached dict (may be None if it failed before)
            if cached is not None:
                return cached
            return None  # previously failed

        try:
            match = await score_job(session.cv_text, job)
            session.scored_jobs[job.id] = match.model_dump()
            return session.scored_jobs[job.id]
        except Exception:
            logger.warning(
                "[jobs/score] Scoring failed for job %s", job.id, exc_info=True
            )
            session.scored_jobs[job.id] = None
            return None

    results_list = await asyncio.gather(*[score_one(j) for j in top_jobs])

    response = []
    for job, result in zip(top_jobs, results_list):
        if result is not None:
            response.append({"job_id": job.id, **result})
        else:
            response.append({
                "job_id": job.id,
                "score": None,
                "match_level": None,
                "matched_skills": [],
                "missing_skills": [],
                "one_line_summary": None,
            })

    return response
