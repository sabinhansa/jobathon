from typing import Any

from app.schemas import RequirementMatch, StructuredJob, SuggestedBullet


def build_markdown_report(
    score: int,
    summary: str,
    requirement_matches: list[RequirementMatch],
    strengths: list[str],
    gaps: list[str],
    cv_improvements: list[SuggestedBullet],
    cover_letter: str,
    recruiter_message: str,
    interview_prep: list[str],
    warnings: list[str],
) -> str:
    rows = [
        "| Requirement | Importance | Status | Evidence |",
        "| --- | --- | --- | --- |",
    ]
    for item in requirement_matches:
        evidence = "<br>".join(item.cv_evidence) if item.cv_evidence else "not visible in the CV"
        rows.append(f"| {item.requirement} | {item.importance} | {item.status} | {evidence} |")

    bullets = lambda values: "\n".join(f"- {value}" for value in values) if values else "- None called out."
    cv_fix_rows = "\n".join(
        f"- **{item.target_section}:** {item.suggested_bullet} _({item.why_it_helps})_"
        for item in cv_improvements
    ) or "- No targeted rewrite suggestions generated."

    return f"""# JobFit GX Match Report

**Overall score:** {score}/100

{summary}

## Requirement Matches

{chr(10).join(rows)}

## Strong Matches

{bullets(strengths)}

## Missing or Weak Evidence

{bullets(gaps)}

## CV Improvements

{cv_fix_rows}

## Cover Letter Draft

{cover_letter}

## Recruiter Message Draft

{recruiter_message}

## Interview Prep

{bullets(interview_prep)}

## Warnings

{bullets(warnings)}
"""


def fallback_cv_improvements(evidence: list[str], structured_job: StructuredJob) -> list[SuggestedBullet]:
    keywords = structured_job.technologies[:5] + structured_job.hard_requirements[:3]
    suggestions: list[SuggestedBullet] = []
    for idx, snippet in enumerate(evidence[:6]):
        keyword = keywords[idx % len(keywords)] if keywords else "role-relevant impact"
        suggestions.append(
            SuggestedBullet(
                target_section="Experience",
                original_evidence=snippet[:500],
                suggested_bullet=f"Emphasize {keyword} using this CV-backed evidence and add [add metric if true].",
                why_it_helps="It makes the CV evidence easier to map to the job requirement without inventing facts.",
            )
        )
    return suggestions


def fallback_generation(company: str | None, title: str | None, score: int, strengths: list[str]) -> dict[str, Any]:
    role = title or "the role"
    org = company or "your team"
    strength_text = "; ".join(strengths[:3]) or "relevant CV-backed experience"
    cover = (
        f"Hello,\n\nI am interested in {role} at {org}. My CV shows {strength_text}. "
        "The role appears to align with my background, and I would welcome the chance to discuss where my experience is strongest "
        "and where I would ramp up quickly.\n\nBest regards"
    )
    recruiter = f"Hi, I am interested in {role}. My CV appears to match key needs around {strength_text}. Happy to share more context if useful."
    prep = [
        "Prepare one concrete example for each strong match in the report.",
        "Be ready to explain gaps as ramp-up areas, using the phrase 'not currently visible in my CV' where accurate.",
        f"Have a crisp answer for why {role} is a fit based on the strongest CV evidence.",
    ]
    return {"cover_letter": cover, "recruiter_message": recruiter[:700], "interview_talking_points": prep}

