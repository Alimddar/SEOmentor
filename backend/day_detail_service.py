"""Generate detailed day-task guidance using Claude."""

import json
import os
import random
import re
import time
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

DETAIL_MODEL_CANDIDATES = [
    os.getenv("CLAUDE_DETAIL_MODEL", "").strip(),
    os.getenv("CLAUDE_MODEL", "").strip(),
    "claude-3-5-haiku-latest",
    "claude-3-haiku-20240307",
    "claude-3-5-sonnet-latest",
]


def _dedupe_models(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        model = value.strip()
        if not model or model in seen:
            continue
        out.append(model)
        seen.add(model)
    return out


DETAIL_MODEL_CANDIDATES = _dedupe_models(DETAIL_MODEL_CANDIDATES)
DETAIL_TEMPERATURE = float(os.getenv("CLAUDE_DETAIL_TEMPERATURE", "0.2"))
DETAIL_MAX_TOKENS = int(os.getenv("CLAUDE_DETAIL_MAX_TOKENS", "900"))
DETAIL_MAX_RETRIES = int(os.getenv("CLAUDE_DETAIL_MAX_RETRIES", "2"))
DETAIL_RETRY_BASE_SECONDS = float(os.getenv("CLAUDE_DETAIL_RETRY_BASE_SECONDS", "0.8"))

DETAIL_SYSTEM_MESSAGE = """You are an expert SEO execution coach.
Return only valid raw JSON.
Do not include markdown fences or any text outside JSON."""


def _extract_json(text: str) -> dict | None:
    if not text:
        return None
    cleaned = text.strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1:
        return None
    json_str = cleaned[start : end + 1]
    json_str = (
        json_str
        .replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
    )

    def _escape_controls_in_string_values(value: str) -> str:
        out: list[str] = []
        in_string = False
        escaped = False
        for ch in value:
            if escaped:
                out.append(ch)
                escaped = False
                continue
            if ch == "\\":
                out.append(ch)
                escaped = True
                continue
            if ch == '"':
                out.append(ch)
                in_string = not in_string
                continue
            if in_string and ch in {"\n", "\r", "\t"}:
                out.append("\\n")
                continue
            out.append(ch)
        return "".join(out)

    repaired = _escape_controls_in_string_values(json_str)
    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)

    try:
        parsed = json.loads(json_str)
        return parsed if isinstance(parsed, dict) else None
    except Exception:
        try:
            parsed = json.loads(repaired)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None


