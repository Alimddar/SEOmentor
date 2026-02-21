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
    word_count: int
    internal_links: int
    missing_alt_images: int


class AIAnalysisResult(TypedDict):
    """Structured JSON returned by the AI service."""

    seo_score: float
    issues: list[str]
    competitors: list[dict]
    keyword_gaps: list[str]
    roadmap: list[dict]
