from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.router import router
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI(title="CV Evaluator API")

# usamos la variable de entorno en vez de "*"
# en desarrollo es localhost, en produccion es la url real del front
FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_BASE_URL],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)