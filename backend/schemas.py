"""Pydantic schemas for API request/response."""

import re

from pydantic import BaseModel, Field, field_validator

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AnalyzeRequest(BaseModel):
    """Request body for POST /analyze."""

    url: str
    country: str = "Azerbaijan"
    language: str = "English"
    plan_days: int = Field(default=30, ge=7, le=30)
    primary_goal: str = "Increase organic traffic"
    business_offer: str = ""
    target_audience: str = ""
    priority_pages: list[str] = Field(default_factory=list)
    seed_keywords: list[str] = Field(default_factory=list)
    known_competitors: list[str] = Field(default_factory=list)
    execution_capacity: str = ""

    @field_validator(
        "url",
        "country",
        "language",
        "primary_goal",
        "business_offer",
        "target_audience",
        "execution_capacity",
        mode="before",
    )
    @classmethod
    def normalize_text_fields(cls, value: object) -> str:
        return str(value or "").strip()

    @field_validator("priority_pages", "seed_keywords", "known_competitors", mode="before")
    @classmethod
    def normalize_list_fields(cls, value: object) -> list[str]:
        if value is None:
            return []

        if isinstance(value, str):
            raw_items = re.split(r"[\n,]", value)
        elif isinstance(value, list):
            raw_items = value
        else:
            return []

        cleaned: list[str] = []
        for item in raw_items:
            text = str(item or "").strip()
            if text:
                cleaned.append(text)

        return cleaned[:15]


class AnalyzeResponse(BaseModel):
    """Response for POST /analyze."""

    project_id: int


class SendPlanEmailRequest(BaseModel):
    """Request body for sending existing project plan to email."""

    email: str

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Email is required")
        if not EMAIL_PATTERN.match(normalized):
            raise ValueError("Invalid email format")
        return normalized


class SendPlanEmailResponse(BaseModel):
    """Response for sending project plan email."""

    sent: bool
    message: str


class DayTaskDetailResponse(BaseModel):
    """Detailed breakdown for a specific roadmap day."""

    day: int
    task: str
    description: str
    checklist: list[str]
    kpi: str


class CompetitorItem(BaseModel):
    """Single competitor entry."""

    name: str
    reason: str
    url: str = ""


class RoadmapDay(BaseModel):
    """Single day in the generated roadmap."""

    day: int
    task: str


class ProjectResponse(BaseModel):
    """Full SEO analysis returned by GET /project/{id}."""

    seo_score: float
    issues: list[str]
    competitors: list[CompetitorItem]
    keyword_gaps: list[str]
    roadmap: list[RoadmapDay]


class ProjectHistoryItem(BaseModel):
    """Summary row for history list."""

    id: int
    url: str
    seo_score: float
    plan_days: int
    created_at: str
