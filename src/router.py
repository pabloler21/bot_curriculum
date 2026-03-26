from fastapi import APIRouter
from fastapi.middleware.cors import CORSMiddleware
from src.routes.evaluate import router as evaluate_router
from src.routes.health import router as health_router
from dotenv import load_dotenv
import os

load_dotenv()

router = APIRouter()

router.include_router(evaluate_router)
router.include_router(health_router)