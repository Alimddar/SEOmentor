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
    "claude-3-5-sonnet-latest",
    "claude-3-5-haiku-latest",
    "claude-3-haiku-20240307",
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

DETAIL_SYSTEM_MESSAGE = """You are an expert SEO execution coach with deep hands-on experience implementing \
technical SEO fixes, content optimization, link building campaigns, and performance tuning.

Your role is to translate high-level SEO tasks into detailed, step-by-step execution guides that a \
marketing team member with basic technical skills can follow independently.

For every task, think about:
- What exact tools or methods to use (Google Search Console, Screaming Frog, PageSpeed Insights, etc.)
- What the specific deliverable looks like when complete
- What metrics to measure before and after to prove impact
- Common pitfalls to avoid during execution

Return only valid raw JSON. No markdown fences or text outside JSON."""


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
            "Open Google Search Console and export current CTR and impression data for the target page.",
            "Analyze the existing title tag and meta description — note character length, keyword presence, and call-to-action clarity.",
            "Draft 2-3 keyword-optimized title/meta variants using the primary target keyword within the first 60 characters.",
            "Implement the strongest variant in the CMS or HTML template and verify it renders correctly in the page source.",
            "Use Google's Rich Results Test or a SERP preview tool to confirm the snippet displays properly on mobile and desktop.",
            "Submit the URL for re-indexing in Google Search Console and set a 14-day reminder to compare CTR changes.",
        ]
        kpi = "Increase organic CTR for the target page by at least 0.5 percentage points within 14 days."
    elif "alt" in task_lower and "image" in task_lower:
        checklist = [
            "Run Screaming Frog or use Chrome DevTools to export a list of all images on the target page with their current alt attributes.",
            "Identify every image with missing or empty alt text and categorize them by content type (product, decorative, informational).",
            "Write descriptive, keyword-relevant alt text for each non-decorative image — keep under 125 characters and describe what the image shows.",
            "Mark purely decorative images with empty alt='' and role='presentation' to comply with accessibility standards.",
            "Deploy the updated alt attributes and run a Lighthouse accessibility audit to verify zero missing-alt warnings.",
            "Document the changes in a spreadsheet noting old vs. new alt text for future reference and team review.",
        ]
        kpi = "Reduce missing alt-text count on the target page to zero and achieve Lighthouse accessibility score above 90."
    elif "schema" in task_lower or "structured data" in task_lower:
        checklist = [
            "Identify the most appropriate schema type for the page (Organization, LocalBusiness, Product, FAQ, Article, etc.) based on content intent.",
            "Use Schema.org documentation to draft a complete JSON-LD block with all recommended properties for the chosen type.",
            "Insert the JSON-LD script tag into the page head or before the closing body tag in the template.",
            "Validate the markup using Google's Rich Results Test — fix any errors or warnings flagged.",
            "Cross-check with Schema Markup Validator (schema.org) for full compliance beyond Google-specific requirements.",
            "Monitor Google Search Console's Enhancements section over the next 7 days for rich result eligibility changes.",
        ]
        kpi = "Achieve valid structured data markup with zero critical errors and eligibility for rich results within 7 days."
    elif "speed" in task_lower or "core web vital" in task_lower or "mobile" in task_lower:
        checklist = [
            "Run PageSpeed Insights and Web Vitals extension to capture baseline LCP, FID/INP, and CLS scores for both mobile and desktop.",
            "Identify the top 3 performance bottlenecks from the diagnostics (typically unoptimized images, render-blocking resources, or excessive DOM size).",
            "Compress and convert images to WebP/AVIF format, implement lazy loading for below-the-fold images, and add explicit width/height attributes.",
            "Defer non-critical JavaScript and CSS — move render-blocking scripts to async/defer and inline critical CSS above the fold.",
            "Re-run PageSpeed Insights to verify improvements and fix any remaining issues flagged in the Opportunities section.",
            "Document before/after scores and set up a CrUX or Web Vitals monitoring dashboard for ongoing tracking.",
        ]
        kpi = "Improve mobile PageSpeed Performance score by at least 15 points and achieve LCP under 2.5 seconds."
    elif "keyword" in task_lower or "content" in task_lower or "page" in task_lower:
        checklist = [
            "Research the primary keyword using Google Search Console data and competitor analysis — identify search volume, intent, and current ranking position.",
            "Audit the target page's current content: check word count, heading structure, keyword density, and topical coverage gaps vs. top 3 ranking competitors.",
            "Expand or rewrite content sections to fully address user intent — add relevant subtopics, FAQ sections, and supporting evidence.",
            "Optimize the H1 tag, H2 subheadings, intro paragraph, and meta description to naturally incorporate the target keyword and related terms.",
            "Add 3-5 contextual internal links from high-authority pages on the site to the target page using descriptive anchor text.",
            "Publish the updated content, submit for re-indexing, and track ranking position changes in Google Search Console over 21 days.",
        ]
        kpi = "Improve target keyword ranking position by at least 5 places within 21 days."
    elif "link" in task_lower or "backlink" in task_lower or "outreach" in task_lower:
        checklist = [
            "Audit the current backlink profile using available data — identify referring domains, anchor text distribution, and link quality.",
            "Research 10-15 relevant link prospects: industry directories, resource pages, guest post opportunities, and local business listings.",
            "Draft personalized outreach templates for each prospect type — focus on mutual value rather than link requests.",
            "Send outreach emails to the top 5 most promising prospects and track responses in a spreadsheet.",
            "Submit the site to 3-5 relevant, high-quality business directories or industry listings with complete NAP information.",
            "Document all outreach activity, responses, and acquired links for ongoing link building tracking.",
        ]
        kpi = "Acquire at least 2 new referring domains from relevant, authoritative sources within 30 days."
    else:
        checklist = [
            "Review the task requirements and identify which specific page, element, or content piece needs attention.",
            "Collect baseline metrics from Google Search Console or analytics for the targeted page or element before making changes.",
            "Execute the planned optimization following SEO best practices — ensure all changes are technically correct and user-friendly.",
            "Validate the changes using appropriate tools (Lighthouse, Search Console URL Inspection, SERP preview tools).",
            "Cross-check that the change does not negatively impact other pages (check internal links, canonical tags, redirect chains).",
            "Record the change details, before/after metrics, and expected timeline for measurable impact in your project tracker.",
        ]
        kpi = "Complete the task with verified technical correctness and one measurable SEO metric improvement logged."

    return {
        "description": f"Day {day} execution focus: {normalized_task} — This task targets a specific "
        f"optimization area that will contribute to the overall SEO improvement plan. "
        f"Follow the checklist below for step-by-step implementation guidance.",
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
    issues = _safe_str_list(result_json.get("issues", []), 6)
    keyword_gaps = _safe_str_list(result_json.get("keyword_gaps", []), 8)
    competitors = []
    for item in result_json.get("competitors", []):
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if name:
            competitors.append(name)
        if len(competitors) >= 5:
            break

    primary_goal = str(input_context.get("primary_goal") or "").strip() or "Not provided"
    business_offer = str(input_context.get("business_offer") or "").strip() or "Not provided"
    target_audience = str(input_context.get("target_audience") or "").strip() or "Not provided"
    execution_capacity = str(input_context.get("execution_capacity") or "").strip() or "Not provided"
    country = str(input_context.get("country") or "").strip() or "Not provided"
    language = str(input_context.get("language") or "").strip() or "Not provided"
    seed_keywords = _safe_str_list(input_context.get("seed_keywords", []), 6)

    return f"""Return ONLY valid JSON with this exact shape:
{{
  "description": "string",
  "checklist": ["string"],
  "kpi": "string"
}}

===== CONTEXT =====
Website: {url}
Country: {country}
Language: {language}
Day {day} of the SEO roadmap
Task: {task}
Primary Goal: {primary_goal}
Business / Offer: {business_offer}
Target Audience: {target_audience}
Execution Capacity: {execution_capacity}
Seed Keywords: {seed_keywords if seed_keywords else "Not provided"}
Known Issues: {issues if issues else "Not provided"}
Keyword Gaps: {keyword_gaps if keyword_gaps else "Not provided"}
Competitors: {competitors if competitors else "Not provided"}

===== INSTRUCTIONS =====

DESCRIPTION (3-4 sentences):
Write a clear, actionable explanation of what needs to be done today and WHY it matters for this \
specific website's SEO. Reference the actual task, the site's current state, and the expected outcome. \
Mention which specific page, element, or content piece this targets.

CHECKLIST (exactly 6 items):
Create 6 sequential, concrete steps that someone can follow to complete this task:
- Step 1-2: Preparation and baseline measurement (what to audit/measure before starting)
- Step 3-4: Core execution (the actual implementation work with specific instructions)
- Step 5: Validation and quality check (how to verify the work is correct)
- Step 6: Measurement and documentation (how to track impact and record what was done)
Each step should be specific enough that someone unfamiliar with the project can execute it. \
Mention specific tools where relevant (Google Search Console, PageSpeed Insights, Screaming Frog, \
Chrome DevTools, etc.).

KPI (1 measurable metric):
Define ONE specific, measurable metric with a concrete numeric target and timeframe. \
Examples: 'Reduce page load time from Xms to under 2000ms within 7 days', \
'Increase organic CTR for target page from X% to X+1.5% within 14 days'. \
The KPI must be directly tied to this specific task's outcome.

===== RULES =====
- No markdown, no extra keys, no text outside JSON
- Do not use unescaped double quotes inside string values; use single quotes
- Every checklist item must be actionable — no vague items like 'review results'
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
            if len(checklist) >= 8:
                break

    if not description or not kpi or len(checklist) < 4:
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
