from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlmodel import Session, select

from app.config import get_settings
from app.db import get_session
from app.models import CV, CVChunk, JobAnalysis
from app.schemas import CVListItem, CVRead, CVSummary
from app.services.cv_parser import chunk_cv, clean_text, extract_text_from_bytes, read_upload, summarize_cv, text_hash
from app.services.embeddings import get_embedding_service

router = APIRouter(prefix="/cvs", tags=["cvs"])


@router.post("/upload", response_model=CVSummary)
async def upload_cv(upload: UploadFile = File(...), session: Session = Depends(get_session)) -> CVSummary:
    filename, content = await read_upload(upload, get_settings().max_upload_bytes)
    raw_text = clean_text(extract_text_from_bytes(filename, content))
    if len(raw_text) < 40:
        raise HTTPException(status_code=400, detail="Could not extract enough text from this CV.")

    chunks_data = chunk_cv(raw_text)
    cv = CV(
        name=filename.rsplit(".", 1)[0],
        filename=filename,
        text_hash=text_hash(raw_text),
        raw_text=raw_text,
        parsed_summary=summarize_cv(raw_text, chunks_data),
    )
    session.add(cv)
    session.commit()
    session.refresh(cv)

    chunks = [CVChunk(cv_id=cv.id, section=item["section"], text=item["text"]) for item in chunks_data]
    session.add_all(chunks)
    session.commit()
    for chunk in chunks:
        session.refresh(chunk)

    try:
        get_embedding_service().add_chunks(chunks)
        session.add_all(chunks)
        session.commit()
        embedding_status = "ok"
    except Exception as exc:
        embedding_status = f"deferred:{type(exc).__name__}"
    cv.parsed_summary = {**cv.parsed_summary, "embedding_status": embedding_status}
    cv.updated_at = datetime.now(timezone.utc)
    session.add(cv)
    session.commit()
    session.refresh(cv)

    return CVSummary(cv_id=cv.id, name=cv.name, filename=cv.filename, parsed_summary=cv.parsed_summary, chunk_count=len(chunks))


@router.get("", response_model=list[CVListItem])
def list_cvs(session: Session = Depends(get_session)) -> list[CV]:
    return list(session.exec(select(CV).order_by(CV.created_at.desc())).all())


@router.get("/{cv_id}", response_model=CVRead)
def get_cv(cv_id: str, session: Session = Depends(get_session)) -> CV:
    cv = session.get(CV, cv_id)
    if cv is None:
        raise HTTPException(status_code=404, detail="CV not found")
    cv.chunks
    return cv


@router.delete("/{cv_id}")
def delete_cv(cv_id: str, session: Session = Depends(get_session)) -> dict[str, str]:
    cv = session.get(CV, cv_id)
    if cv is None:
        raise HTTPException(status_code=404, detail="CV not found")
    for chunk in session.exec(select(CVChunk).where(CVChunk.cv_id == cv_id)).all():
        session.delete(chunk)
    for analysis in session.exec(select(JobAnalysis).where(JobAnalysis.cv_id == cv_id)).all():
        session.delete(analysis)
    get_embedding_service().delete_cv(cv_id)
    session.delete(cv)
    session.commit()
    return {"status": "deleted", "cv_id": cv_id}
