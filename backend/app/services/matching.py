import re
from typing import Any

from sqlmodel import Session, select

from app.models import CV, CVChunk, JobAnalysis
from app.schemas import AnalyzeRequest, AnalyzeResponse, RequirementMatch, StructuredJob, SuggestedBullet
from app.services.embeddings import EmbeddingService
from app.services.job_parser import clean_job_text, deterministic_extract
from app.services.llm_client import OllamaClient, load_prompt
from app.services.preferences import get_or_create_preferences
from app.services.report_generator import build_markdown_report, fallback_cv_improvements, fallback_generation

STATUS_VALUE = {"strong_match": 1.0, "partial_match": 0.5, "unclear": 0.25, "missing": 0.0}
CATEGORY_WEIGHT = {"required": 55, "responsibility": 20, "technology": 15, "nice_to_have": 5, "preferences": 5}


async def analyze_job(session: Session, embeddings: EmbeddingService, payload: AnalyzeRequest) -> AnalyzeResponse:
    cv = session.get(CV, payload.cv_id)
    if cv is None:
        raise ValueError("CV not found")

    cleaned = clean_job_text(payload.job_text)
    structured = deterministic_extract(cleaned) if payload.mode == "fast" else await parse_structured_job(cleaned)
    if payload.job_title:
        structured.title = payload.job_title
    if payload.company:
        structured.company = payload.company

    requirements = requirement_items(structured)
    evidence_by_requirement = retrieve_evidence(session, embeddings, cv.id, requirements)
    llm_result = (
        fallback_match(requirements, evidence_by_requirement)
        if payload.mode == "fast"
        else await compare_with_llm_or_fallback(structured, evidence_by_requirement, requirements, session)
    )
    requirement_matches = [RequirementMatch.model_validate(item) for item in llm_result["requirement_matches"]]
    deterministic_score = compute_score(requirement_matches)

    evidence_flat = dedupe([snippet for snippets in evidence_by_requirement.values() for snippet in snippets])
    if payload.mode == "fast":
        cv_improvements = fallback_cv_improvements(evidence_flat, structured)
        generated = fallback_generation(structured.company, structured.title, deterministic_score, llm_result["strengths"])
    else:
        cv_improvements, generated = await generate_sections_or_fallback(structured, evidence_flat, deterministic_score, llm_result, session)

    markdown = build_markdown_report(
        deterministic_score,
        llm_result["summary"],
        requirement_matches,
        llm_result["strengths"],
        llm_result["gaps"],
        cv_improvements,
        generated["cover_letter"],
        generated["recruiter_message"],
        generated["interview_talking_points"],
        llm_result["warnings"],
    )
    report_json: dict[str, Any] = {
        "summary": llm_result["summary"],
        "confidence": llm_result["confidence"],
        "requirement_matches": [item.model_dump() for item in requirement_matches],
        "strengths": llm_result["strengths"],
        "gaps": llm_result["gaps"],
        "cv_improvements": [item.model_dump() for item in cv_improvements],
        "cover_letter": generated["cover_letter"],
        "recruiter_message": generated["recruiter_message"],
        "interview_prep": generated["interview_talking_points"],
        "warnings": llm_result["warnings"],
    }
    analysis = JobAnalysis(
        cv_id=cv.id,
        job_url=payload.job_url,
        job_title=structured.title,
        company=structured.company,
        raw_job_text=cleaned,
        structured_job_json=structured.model_dump(),
        deterministic_score=deterministic_score,
        final_score=deterministic_score,
        confidence=llm_result["confidence"],
        report_json=report_json,
        markdown_report=markdown,
    )
    session.add(analysis)
    session.commit()
    session.refresh(analysis)
    return AnalyzeResponse(
        analysis_id=analysis.id,
        overall_score=analysis.final_score,
        confidence=analysis.confidence,  # type: ignore[arg-type]
        summary=report_json["summary"],
        requirement_matches=requirement_matches,
        strengths=report_json["strengths"],
        gaps=report_json["gaps"],
        cv_improvements=cv_improvements,
        cover_letter=report_json["cover_letter"],
        recruiter_message=report_json["recruiter_message"],
        interview_prep=report_json["interview_prep"],
        warnings=report_json["warnings"],
        markdown_report=markdown,
    )


