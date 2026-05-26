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
        fallback_match(requirements, evidence_by_requirement, include_warning=False)
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
    deterministic = deterministic_extract(cleaned)
    client = OllamaClient()
    if await client.health() == "ok":
        try:
            data = await client.generate_json(load_prompt("extraction_prompt.txt"), {"job_text": cleaned})
            return repair_structured_job(StructuredJob.model_validate(data), deterministic)
        except Exception:
            pass
    return deterministic


def repair_structured_job(structured: StructuredJob, deterministic: StructuredJob) -> StructuredJob:
    employer_side = [
        "update you on",
        "provide the tools",
        "protect your time",
        "listen actively",
        "celebrate your wins",
        "grant you the freedom",
    ]
    joined = " ".join(structured.responsibilities).lower()
    if deterministic.responsibilities and (not structured.responsibilities or any(phrase in joined for phrase in employer_side)):
        structured.responsibilities = deterministic.responsibilities
    if not structured.hard_requirements and deterministic.hard_requirements:
        structured.hard_requirements = deterministic.hard_requirements
    if not structured.technologies and deterministic.technologies:
        structured.technologies = deterministic.technologies
    return structured


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


def chunk_requirements(requirements: list[tuple[str, str]], size: int) -> list[list[tuple[str, str]]]:
    return [requirements[index : index + size] for index in range(0, len(requirements), size)]


async def compare_with_llm_or_fallback(
    structured: StructuredJob,
    evidence_by_requirement: dict[str, list[str]],
    requirements: list[tuple[str, str]],
    session: Session,
) -> dict[str, Any]:
    prefs = get_or_create_preferences(session)
    client = OllamaClient()
    if await client.health() == "ok":
        matches: list[dict[str, Any]] = []
        strengths: list[str] = []
        gaps: list[str] = []
        warnings: list[str] = []
        prompt = load_prompt("matching_prompt.txt")
        for batch in chunk_requirements(requirements, size=6):
            payload = {
                "structured_job": structured.model_dump(),
                "requirements": [{"importance": kind, "requirement": req, "cv_chunks": evidence_by_requirement.get(req, [])} for kind, req in batch],
                "preferences": {
                    "target_roles": prefs.target_roles,
                    "locations": prefs.locations,
                    "seniority": prefs.seniority,
                    "tone": prefs.tone,
                    "skills_to_emphasize": prefs.skills_to_emphasize,
                    "avoid_claims_not_in_cv": prefs.avoid_claims_not_in_cv,
                },
            }
            try:
                data = await client.generate_json(prompt, payload)
                normalized = normalize_match_result(data, batch, evidence_by_requirement)
            except Exception as exc:
                normalized = fallback_match(
                    batch,
                    evidence_by_requirement,
                    include_warning=True,
                    fallback_reason=f"{type(exc).__name__}: {str(exc)[:180]}",
                )
            matches.extend(normalized["requirement_matches"])
            strengths.extend(normalized["strengths"])
            gaps.extend(normalized["gaps"])
            warnings.extend(normalized["warnings"])
        if matches:
            return {
                "summary": "Deep LLM analysis compared the job against visible CV evidence.",
                "confidence": "medium",
                "requirement_matches": matches,
                "strengths": dedupe(strengths)[:12],
                "gaps": dedupe(gaps)[:12],
                "warnings": dedupe(warnings),
            }
    return fallback_match(
        requirements,
        evidence_by_requirement,
        include_warning=True,
        fallback_reason="Ollama is not reachable",
    )


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


