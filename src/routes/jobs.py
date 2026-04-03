# src/routes/jobs.py
import logging
import uuid

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from backend.jobs import fetch_jobs
from backend.ranker import rank_jobs
from backend.sessions import get_session

logger = logging.getLogger(__name__)
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
        ranked = rank_jobs(session.cv_embedding, jobs)
        result = []
        for job, score in ranked:
            job_dict = job.model_dump(mode="json")
            job_dict["similarity_score"] = round(score, 2)
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
