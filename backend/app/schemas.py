from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(APIModel):
    status: str
    model: str
    database: str
    embeddings: str
    ollama: str
    chroma: str


class CVSummary(APIModel):
    cv_id: str
    name: str
    filename: str
    parsed_summary: dict
    chunk_count: int


class CVListItem(APIModel):
    id: str
    name: str
    filename: str
    created_at: datetime
    updated_at: datetime


class CVChunkRead(APIModel):
    id: str
    section: str
    text: str


class CVRead(CVListItem):
    parsed_summary: dict
    chunks: list[CVChunkRead]


class PreferencesIn(APIModel):
    target_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    seniority: str | None = None
    salary_range: str | None = None
    languages: list[str] = Field(default_factory=list)
    tone: str = "confident, concise, practical"
    projects_to_emphasize: list[str] = Field(default_factory=list)
    skills_to_emphasize: list[str] = Field(default_factory=list)
    avoid_claims_not_in_cv: bool = True
    cover_letter_style: str = "short, grounded, specific"


class PreferencesOut(PreferencesIn):
    id: str = "default"
    updated_at: datetime | None = None


class JobCleanRequest(APIModel):
    raw_text: str


class StructuredJob(APIModel):
    title: str | None = None
    company: str | None = None
    location: str | None = None
    remote_policy: str | None = None
    seniority: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    hard_requirements: list[str] = Field(default_factory=list)
    nice_to_have_requirements: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    soft_skills: list[str] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    years_experience: str | None = None
    benefits: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    unclear_points: list[str] = Field(default_factory=list)


class JobCleanResponse(APIModel):
    cleaned_text: str
    structured: StructuredJob


class AnalyzeRequest(APIModel):
    cv_id: str
    job_text: str
    job_url: str | None = None
    job_title: str | None = None
    company: str | None = None
    mode: Literal["fast", "deep"] = "fast"


class RequirementMatch(APIModel):
    requirement: str
    importance: Literal["required", "nice_to_have", "responsibility", "technology"]
    status: Literal["strong_match", "partial_match", "missing", "unclear"]
    cv_evidence: list[str] = Field(default_factory=list)
    explanation: str


class SuggestedBullet(APIModel):
    target_section: str
    original_evidence: str
    suggested_bullet: str
    why_it_helps: str


class AnalyzeResponse(APIModel):
    analysis_id: str
    overall_score: int
    confidence: Literal["low", "medium", "high"]
    summary: str
    requirement_matches: list[RequirementMatch]
    strengths: list[str]
    gaps: list[str]
    cv_improvements: list[SuggestedBullet]
    cover_letter: str
    recruiter_message: str
    interview_prep: list[str]
    warnings: list[str]
    markdown_report: str


class AnalysisHistoryItem(APIModel):
    id: str
    cv_id: str
    job_title: str | None
    company: str | None
    final_score: int
    confidence: str
    created_at: datetime


class RegenerateRequest(APIModel):
    section: Literal["cover_letter", "recruiter_message", "cv_bullets", "interview_prep"]
    tone: str | None = None
