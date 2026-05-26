from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.db import get_session
from app.models import JobAnalysis
from app.schemas import AnalysisHistoryItem, AnalyzeRequest, AnalyzeResponse, RegenerateRequest
from app.services.embeddings import get_embedding_service
from app.services.matching import analyze_job

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze(payload: AnalyzeRequest, session: Session = Depends(get_session)) -> AnalyzeResponse:
    if not payload.job_text.strip():
        raise HTTPException(status_code=400, detail="Paste job description or extract visible page text.")
    try:
        return await analyze_job(session, get_embedding_service(), payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/history", response_model=list[AnalysisHistoryItem])
def history(session: Session = Depends(get_session)) -> list[JobAnalysis]:
    return list(session.exec(select(JobAnalysis).order_by(JobAnalysis.created_at.desc()).limit(50)).all())


@router.get("/{analysis_id}")
def get_analysis(analysis_id: str, session: Session = Depends(get_session)) -> JobAnalysis:
    analysis = session.get(JobAnalysis, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return analysis


@router.delete("/{analysis_id}")
def delete_analysis(analysis_id: str, session: Session = Depends(get_session)) -> dict[str, str]:
    analysis = session.get(JobAnalysis, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    session.delete(analysis)
    session.commit()
    return {"status": "deleted", "analysis_id": analysis_id}


@router.post("/{analysis_id}/regenerate")
def regenerate(analysis_id: str, payload: RegenerateRequest, session: Session = Depends(get_session)) -> dict:
    analysis = session.get(JobAnalysis, analysis_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    report = dict(analysis.report_json)
    tone = payload.tone or "confident, concise, practical"
    if payload.section == "cover_letter":
        return {"section": payload.section, "content": report.get("cover_letter", ""), "tone": tone}
    if payload.section == "recruiter_message":
        return {"section": payload.section, "content": report.get("recruiter_message", ""), "tone": tone}
    if payload.section == "cv_bullets":
        return {"section": payload.section, "content": report.get("cv_improvements", []), "tone": tone}
    return {"section": payload.section, "content": report.get("interview_prep", []), "tone": tone}