def _extract_response_text(response: object) -> str:
    content = ""
    for block in getattr(response, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            content += text
    return content.strip()


def _safe_str_list(value: object, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = str(item or "").strip()
        if text:
            out.append(text)
        if len(out) >= limit:
            break
    return out


def _fallback_day_detail(task: str, day: int) -> dict:
    normalized_task = str(task or "").strip() or "Execute today's SEO task."
    task_lower = normalized_task.lower()

    if "title" in task_lower or "meta" in task_lower:
        checklist = [
            "Audit current title/meta and note baseline CTR for target page.",
            "Draft two keyword-aligned title/meta variants for the page.",
            "Publish the best variant and verify rendered HTML.",
            "Submit URL for recrawl and track CTR/impression changes.",
        ]
        kpi = "Increase page CTR by at least 0.5 percentage points in 14 days."
    elif "alt" in task_lower and "image" in task_lower:
        checklist = [
            "List all images on the target page missing alt text.",
            "Write descriptive alt text including relevant intent keywords.",
            "Update image alt attributes and run accessibility checks.",
            "Re-crawl the page and confirm no missing-alt warnings.",
        ]
        kpi = "Reduce missing alt-text count on target page to zero."
    elif "schema" in task_lower or "structured data" in task_lower:
        checklist = [
            "Choose schema type matching the page intent (Organization, FAQ, Product, etc.).",
            "Generate valid JSON-LD and insert it into the page template.",
            "Validate markup with rich result testing tools.",
            "Fix warnings and re-test until the schema is valid.",
        ]
        kpi = "Achieve valid schema markup with zero critical errors on the target page."
    elif "speed" in task_lower or "core web vital" in task_lower or "mobile" in task_lower:
        checklist = [
            "Measure baseline Core Web Vitals for the target page.",
            "Optimize largest assets (images, scripts, CSS) and defer non-critical JS.",
            "Re-run performance tests on mobile and desktop.",
            "Deploy fixes and compare before/after performance metrics.",
        ]
        kpi = "Improve mobile Performance score by at least 10 points on the target page."
    elif "keyword" in task_lower or "content" in task_lower or "page" in task_lower:
        checklist = [
            "Define the primary keyword and supporting subtopics for this page.",
            "Create or expand page sections to satisfy user intent clearly.",
            "Optimize H1/H2, intro paragraph, and internal links for the target term.",
            "Publish and track ranking movement for the primary keyword.",
        ]
        kpi = "Improve target keyword position by at least 3 ranks within 21 days."
    else:
        checklist = [
            "Review current page status and collect baseline metrics.",
            "Execute the planned task on the target page or asset.",
            "Validate technical correctness and on-page relevance after deployment.",
            "Record outcome and define next optimization step.",
        ]
        kpi = "Complete the task with one measurable SEO improvement logged."

    return {
        "description": f"Day {day} execution focus: {normalized_task}",
        "checklist": checklist,
        "kpi": kpi,
    }


def _build_prompt(
    *,
    url: str,
    day: int,
    task: str,
    result_json: dict,
    input_context: dict,
) -> str:
    issues = _safe_str_list(result_json.get("issues", []), 4)
    keyword_gaps = _safe_str_list(result_json.get("keyword_gaps", []), 6)
    competitors = []
    for item in result_json.get("competitors", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if name:
            competitors.append(name)
        if len(competitors) >= 4:
            break

    primary_goal = str(input_context.get("primary_goal") or "").strip() or "Not provided"
    business_offer = str(input_context.get("business_offer") or "").strip() or "Not provided"
    target_audience = str(input_context.get("target_audience") or "").strip() or "Not provided"
    execution_capacity = str(input_context.get("execution_capacity") or "").strip() or "Not provided"
    country = str(input_context.get("country") or "").strip() or "Not provided"
    language = str(input_context.get("language") or "").strip() or "Not provided"

    return f"""Return ONLY valid JSON with this exact shape:
{{
  "description": "string",
  "checklist": ["string"],
  "kpi": "string"
}}

Context:
- Website: {url}
- Country: {country}
- Language: {language}
- Day: {day}
- Task: {task}
- Primary Goal: {primary_goal}
- Business / Offer: {business_offer}
- Target Audience: {target_audience}
- Execution Capacity: {execution_capacity}
- Top Issues: {issues if issues else "Not provided"}
- Keyword Gaps: {keyword_gaps if keyword_gaps else "Not provided"}
- Competitors: {competitors if competitors else "Not provided"}

Rules:
1) Make the description concrete and actionable for this exact task.
2) Keep description between 2 and 3 short sentences.
3) checklist must have exactly 4 concrete items.
4) kpi must be one measurable metric with target.
5) No markdown. No extra keys. No text outside JSON.
"""


def _build_compact_retry_prompt(prompt: str) -> str:
    return (
        prompt
        + "\n\nPrevious output was invalid JSON."
        + "\nRegenerate strict compact JSON only."
        + "\nKeep every string short and ensure all braces are closed."
    )


def _is_retryable_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    retry_tokens = (
        "overloaded",
        "529",
        "rate limit",
        "rate_limit",
        "429",
        "500",
        "502",
        "503",
        "504",
        "timeout",
        "connection",
    )
    return any(token in msg for token in retry_tokens)


def _call_claude_once(client: Anthropic, prompt: str, max_output_tokens: int) -> tuple[dict | None, str]:
    last_stop_reason = ""
    for model in DETAIL_MODEL_CANDIDATES:
        for attempt in range(DETAIL_MAX_RETRIES):
            try:
                response = client.messages.create(
                    model=model,
                    max_tokens=max_output_tokens,
                    system=DETAIL_SYSTEM_MESSAGE,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=DETAIL_TEMPERATURE,
                )
                stop_reason = str(getattr(response, "stop_reason", "") or "").lower()
                last_stop_reason = stop_reason
                text = _extract_response_text(response)
                if not text:
                    if attempt < DETAIL_MAX_RETRIES - 1:
                        delay = DETAIL_RETRY_BASE_SECONDS * (2 ** attempt) + random.uniform(0, 0.25)
                        time.sleep(delay)
                        continue
                    break

                parsed = _extract_json(text)
                if parsed is None:
                    print(
                        "CLAUDE DETAIL PARSE ERROR:",
                        f"model={model} stop_reason={stop_reason} raw={text[:500]}",
                    )
                return parsed, stop_reason
            except Exception as exc:
                if _is_retryable_error(exc) and attempt < DETAIL_MAX_RETRIES - 1:
                    delay = DETAIL_RETRY_BASE_SECONDS * (2 ** attempt) + random.uniform(0, 0.25)
                    time.sleep(delay)
                    continue
                print(f"CLAUDE DETAIL ERROR model={model}:", str(exc))
                break

    return None, last_stop_reason


def _call_claude(prompt: str) -> dict | None:
    api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        print("CLAUDE DETAIL: ANTHROPIC_API_KEY is missing, using fallback.")
        return None

    client = Anthropic(api_key=api_key)
    first, first_stop_reason = _call_claude_once(client, prompt, max_output_tokens=DETAIL_MAX_TOKENS)
    if isinstance(first, dict):
        return first

    retry_prompt = _build_compact_retry_prompt(prompt)
    retry_tokens = (
        max(1200, DETAIL_MAX_TOKENS + 300)
        if first_stop_reason == "max_tokens"
        else max(400, DETAIL_MAX_TOKENS // 2)
    )
    second, _ = _call_claude_once(client, retry_prompt, max_output_tokens=retry_tokens)
    return second


def _normalize_detail(parsed: dict) -> dict | None:
    description = str(parsed.get("description") or "").strip()
    kpi = str(parsed.get("kpi") or "").strip()
    checklist_raw = parsed.get("checklist")
    checklist: list[str] = []
    if isinstance(checklist_raw, list):
        for item in checklist_raw:
            text = str(item or "").strip()
            if text:
                checklist.append(text)
            if len(checklist) >= 6:
                break

    if not description or not kpi or len(checklist) < 3:
        return None

    return {
        "description": description,
        "checklist": checklist,
        "kpi": kpi,
    }


def generate_day_task_detail(
    *,
    url: str,
    day: int,
    task: str,
    result_json: dict,
    input_context: dict | None = None,
) -> dict:
    """Return normalized day detail. Never raises."""
    fallback = _fallback_day_detail(task=task, day=day)
    safe_context = input_context if isinstance(input_context, dict) else {}

    try:
        prompt = _build_prompt(
            url=url,
            day=day,
            task=task,
            result_json=result_json if isinstance(result_json, dict) else {},
            input_context=safe_context,
        )
        parsed = _call_claude(prompt)
        if not isinstance(parsed, dict):
            return fallback

        normalized = _normalize_detail(parsed)
        return normalized if normalized is not None else fallback
    except Exception as exc:
        print("DAY DETAIL ERROR:", str(exc))
        return fallback
