import re

from bs4 import BeautifulSoup

from app.schemas import StructuredJob

TECH_TERMS = [
    "python", "typescript", "javascript", "react", "fastapi", "django", "flask",
    "sql", "postgres", "postgresql", "aws", "azure", "gcp", "docker", "kubernetes",
    "llm", "rag", "machine learning", "nlp", "pytorch", "tensorflow", "git",
    "ci/cd", "linux", "api", "rest", "graphql", "node", "next.js",
]


def clean_job_text(raw_text: str) -> str:
    soup = BeautifulSoup(raw_text or "", "html.parser")
    text = soup.get_text("\n") if soup.find() else raw_text
    text = re.sub(r"\r", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(?i)\b(show more|see less|apply now|save job)\b", "", text)
    return text.strip()


def deterministic_extract(cleaned_text: str) -> StructuredJob:
    lines = [line.strip(" -*\t") for line in cleaned_text.splitlines() if line.strip()]
    title = lines[0] if lines else None
    company = lines[1] if len(lines) > 1 and len(lines[1]) < 80 else None
    sections = _collect_sections(lines)
    tech = sorted({term for term in TECH_TERMS if re.search(rf"\b{re.escape(term)}\b", cleaned_text, re.I)})
    years = re.search(r"(\d+\+?\s*(?:years|yrs)[^.\n]*)", cleaned_text, re.I)
    remote = _find_first(cleaned_text, [r"\bremote\b", r"\bhybrid\b", r"\bon[- ]site\b"])
    seniority = _find_first(cleaned_text, [r"\bsenior\b", r"\bmid[- ]level\b", r"\bjunior\b", r"\blead\b", r"\bstaff\b"])
    return StructuredJob(
        title=title,
        company=company,
        location=_guess_location(lines),
        remote_policy=remote,
        seniority=seniority,
        responsibilities=sections.get("responsibilities", [])[:12],
        hard_requirements=(sections.get("requirements", []) + sections.get("qualifications", []))[:16],
        nice_to_have_requirements=sections.get("nice", [])[:10],
        technologies=tech,
        soft_skills=_soft_skills(cleaned_text),
        education=_education(cleaned_text),
        years_experience=years.group(1) if years else None,
        benefits=sections.get("benefits", [])[:12],
        red_flags=_red_flags(cleaned_text),
        unclear_points=[],
    )


def _collect_sections(lines: list[str]) -> dict[str, list[str]]:
    current = "description"
    sections: dict[str, list[str]] = {}
    for line in lines:
        lowered = line.lower()
        if any(word in lowered for word in ["responsibilities", "what you will do", "role"]):
            current = "responsibilities"
            continue
        if any(word in lowered for word in ["requirements", "required", "must have"]):
            current = "requirements"
            continue
        if any(word in lowered for word in ["qualifications"]):
            current = "qualifications"
            continue
        if any(word in lowered for word in ["nice to have", "preferred", "bonus"]):
            current = "nice"
            continue
        if any(word in lowered for word in ["benefits", "perks", "what we offer"]):
            current = "benefits"
            continue
        if current != "description" and 18 <= len(line) <= 260:
            sections.setdefault(current, []).append(line)
    return sections


def _find_first(text: str, patterns: list[str]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return match.group(0)
    return None


def _guess_location(lines: list[str]) -> str | None:
    for line in lines[:8]:
        if any(token in line.lower() for token in ["remote", "hybrid", "onsite", "on-site"]):
            return line
        if "," in line and len(line) < 90:
            return line
    return None


def _soft_skills(text: str) -> list[str]:
    found = []
    for skill in ["communication", "collaboration", "leadership", "stakeholder management", "mentoring", "ownership"]:
        if re.search(rf"\b{re.escape(skill)}\b", text, re.I):
            found.append(skill)
    return found


def _education(text: str) -> list[str]:
    results = []
    for pattern in [r"bachelor'?s?[^.\n]*", r"master'?s?[^.\n]*", r"degree[^.\n]*"]:
        results.extend(match.group(0) for match in re.finditer(pattern, text, re.I))
    return results[:5]


def _red_flags(text: str) -> list[str]:
    flags = []
    for phrase in ["rockstar", "ninja", "work hard play hard", "unpaid", "must be available 24/7"]:
        if phrase in text.lower():
            flags.append(phrase)
    return flags
