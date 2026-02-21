"""Data models and types used across the backend.

Database table definitions are in database.py.
Types for scraper and AI output live here.
"""

from typing import TypedDict


class ScrapedData(TypedDict):
    """Structured output from homepage scraper."""

    title: str
    meta_description: str
    h1_count: int
    h2_count: int
    h3_count: int
    word_count: int
    internal_links: int
    external_links: int
    missing_alt_images: int
    total_images: int
    canonical_url: str
    robots_meta: str
    has_viewport_meta: bool
    og_title: str
    og_description: str
    og_image: str
    has_structured_data: bool
    structured_data_types: list[str]
    hreflang_tags: list[str]
    h1_texts: list[str]
    http_status: int
    response_time_ms: int


class AIAnalysisResult(TypedDict):
    """Structured JSON returned by the AI service."""

    seo_score: float
    issues: list[str]
    competitors: list[dict]
    keyword_gaps: list[str]
    roadmap: list[dict]
