"""SEOmentor API – FastAPI app and endpoint skeletons."""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from database import get_project, init_db, insert_project, list_projects, update_project_result
from ai_service import analyze_with_ai
from day_detail_service import generate_day_task_detail
from mailer import send_plan_email
from scraper import scrape_homepage
from schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    CompetitorItem,
    DayTaskDetailResponse,
    ProjectHistoryItem,
    ProjectResponse,
    RoadmapDay,
    SendPlanEmailRequest,
    SendPlanEmailResponse,
)

app = FastAPI(
    title="SEOmentor API",
    description="AI SEO Roadmap Generator",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(body: AnalyzeRequest) -> AnalyzeResponse:
    """
    Pipeline: scrape homepage -> extract metrics -> AI analysis -> store -> return project_id.
    """
    # 1. Scrape homepage
    scraped = scrape_homepage(body.url)

    # 2. Send to AI service (skeleton: no real AI yet)
    result = analyze_with_ai(
        url=body.url,
        country=body.country,
        language=body.language,
        plan_days=body.plan_days,
        primary_goal=body.primary_goal,
        business_offer=body.business_offer,
        target_audience=body.target_audience,
        priority_pages=body.priority_pages,
        seed_keywords=body.seed_keywords,
        known_competitors=body.known_competitors,
        execution_capacity=body.execution_capacity,
        scraped=scraped,
    )
    result["_input_context"] = {
        "country": body.country,
        "language": body.language,
        "primary_goal": body.primary_goal,
        "business_offer": body.business_offer,
        "target_audience": body.target_audience,
        "priority_pages": body.priority_pages,
        "seed_keywords": body.seed_keywords,
        "known_competitors": body.known_competitors,
        "execution_capacity": body.execution_capacity,
        "plan_days": body.plan_days,
    }

    # 3. Store result and return project_id
    project_id = insert_project(url=body.url, result_json=result)

    return AnalyzeResponse(project_id=project_id)


@app.get("/project/{project_id}", response_model=ProjectResponse)
def get_project_result(project_id: int) -> ProjectResponse:
    """Return full stored SEO analysis for a project."""
    row = get_project(project_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Project not found")

    data = row["result_json"]
    return ProjectResponse(
        seo_score=data["seo_score"],
        issues=data.get("issues", []),
        competitors=[CompetitorItem(**c) for c in data.get("competitors", [])],
        keyword_gaps=data.get("keyword_gaps", []),
        roadmap=[RoadmapDay(**r) for r in data.get("roadmap", [])],
    )


@app.get("/projects", response_model=list[ProjectHistoryItem])
def get_projects(limit: int = 20) -> list[ProjectHistoryItem]:
    """Return recent projects for frontend history page."""
    return [ProjectHistoryItem(**row) for row in list_projects(limit=limit)]


@app.get("/project/{project_id}/day/{day}/detail", response_model=DayTaskDetailResponse)
def get_day_task_detail(project_id: int, day: int, refresh: bool = False) -> DayTaskDetailResponse:
    """Return enriched detail for a specific roadmap day."""
    if day < 1 or day > 30:
        raise HTTPException(status_code=400, detail="Day must be between 1 and 30.")

    row = get_project(project_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Project not found")

    result_json = row["result_json"] if isinstance(row["result_json"], dict) else {}
    roadmap = result_json.get("roadmap", [])
    task_item = None
    for item in roadmap:
        if not isinstance(item, dict):
            continue
        try:
            day_value = int(item.get("day", -1))
        except (TypeError, ValueError):
            day_value = -1
        if day_value == day:
            task_item = item
            break

    if task_item is None:
        raise HTTPException(status_code=404, detail="Roadmap day not found")

    task = str(task_item.get("task") or "").strip() or "Execute today's SEO task."

    def is_generic_fallback_detail(description: str, checklist: list[str], kpi: str) -> bool:
        return (
            description.startswith(f"Day {day} focuses on this priority:")
            and "Execute on live pages, validate the change, and document impact." in description
            and checklist == [
                "Review current page status and collect baseline metrics.",
                "Implement one concrete SEO change for this task.",
                "Verify update is live and technically correct.",
                "Record before/after notes for next-day decisions.",
            ]
            and kpi == "At least one page updated and one measurable SEO metric tracked today."
        )

    cached_details = result_json.get("_day_details", {})
    if isinstance(cached_details, dict) and not refresh:
        cached = cached_details.get(str(day))
        if isinstance(cached, dict):
            description = str(cached.get("description") or "").strip()
            kpi = str(cached.get("kpi") or "").strip()
            checklist = cached.get("checklist")
            if isinstance(checklist, list):
                normalized_checklist = [str(x).strip() for x in checklist if str(x).strip()]
            else:
                normalized_checklist = []
            if description and kpi and normalized_checklist and not is_generic_fallback_detail(
                description,
                normalized_checklist,
                kpi,
            ):
                return DayTaskDetailResponse(
                    day=day,
                    task=task,
                    description=description,
                    checklist=normalized_checklist,
                    kpi=kpi,
                )

    detail = generate_day_task_detail(
        url=row["url"],
        day=day,
        task=task,
        result_json=result_json,
        input_context=result_json.get("_input_context", {}),
    )

    if not isinstance(cached_details, dict):
        cached_details = {}
    cached_details[str(day)] = detail
    result_json["_day_details"] = cached_details
    update_project_result(project_id, result_json)

    return DayTaskDetailResponse(
        day=day,
        task=task,
        description=str(detail.get("description") or ""),
        checklist=[str(x).strip() for x in detail.get("checklist", []) if str(x).strip()],
        kpi=str(detail.get("kpi") or ""),
    )


@app.post("/project/{project_id}/email", response_model=SendPlanEmailResponse)
def email_project_plan(project_id: int, body: SendPlanEmailRequest) -> SendPlanEmailResponse:
    """Send an existing project plan PDF to the provided email."""
    row = get_project(project_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Project not found")

    result_json = row["result_json"]
    roadmap = result_json.get("roadmap", [])
    plan_days = len(roadmap) if isinstance(roadmap, list) and len(roadmap) > 0 else 30
    plan_days = max(1, min(30, plan_days))

    sent = send_plan_email(
        recipient_email=body.email,
        project_id=project_id,
        url=row["url"],
        result=result_json,
        plan_days=plan_days,
    )
    if not sent:
        raise HTTPException(status_code=500, detail="Could not send email.")

    return SendPlanEmailResponse(sent=True, message="Plan emailed successfully.")


@app.get("/health")
def health() -> dict:
    """Health check for deployment."""
    return {"status": "ok"}
