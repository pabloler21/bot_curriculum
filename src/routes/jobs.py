# src/routes/jobs.py
import logging

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.jobs import fetch_jobs

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/jobs")
async def get_jobs():
    try:
        jobs = await fetch_jobs()
        return [job.model_dump(mode="json") for job in jobs]
    except (httpx.HTTPError, httpx.RequestError) as e:
        logger.warning("[jobs] Upstream fetch failed: %s", e)
        return JSONResponse(
            status_code=502,
            content={"detail": "Could not fetch job listings", "code": "upstream_error"},
        )
    except Exception as e:
        logger.exception("[jobs] Unexpected error: %s", e)
        return JSONResponse(
            status_code=502,
            content={"detail": "Could not fetch job listings", "code": "upstream_error"},
        )
