"""
Claude API key must be defined in a .env file in the backend root:

ANTHROPIC_API_KEY=your_real_key_here

The app loads environment variables automatically using python-dotenv.
"""

from dotenv import load_dotenv
import os
from pathlib import Path
import random
import re
import time
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

from anthropic import Anthropic

from models import AIAnalysisResult, ScrapedData

MODEL_CANDIDATES = [
    os.getenv("CLAUDE_MODEL", "").strip(),
    "claude-3-5-sonnet-latest",
    "claude-3-haiku-20240307",
]
MODEL_CANDIDATES = [m for m in MODEL_CANDIDATES if m]
TEMPERATURE = 0.2
MAX_TOKENS = int(os.getenv("CLAUDE_MAX_TOKENS", "3200"))
MAX_RETRIES = int(os.getenv("CLAUDE_MAX_RETRIES", "3"))
RETRY_BASE_SECONDS = float(os.getenv("CLAUDE_RETRY_BASE_SECONDS", "1.0"))
COMPETITOR_LINK_ENRICHMENT = os.getenv("COMPETITOR_LINK_ENRICHMENT", "1").strip().lower() not in {
    "0",
    "false",
    "no",
    "off",
}
COMPETITOR_SEARCH_TIMEOUT_SECONDS = float(os.getenv("COMPETITOR_SEARCH_TIMEOUT_SECONDS", "3.5"))
COMPETITOR_SEARCH_MAX_RESULTS = int(os.getenv("COMPETITOR_SEARCH_MAX_RESULTS", "6"))
SEARCH_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36 SEOmentorBot/1.0"
)
UNWANTED_COMPETITOR_HOSTS = {
    "duckduckgo.com",
    "google.com",
    "bing.com",
    "yahoo.com",
    "facebook.com",
    "instagram.com",
    "x.com",
    "twitter.com",
    "linkedin.com",
    "youtube.com",
    "tiktok.com",
    "wikipedia.org",
}

SYSTEM_MESSAGE = """You are a senior international SEO strategist.
Return ONLY valid raw JSON that matches the schema exactly.
Recommendations must be specific to the provided URL, country, language, and scraped metrics.
Avoid generic advice and repeated actions.
Do not include markdown, code fences, or text outside JSON."""

USER_TEMPLATE = """Website URL: {url}
Country: {country}
Language: {language}

Onboarding Context:
Primary Goal: {primary_goal}
Business / Offer: {business_offer}
Target Audience: {target_audience}
Priority Pages: {priority_pages}
Seed Keywords: {seed_keywords}
Known Competitors: {known_competitors}
Execution Capacity: {execution_capacity}

Extracted SEO Data:
Title: {title}
Meta Description: {meta_description}
H1 Count: {h1_count}
H2 Count: {h2_count}
Word Count: {word_count}
Internal Links: {internal_links}
Images Missing Alt: {missing_alt_images}

Tasks:
0. Tailor every recommendation to the onboarding context above when available.
1. Generate an SEO score between 0 and 100.
2. List key SEO issues using this string format:
   "<Issue> | Evidence: <metric/page signal> | Impact: <why rankings suffer> | Fix: <exact action>".
3. Identify exactly 5 realistic competitors operating in this country/language.
   Include a clickable "url" and in "reason" explain why they directly compete.
   If the business is food/delivery/restaurant, prefer Wolt listing URLs when possible.
4. Identify 10-15 keyword/content gaps with strong search intent in this country/language.
5. Generate exactly {plan_days} unique roadmap tasks (day 1..{plan_days}).
   Every task must include a concrete page/asset target and a KPI.
6. Avoid filler tasks like "develop strategy" without specifics.
7. Do not use unescaped double quotes inside any JSON string value.
8. Do not wrap keywords in double quotes; use plain words or single quotes.

Return ONLY this JSON structure:

{{
  "seo_score": number,
  "issues": ["string"],
  "competitors": [
    {{ "name": "string", "reason": "string", "url": "string" }}
  ],
  "keyword_gaps": ["string"],
  "roadmap": [
    {{ "day": 1, "task": "string" }}
  ]
}}

No additional text."""

FALLBACK_RESULT: AIAnalysisResult = {
    "seo_score": 50,
    "issues": ["AI response parsing failed, using fallback data."],
    "competitors": [],
    "keyword_gaps": [],
    "roadmap": [{"day": 1, "task": "Review homepage SEO basics."}],
}