def fallback_match(
    requirements: list[tuple[str, str]],
    evidence_by_requirement: dict[str, list[str]],
    include_warning: bool = True,
    fallback_reason: str | None = None,
) -> dict[str, Any]:
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
    fit_label = "strong" if score >= 75 else "moderate" if score >= 50 else "stretch"
    if include_warning:
        summary = f"Fallback local scan: this role looks like a {fit_label} fit based on the CV evidence I could match."
    else:
        summary = f"Quick local scan: this role looks like a {fit_label} fit based on the CV evidence I could match."
    warnings = []
    if include_warning:
        detail = f" Reason: {fallback_reason}" if fallback_reason else ""
        warnings.append(f"Deep LLM comparison could not produce a valid structured match report, so deterministic local matching was used.{detail}")
    return {
        "summary": summary,
        "confidence": "medium" if matches else "low",
        "requirement_matches": matches,
        "strengths": strengths[:8],
        "gaps": gaps[:8],
        "warnings": warnings,
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
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", text)
    return [token for token in re.findall(r"[a-zA-Z][a-zA-Z0-9+.#-]{1,}", text.lower()) if len(token) > 2]


def normalize_match_result(
    data: dict[str, Any],
    requirements: list[tuple[str, str]],
    evidence_by_requirement: dict[str, list[str]],
) -> dict[str, Any]:
    fallback = fallback_match(requirements, evidence_by_requirement, include_warning=False)
    fallback_by_requirement = {item["requirement"]: item for item in fallback["requirement_matches"]}
    known_importance = {requirement: importance for importance, requirement in requirements}
    warnings = [str(item) for item in as_list(data.get("warnings"))]
    matches: list[dict[str, Any]] = []
    seen: set[str] = set()

    for item in as_list(data.get("requirement_matches")):
        if not isinstance(item, dict):
            continue
        requirement = str(item.get("requirement") or "").strip()
        if not requirement:
            continue
        importance = coerce_importance(item.get("importance"), known_importance.get(requirement, "required"))
        status = coerce_status(item.get("status"))
        evidence = [str(value).strip() for value in as_list(item.get("cv_evidence")) if str(value).strip()]
        explanation = str(item.get("explanation") or "").strip()
        if not explanation:
            explanation = "Compared by the local LLM against the retrieved CV evidence."
        matches.append(
            {
                "requirement": requirement,
                "importance": importance,
                "status": status,
                "cv_evidence": evidence[:4] if status != "missing" else [],
                "explanation": explanation,
            }
        )
        seen.add(requirement)

    for _, requirement in requirements:
        if requirement in seen:
            continue
        fallback_item = fallback_by_requirement.get(requirement)
        if fallback_item:
            matches.append(fallback_item)

    if not matches:
        raise ValueError("LLM returned no usable requirement_matches")
    for item in matches:
        RequirementMatch.model_validate(item)

    omitted_count = max(0, len(requirements) - len(seen))
    if omitted_count:
        warnings.append(f"{omitted_count} requirement(s) were filled with local matching because the LLM omitted them.")
    return {
        "summary": str(data.get("summary") or "Deep LLM analysis compared the job against visible CV evidence.").strip(),
        "confidence": coerce_confidence(data.get("confidence")),
        "requirement_matches": matches,
        "strengths": [str(item) for item in as_list(data.get("strengths"))][:12],
        "gaps": [str(item) for item in as_list(data.get("gaps"))][:12],
        "warnings": warnings,
    }


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def coerce_importance(value: Any, default: str) -> str:
    normalized = str(value or default).lower().replace("-", "_").replace(" ", "_")
    if normalized in {"required", "hard", "hard_requirement", "hard_requirements", "must_have", "qualification"}:
        return "required"
    if normalized in {"nice", "nice_to_have", "preferred", "bonus"}:
        return "nice_to_have"
    if normalized in {"responsibility", "responsibilities", "task", "candidate_responsibility"}:
        return "responsibility"
    if normalized in {"technology", "technologies", "tool", "tools", "tech"}:
        return "technology"
    return "required"


def coerce_status(value: Any) -> str:
    normalized = str(value or "").lower().replace("-", "_").replace(" ", "_")
    if normalized in {"strong", "match", "matched", "strong_match", "yes"}:
        return "strong_match"
    if normalized in {"partial", "partially_matched", "partial_match", "weak_match"}:
        return "partial_match"
    if normalized in {"missing", "not_visible", "absent", "no"}:
        return "missing"
    return "unclear"


def coerce_confidence(value: Any) -> str:
    normalized = str(value or "medium").lower()
    return normalized if normalized in {"low", "medium", "high"} else "medium"


def dedupe(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        key = value[:120]
        if key not in seen:
            seen.add(key)
            out.append(value)
    return out
