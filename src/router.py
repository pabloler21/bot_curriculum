import logging

from dotenv import load_dotenv
from fastapi import APIRouter

from src.routes.adapt import router as adapt_router
from src.routes.config import router as config_router
from src.routes.credits import router as credits_router
from src.routes.evaluate import router as evaluate_router
from src.routes.health import router as health_router
from src.routes.session import router as session_router
from src.routes.waitlist import router as waitlist_router

load_dotenv()

logger = logging.getLogger(__name__)

router = APIRouter()

router.include_router(adapt_router)
router.include_router(config_router)
router.include_router(credits_router)
router.include_router(evaluate_router)
router.include_router(health_router)
router.include_router(session_router)
router.include_router(waitlist_router)

# Job Board is isolated: if its dependencies (zvec, fastembed, Remotive API) fail,
# the adapter and evaluator continue working.
try:
    from src.routes.jobs import router as jobs_router
    router.include_router(jobs_router)
except Exception as _e:
    logger.warning("[router] Job Board routes unavailable: %s", _e)