def _fallback_result(plan_days: int) -> AIAnalysisResult:
    if plan_days < 1:
        return FALLBACK_RESULT
    return {
        "seo_score": 50,
        "issues": ["AI response parsing failed, using fallback data."],
        "competitors": [],
        "keyword_gaps": [],
        "roadmap": [{"day": day, "task": "Review homepage SEO basics."} for day in range(1, plan_days + 1)],
    }


def _compact_retry_suffix(plan_days: int) -> str:
    return f"""
Previous output was invalid or incomplete.
Regenerate complete strict JSON only and keep it compact:
- issues: 4-5 items, each concise.
- competitors: exactly 5.
- keyword_gaps: exactly 10 short phrases.
- roadmap: exactly {plan_days} tasks, each <= 14 words.
- ensure all JSON brackets and braces are closed.
- never use double quotes inside string values; use plain words or single quotes.
No text outside JSON.
"""


def _extract_json(text: str) -> dict | None:
    import json

    if not text:
        return None

    text = text.strip()

    # Remove markdown fences
    if text.startswith("```"):
        text = text.replace("```json", "").replace("```", "").strip()

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1:
        return None

    json_str = text[start : end + 1]

    # Replace smart quotes
    json_str = (
        json_str
        .replace("“", '"')
        .replace("”", '"')
        .replace("‘", "'")
        .replace("’", "'")
    )

    def _escape_inner_quotes(value: str) -> str:
        """
        Escape likely unescaped quotes inside JSON strings.
        Keeps closing quotes intact by checking the next non-space token.
        """
        out: list[str] = []
        in_string = False
        escaped = False
        length = len(value)
        i = 0

        while i < length:
            ch = value[i]
            if escaped:
                out.append(ch)
                escaped = False
                i += 1
                continue

            if ch == "\\":
                out.append(ch)
                escaped = True
                i += 1
                continue

            if ch == '"':
                if not in_string:
                    in_string = True
                    out.append(ch)
                    i += 1
                    continue

                j = i + 1
                while j < length and value[j].isspace():
                    j += 1
                next_char = value[j] if j < length else ""

                # Valid string-close chars in JSON: key close before ":", value close before ",", "}", "]"
                if next_char in {":", ",", "}", "]"}:
                    in_string = False
                    out.append(ch)
                else:
                    out.append('\\"')
                i += 1
                continue

            out.append(ch)
            i += 1

        return "".join(out)

    repaired_json = _escape_inner_quotes(json_str)

    try:
        return json.loads(json_str)
    except Exception:
        try:
            return json.loads(repaired_json)
        except Exception as e:
            print("JSON PARSE ERROR:", json_str)
            print("ERROR:", str(e))
            return None


def _build_user_message(
    url: str,
    country: str,
    language: str,
    scraped: ScrapedData,
    plan_days: int,
    primary_goal: str = "",
    business_offer: str = "",
    target_audience: str = "",
    priority_pages: list[str] | None = None,
    seed_keywords: list[str] | None = None,
    known_competitors: list[str] | None = None,
    execution_capacity: str = "",
) -> str:
    def _text_value(value: str) -> str:
        cleaned = str(value or "").strip()
        return cleaned if cleaned else "Not provided"

    def _list_value(values: list[str] | None) -> str:
        cleaned = [str(item).strip() for item in (values or []) if str(item).strip()]
        return ", ".join(cleaned) if cleaned else "Not provided"

    return USER_TEMPLATE.format(
        url=url,
        country=country,
        language=language,
        plan_days=plan_days,
        primary_goal=_text_value(primary_goal),
        business_offer=_text_value(business_offer),
        target_audience=_text_value(target_audience),
        priority_pages=_list_value(priority_pages),
        seed_keywords=_list_value(seed_keywords),
        known_competitors=_list_value(known_competitors),
        execution_capacity=_text_value(execution_capacity),
        title=scraped.get("title", "") or "",
        meta_description=scraped.get("meta_description", "") or "",
        h1_count=scraped.get("h1_count", 0),
        h2_count=scraped.get("h2_count", 0),
        word_count=scraped.get("word_count", 0),
        internal_links=scraped.get("internal_links", 0),
        missing_alt_images=scraped.get("missing_alt_images", 0),
    )


def _extract_response_text(response: object) -> str:
    content = ""
    for block in getattr(response, "content", []) or []:
        text = getattr(block, "text", None)
        if text:
            content += text
    return content.strip()


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
    )
    return any(token in msg for token in retry_tokens)


