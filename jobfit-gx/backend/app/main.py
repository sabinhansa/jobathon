from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.db import create_db_and_tables
from app.routers import analysis, cvs, health, jobs, preferences

settings = get_settings()

app = FastAPI(
    title="JobFit GX",
    version="0.1.0",
    description="Local-first CV/job matching with FastAPI, Ollama, Chroma, and a Chromium extension.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin for origin in settings.cors_allow_origins if "*" not in origin],
    allow_origin_regex=r"chrome-extension://.*",
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse("/app")


app.include_router(health.router)
app.include_router(cvs.router)
app.include_router(preferences.router)
app.include_router(jobs.router)
app.include_router(analysis.router)
app.mount("/app", StaticFiles(directory="app/static/app", html=True), name="dashboard")