async def parse_structured_job(cleaned: str) -> StructuredJob:
    client = OllamaClient()
    if await client.health() == "ok":
        try:
            data = await client.generate_json(load_prompt("extraction_prompt.txt"), {"job_text": cleaned})
            return StructuredJob.model_validate(data)
        except Exception:
            pass
    return deterministic_extract(cleaned)


def requirement_items(structured: StructuredJob) -> list[tuple[str, str]]:
    items: list[tuple[str, str]] = []
    items.extend(("required", item) for item in structured.hard_requirements)
    items.extend(("responsibility", item) for item in structured.responsibilities)
    items.extend(("technology", item) for item in structured.technologies)
    items.extend(("nice_to_have", item) for item in structured.nice_to_have_requirements)
    if structured.years_experience:
        items.append(("required", structured.years_experience))
    if structured.education:
        items.extend(("required", item) for item in structured.education)
    return [(kind, text) for kind, text in items if text][:35]


def retrieve_evidence(
    session: Session,
    embeddings: EmbeddingService,
    cv_id: str,
    requirements: list[tuple[str, str]],
) -> dict[str, list[str]]:
    chunks = session.exec(select(CVChunk).where(CVChunk.cv_id == cv_id)).all()
    fallback_texts = [chunk.text for chunk in chunks]
    results: dict[str, list[str]] = {}
    for _, requirement in requirements:
        try:
            results[requirement] = embeddings.query_cv(cv_id, requirement, limit=5)
        except Exception:
            results[requirement] = lexical_retrieve(fallback_texts, requirement, limit=5)
    return results


async def compare_with_llm_or_fallback(
    structured: StructuredJob,
    evidence_by_requirement: dict[str, list[str]],
    requirements: list[tuple[str, str]],
    session: Session,
) -> dict[str, Any]:
    prefs = get_or_create_preferences(session)
    client = OllamaClient()
    payload = {
        "structured_job": structured.model_dump(),
        "requirements": [{"importance": kind, "requirement": req, "cv_chunks": evidence_by_requirement.get(req, [])} for kind, req in requirements],
        "preferences": {
            "target_roles": prefs.target_roles,
            "locations": prefs.locations,
            "seniority": prefs.seniority,
            "tone": prefs.tone,
            "skills_to_emphasize": prefs.skills_to_emphasize,
            "avoid_claims_not_in_cv": prefs.avoid_claims_not_in_cv,
        },
    }
    if await client.health() == "ok":
        try:
            data = await client.generate_json(load_prompt("matching_prompt.txt"), payload)
            if data.get("requirement_matches"):
                return normalize_match_result(data)
        except Exception:
            pass
    return fallback_match(requirements, evidence_by_requirement)


async def generate_sections_or_fallback(
    structured: StructuredJob,
    evidence: list[str],
    score: int,
    match_result: dict[str, Any],
    session: Session,
) -> tuple[list[SuggestedBullet], dict[str, Any]]:
    prefs = get_or_create_preferences(session)
    client = OllamaClient()
    fallback_bullets = fallback_cv_improvements(evidence, structured)
    fallback_text = fallback_generation(structured.company, structured.title, score, match_result["strengths"])
    if await client.health() != "ok":
        return fallback_bullets, fallback_text

    bullet_payload = {
        "structured_job": structured.model_dump(),
        "cv_evidence": evidence[:12],
        "requirement_matches": match_result["requirement_matches"],
        "preferences": {"tone": prefs.tone, "skills_to_emphasize": prefs.skills_to_emphasize},
    }
    letter_payload = {
        "structured_job": structured.model_dump(),
        "cv_evidence": evidence[:12],
        "strengths": match_result["strengths"],
        "gaps": match_result["gaps"],
        "tone": prefs.tone,
        "cover_letter_style": prefs.cover_letter_style,
    }
    try:
        bullet_data = await client.generate_json(load_prompt("cv_rewrite_prompt.txt"), bullet_payload)
        bullets = [SuggestedBullet.model_validate(item) for item in bullet_data.get("suggested_bullets", [])][:10]
    except Exception:
        bullets = fallback_bullets
    try:
        generated = await client.generate_json(load_prompt("cover_letter_prompt.txt"), letter_payload)
        generated.setdefault("cover_letter", fallback_text["cover_letter"])
        generated.setdefault("recruiter_message", fallback_text["recruiter_message"])
        generated.setdefault("interview_talking_points", fallback_text["interview_talking_points"])
    except Exception:
        generated = fallback_text
    return bullets or fallback_bullets, generated