def _call_claude(client: Anthropic, user_message: str) -> str:
    last_error: Exception | None = None

    for model in MODEL_CANDIDATES:
        for attempt in range(MAX_RETRIES):
            try:
                response = client.messages.create(
                    model=model,
                    max_tokens=MAX_TOKENS,
                    system=SYSTEM_MESSAGE,
                    messages=[{"role": "user", "content": user_message}],
                    temperature=TEMPERATURE,
                )
                content = _extract_response_text(response)
                stop_reason = getattr(response, "stop_reason", None)
                if stop_reason == "max_tokens":
                    print(f"CLAUDE WARNING: output hit max_tokens for model={model}.")
                if content:
                    return content

                last_error = RuntimeError("Empty Claude response content.")
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_SECONDS * (2 ** attempt) + random.uniform(0, 0.35)
                    print(f"CLAUDE RETRY: model={model} empty-content wait={delay:.2f}s")
                    time.sleep(delay)
                    continue
            except Exception as e:
                last_error = e
                if _is_retryable_error(e) and attempt < MAX_RETRIES - 1:
                    delay = RETRY_BASE_SECONDS * (2 ** attempt) + random.uniform(0, 0.35)
                    print(f"CLAUDE RETRY: model={model} attempt={attempt + 1} wait={delay:.2f}s")
                    time.sleep(delay)
                    continue
            break

    if last_error is not None:
        raise last_error
    return ""


def _is_likely_truncated_json(text: str) -> bool:
    if not text:
        return False
    stripped = text.strip()
    open_braces = stripped.count("{")
    close_braces = stripped.count("}")
    if open_braces > close_braces:
        return True
    if "{" in stripped and "}" not in stripped:
        return True
    if stripped.endswith(","):
        return True
    return False


def _is_low_quality_result(result: AIAnalysisResult, plan_days: int) -> bool:
    issues = [x for x in result.get("issues", []) if isinstance(x, str) and x.strip()]
    competitors = result.get("competitors", [])
    keyword_gaps = [x for x in result.get("keyword_gaps", []) if isinstance(x, str) and x.strip()]
    roadmap = result.get("roadmap", [])

    tasks = []
    for item in roadmap:
        if not isinstance(item, dict):
            continue
        task = str(item.get("task") or "").strip().lower()
        if task:
            tasks.append(task)

    unique_tasks = len(set(tasks))
    min_unique_tasks = max(6, int(plan_days * 0.8))
    return (
        len(issues) < 4
        or len(competitors) < 5
        or len(keyword_gaps) < 8
        or len(roadmap) < plan_days
        or unique_tasks < min_unique_tasks
    )


def _normalize_result(raw: dict, plan_days: int = 30) -> AIAnalysisResult:
    """Ensure parsed dict has the shape and types of AIAnalysisResult."""
    def num(v) -> float:
        if isinstance(v, (int, float)):
            return float(v)
        return 0.0

    def str_list(v) -> list[str]:
        if not isinstance(v, list):
            return []
        return [str(x) for x in v if x is not None]

    def competitor_list(v) -> list[dict]:
        def extract_domain(text: object) -> str:
            source = str(text or "")
            wolt_match = re.search(r"https?://[^\s)]*wolt\.com[^\s)]*", source, re.IGNORECASE)
            if wolt_match:
                return wolt_match.group(0).rstrip("),.;")
            match = (
                re.search(r"https?://[^\s)]+", source, re.IGNORECASE)
                or re.search(r"\b(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s)]*)?", source, re.IGNORECASE)
            )
            if not match:
                return ""
            raw = match.group(0).rstrip("),.;")
            if raw.lower().startswith(("http://", "https://")):
                return raw
            return f"https://{raw}"

        if not isinstance(v, list):
            return []
        out = []
        for item in v:
            if not isinstance(item, dict):
                continue
            name = item.get("name")
            reason = item.get("reason")
            url = item.get("url")
            if name is not None or reason is not None:
                url_text = str(url or "").strip()
                normalized_url = extract_domain(url_text) or extract_domain(reason)
                out.append(
                    {
                        "name": str(name or ""),
                        "reason": str(reason or ""),
                        "url": normalized_url,
                    }
                )
        return out

    def roadmap_list(v) -> list[dict]:
        if not isinstance(v, list):
            return []
        out = []
        for i, item in enumerate(v):
            if not isinstance(item, dict):
                continue
            day = item.get("day")
            task = item.get("task")
            try:
                day_num = int(day) if day is not None else (i + 1)
            except (TypeError, ValueError):
                day_num = i + 1
            if day_num < 1 or day_num > plan_days:
                continue
            out.append({"day": day_num, "task": str(task or "")})
        out.sort(key=lambda x: x["day"])
        return out[:plan_days]

    return {
        "seo_score": min(100, max(0, num(raw.get("seo_score")))),
        "issues": str_list(raw.get("issues")),
        "competitors": competitor_list(raw.get("competitors")),
        "keyword_gaps": str_list(raw.get("keyword_gaps")),
        "roadmap": roadmap_list(raw.get("roadmap")),
    }


