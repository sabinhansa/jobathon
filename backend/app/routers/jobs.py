from fastapi import APIRouter, HTTPException

from app.schemas import JobCleanRequest, JobCleanResponse
from app.services.job_parser import clean_job_text
from app.services.matching import parse_structured_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/clean", response_model=JobCleanResponse)
async def clean_job(payload: JobCleanRequest) -> JobCleanResponse:
    cleaned = clean_job_text(payload.raw_text)
    if not cleaned:
        raise HTTPException(status_code=400, detail="Paste job text before cleaning.")
    structured = await parse_structured_job(cleaned)
    return JobCleanResponse(cleaned_text=cleaned, structured=structured)

