import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, JSON, Text
from sqlmodel import Field, Relationship, SQLModel


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


class CV(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str
    filename: str
    text_hash: str = Field(index=True)
    raw_text: str = Field(sa_column=Column(Text))
    parsed_summary: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)

    chunks: list["CVChunk"] = Relationship(back_populates="cv")


class CVChunk(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    cv_id: str = Field(foreign_key="cv.id", index=True)
    section: str = "General"
    text: str = Field(sa_column=Column(Text))
    embedding_id: str | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=now_utc)

    cv: CV = Relationship(back_populates="chunks")


class UserPreferences(SQLModel, table=True):
    id: str = Field(default="default", primary_key=True)
    target_roles: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    locations: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    seniority: str | None = None
    salary_range: str | None = None
    tone: str = "confident, concise, practical"
    languages: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    projects_to_emphasize: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    skills_to_emphasize: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    avoid_claims_not_in_cv: bool = True
    cover_letter_style: str = "short, grounded, specific"
    created_at: datetime = Field(default_factory=now_utc)
    updated_at: datetime = Field(default_factory=now_utc)


class JobAnalysis(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    cv_id: str = Field(foreign_key="cv.id", index=True)
    job_url: str | None = None
    job_title: str | None = None
    company: str | None = None
    raw_job_text: str = Field(sa_column=Column(Text))
    structured_job_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    deterministic_score: int
    final_score: int
    confidence: str = "medium"
    report_json: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    markdown_report: str = Field(sa_column=Column(Text))
    created_at: datetime = Field(default_factory=now_utc, index=True)