def _normalize_external_url(raw_url: object) -> str:
    text = str(raw_url or "").strip()
    if not text:
        return ""

    if text.startswith("//"):
        text = f"https:{text}"
    elif not text.lower().startswith(("http://", "https://")):
        if text.startswith("/"):
            return ""
        text = f"https://{text}"

    text = text.rstrip("),.;")
    try:
        parsed = urlparse(text)
    except Exception:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    cleaned = parsed._replace(fragment="").geturl()
    return cleaned


def _unwrap_duckduckgo_redirect(url: str) -> str:
    try:
        parsed = urlparse(url)
    except Exception:
        return url

    host = parsed.netloc.lower()
    if "duckduckgo.com" not in host:
        return url

    query = parse_qs(parsed.query)
    redirect_target = query.get("uddg", [None])[0]
    if not redirect_target:
        return url
    return unquote(redirect_target)


def _host_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except Exception:
        return ""


def _is_unwanted_competitor_host(host: str) -> bool:
    clean_host = host.lower().replace("www.", "")
    return any(clean_host == blocked or clean_host.endswith(f".{blocked}") for blocked in UNWANTED_COMPETITOR_HOSTS)


def _duckduckgo_result_urls(query: str) -> list[str]:
    if not query.strip():
        return []

    try:
        response = requests.get(
            "https://duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": SEARCH_USER_AGENT},
            timeout=COMPETITOR_SEARCH_TIMEOUT_SECONDS,
        )
        if response.status_code != 200:
            return []
        soup = BeautifulSoup(response.text, "html.parser")
    except Exception:
        return []

    urls: list[str] = []
    for anchor in soup.select("a.result__a"):
        href = str(anchor.get("href") or "").strip()
        if not href:
            continue
        unwrapped = _unwrap_duckduckgo_redirect(href)
        normalized = _normalize_external_url(unwrapped)
        if not normalized:
            continue
        if normalized not in urls:
            urls.append(normalized)
        if len(urls) >= COMPETITOR_SEARCH_MAX_RESULTS:
            break

    return urls


def _score_official_candidate(url: str, competitor_name: str) -> int:
    host = _host_from_url(url)
    if not host:
        return -1000
    if _is_unwanted_competitor_host(host):
        return -900
    if "wolt.com" in host:
        return -300

    score = 0
    path = urlparse(url).path or ""
    if path in {"", "/"}:
        score += 8

    tokens = [token for token in re.split(r"[^a-z0-9]+", competitor_name.lower()) if len(token) >= 3]
    if any(token in host for token in tokens):
        score += 30

    if len(host) <= 24:
        score += 4

    return score


def _resolve_competitor_url(name: str, country: str, language: str) -> str:
    normalized_name = str(name or "").strip()
    if not normalized_name:
        return ""

    official_queries = [
        f'"{normalized_name}" official website {country}',
        f'"{normalized_name}" {country} {language}',
    ]
    candidate_urls: list[str] = []
    for query in official_queries:
        for candidate in _duckduckgo_result_urls(query):
            if candidate not in candidate_urls:
                candidate_urls.append(candidate)
        if len(candidate_urls) >= COMPETITOR_SEARCH_MAX_RESULTS:
            break

    sorted_candidates = sorted(
        candidate_urls,
        key=lambda value: _score_official_candidate(value, normalized_name),
        reverse=True,
    )
    for candidate in sorted_candidates:
        host = _host_from_url(candidate)
        if not host or _is_unwanted_competitor_host(host) or "wolt.com" in host:
            continue
        return candidate

    wolt_queries = [
        f'site:wolt.com "{normalized_name}" {country}',
        f'"{normalized_name}" wolt {country}',
    ]
    for query in wolt_queries:
        for candidate in _duckduckgo_result_urls(query):
            host = _host_from_url(candidate)
            if "wolt.com" in host:
                return candidate

    return ""