def fallback_match(requirements: list[tuple[str, str]], evidence_by_requirement: dict[str, list[str]]) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    strengths: list[str] = []
    gaps: list[str] = []
    for importance, requirement in requirements:
        evidence = evidence_by_requirement.get(requirement, [])
        status = lexical_status(requirement, evidence)
        if status in {"strong_match", "partial_match"}:
            strengths.append(f"Your CV already supports: {requirement}")
        elif status == "missing":
            gaps.append(f"The biggest missing evidence is: {requirement}")
        matches.append(
            {
                "requirement": requirement,
                "importance": importance,
                "status": status,
                "cv_evidence": evidence[:2] if status != "missing" else [],
                "explanation": "Matched using local lexical/embedding evidence." if status != "missing" else "This is not visible in the CV evidence.",
            }
        )
    score = compute_score([RequirementMatch.model_validate(item) for item in matches])
    summary = f"This role looks like a {'strong' if score >= 75 else 'moderate' if score >= 50 else 'stretch'} fit based on visible CV evidence."
    return {
        "summary": summary,
        "confidence": "medium" if matches else "low",
        "requirement_matches": matches,
        "strengths": strengths[:8],
        "gaps": gaps[:8],
        "warnings": ["LLM comparison was unavailable; this report used deterministic local matching."],
    }


def compute_score(matches: list[RequirementMatch]) -> int:
    if not matches:
        return 0
    totals = {key: {"earned": 0.0, "count": 0} for key in CATEGORY_WEIGHT}
    for match in matches:
        key = match.importance
        totals[key]["earned"] += STATUS_VALUE[match.status]
        totals[key]["count"] += 1
    score = 0.0
    for key, weight in CATEGORY_WEIGHT.items():
        count = totals[key]["count"]
        score += weight if count == 0 else weight * (totals[key]["earned"] / count)
    return max(0, min(100, round(score)))


def lexical_retrieve(texts: list[str], query: str, limit: int) -> list[str]:
    tokens = set(normalize_tokens(query))
    scored = []
    for text in texts:
        overlap = len(tokens.intersection(normalize_tokens(text)))
        if overlap:
            scored.append((overlap, text))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [text for _, text in scored[:limit]]


def lexical_status(requirement: str, evidence: list[str]) -> str:
    if not evidence:
        return "missing"
    req_tokens = set(normalize_tokens(requirement))
    evidence_tokens = set(normalize_tokens(" ".join(evidence)))
    if not req_tokens:
        return "unclear"
    ratio = len(req_tokens.intersection(evidence_tokens)) / len(req_tokens)
    if ratio >= 0.55:
        return "strong_match"
    if ratio >= 0.25:
        return "partial_match"
    return "unclear"


def normalize_tokens(text: str) -> list[str]:
    return [token for token in re.findall(r"[a-zA-Z][a-zA-Z0-9+.#-]{1,}", text.lower()) if len(token) > 2]


def normalize_match_result(data: dict[str, Any]) -> dict[str, Any]:
    data.setdefault("summary", "This role was compared against visible CV evidence.")
    data.setdefault("confidence", "medium")
    data.setdefault("strengths", [])
    data.setdefault("gaps", [])
    data.setdefault("warnings", [])
    return data


def dedupe(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        key = value[:120]
        if key not in seen:
            seen.add(key)
            out.append(value)
    return out
