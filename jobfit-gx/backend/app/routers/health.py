from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlmodel import Session

from app.config import get_settings
from app.db import get_session
from app.schemas import HealthResponse
from app.services.embeddings import get_embedding_service
from app.services.llm_client import OllamaClient

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(session: Session = Depends(get_session)) -> HealthResponse:
    database = "ok"
    try:
        session.exec(text("select 1"))
    except Exception:
        database = "unreachable"

    embeddings = get_embedding_service()
    settings = get_settings()
    return HealthResponse(
        status="ok" if database == "ok" else "degraded",
        model=settings.local_llm_model,
        database=database,
        embeddings=f"configured:{settings.embedding_model}",
        ollama=await OllamaClient().health(),
        chroma=embeddings.health(),
    )