def _enrich_competitor_urls(result: AIAnalysisResult, country: str, language: str) -> AIAnalysisResult:
    if not COMPETITOR_LINK_ENRICHMENT:
        return result

    competitors = result.get("competitors")
    if not isinstance(competitors, list):
        return result

    for competitor in competitors:
        if not isinstance(competitor, dict):
            continue
        competitor_name = str(competitor.get("name") or "").strip()
        if not competitor_name:
            competitor["url"] = ""
            continue

        existing = _normalize_external_url(competitor.get("url"))
        existing_host = _host_from_url(existing)
        if existing and existing_host and not _is_unwanted_competitor_host(existing_host):
            competitor["url"] = existing
            continue

        resolved = _resolve_competitor_url(competitor_name, country, language)
        competitor["url"] = resolved if resolved else existing

    return result


def analyze_with_ai(
    url: str,
    country: str,
    language: str,
    scraped: ScrapedData,
    plan_days: int = 30,
    primary_goal: str = "",
    business_offer: str = "",
    target_audience: str = "",
    priority_pages: list[str] | None = None,
    seed_keywords: list[str] | None = None,
    known_competitors: list[str] | None = None,
    execution_capacity: str = "",
) -> AIAnalysisResult:
    """
    Call Claude with retries/model fallback and return structured analysis.
    On API/key/network/JSON failure, returns fallback. Never raises.
    """
    effective_plan_days = 30
    try:
        effective_plan_days = max(7, min(30, int(plan_days)))
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("ERROR: ANTHROPIC_API_KEY not found in environment.")
            return _fallback_result(effective_plan_days)

        client = Anthropic(api_key=api_key)
        user_message = _build_user_message(
            url=url,
            country=country,
            language=language,
            scraped=scraped,
            plan_days=effective_plan_days,
            primary_goal=primary_goal,
            business_offer=business_offer,
            target_audience=target_audience,
            priority_pages=priority_pages,
            seed_keywords=seed_keywords,
            known_competitors=known_competitors,
            execution_capacity=execution_capacity,
        )

        content = _call_claude(client, user_message)

        print("========== RAW CLAUDE RESPONSE ==========")
        print(content)
        print("==========================================")

        if not content:
            return _fallback_result(effective_plan_days)

        parsed = _extract_json(content)
        if parsed is None or not isinstance(parsed, dict):
            print("CLAUDE PARSE: invalid JSON, retrying once with compact instructions.")
            parse_retry_message = user_message + "\n\n" + _compact_retry_suffix(effective_plan_days)
            if _is_likely_truncated_json(content):
                parse_retry_message += "\nKeep every value short to avoid truncation."

            retry_content = _call_claude(client, parse_retry_message)
            if not retry_content:
                return _fallback_result(effective_plan_days)

            print("===== RAW CLAUDE RESPONSE (PARSE RETRY) =====")
            print(retry_content)
            print("==============================================")

            retry_parsed = _extract_json(retry_content)
            if retry_parsed is None or not isinstance(retry_parsed, dict):
                return _fallback_result(effective_plan_days)
            parsed = retry_parsed

        normalized = _normalize_result(parsed, effective_plan_days)
        normalized = _enrich_competitor_urls(normalized, country, language)
        if not _is_low_quality_result(normalized, effective_plan_days):
            return normalized

        print("CLAUDE QUALITY: response too generic, retrying with stricter prompt.")
        quality_retry_message = (
            user_message
            + "\n\nRegenerate now with stricter specificity.\n"
            + "Rules: do not repeat tasks, include concrete page/asset targets, include KPI in every roadmap task, "
            + f"ensure competitors are realistic for the country/language, and output exactly {effective_plan_days} roadmap days."
        )
        improved_content = _call_claude(client, quality_retry_message)
        if not improved_content:
            return normalized

        print("===== RAW CLAUDE RESPONSE (QUALITY RETRY) =====")
        print(improved_content)
        print("================================================")

        improved_parsed = _extract_json(improved_content)
        if improved_parsed is None or not isinstance(improved_parsed, dict):
            return normalized

        improved_normalized = _normalize_result(improved_parsed, effective_plan_days)
        improved_normalized = _enrich_competitor_urls(improved_normalized, country, language)
        return (
            improved_normalized
            if not _is_low_quality_result(improved_normalized, effective_plan_days)
            else normalized
        )
    except Exception as e:
        print("CLAUDE ERROR:", str(e))
        return _fallback_result(effective_plan_days)
