import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from src.router import router

load_dotenv()

# el limiter usa la IP del usuario para trackear las requests
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="CV Evaluator API")

# le pasamos el limiter a la app para que slowapi pueda usarlo
app.state.limiter = limiter

# si alguien supera el limite, devuelve 429 Too Many Requests
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

FRONTEND_BASE_URL = os.getenv("FRONTEND_BASE_URL", "http://localhost:3000")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_BASE_URL],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)