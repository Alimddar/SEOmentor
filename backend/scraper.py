"""Homepage scraper: fetch URL and extract comprehensive SEO metrics.

Extracts on-page signals including meta tags, headings, link profile,
structured data, Open Graph, canonical, robots directives, and more.
Does NOT crawl subpages.
"""

import json as _json
import re
from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

from models import ScrapedData

_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

SAFE_DEFAULT: ScrapedData = {
    "title": "",
    "meta_description": "",
    "h1_count": 0,
    "h2_count": 0,
    "h3_count": 0,
    "word_count": 0,
    "internal_links": 0,
    "external_links": 0,
    "missing_alt_images": 0,
    "total_images": 0,
    "canonical_url": "",
    "robots_meta": "",
    "has_viewport_meta": False,
    "og_title": "",
    "og_description": "",
    "og_image": "",
    "has_structured_data": False,
    "structured_data_types": [],
    "hreflang_tags": [],
    "h1_texts": [],
    "http_status": 0,
    "response_time_ms": 0,
}


def scrape_homepage(url: str) -> ScrapedData:
    """
    Fetch the homepage at `url` and return structured SEO metrics.
    On any failure (network, invalid URL, parse error), returns safe defaults.
    """
    response_time_ms = 0
    http_status = 0

    try:
        response = requests.get(url, timeout=12, headers=_REQUEST_HEADERS)
        http_status = response.status_code
        response_time_ms = int(response.elapsed.total_seconds() * 1000)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        html = response.text
    except (requests.RequestException, ValueError, OSError):
        result = dict(SAFE_DEFAULT)
        result["http_status"] = http_status
        result["response_time_ms"] = response_time_ms
        return result

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        result = dict(SAFE_DEFAULT)
        result["http_status"] = http_status
        result["response_time_ms"] = response_time_ms
        return result

    parsed_url = urlparse(url)
    base_domain = (parsed_url.netloc or "").lower().strip()
    base_scheme = parsed_url.scheme or "https"
    base_netloc = parsed_url.netloc or ""
    base_url = f"{base_scheme}://{base_netloc}"

    # --- Structured data (extract before decomposing scripts) ---
    structured_data_types: list[str] = []
    for script_tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            ld = _json.loads(script_tag.string or "")
            items = ld if isinstance(ld, list) else [ld]
            for item in items:
                if isinstance(item, dict):
                    sd_type = item.get("@type", "")
                    if isinstance(sd_type, list):
                        structured_data_types.extend(str(t) for t in sd_type if t)
                    elif sd_type:
                        structured_data_types.append(str(sd_type))
        except Exception:
            pass
    structured_data_types = list(dict.fromkeys(structured_data_types))[:10]

    # Remove script and style before text/structural extraction
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()

    # --- Title ---
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    # --- Meta description ---
    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_description = ""
    if meta_desc_tag and meta_desc_tag.get("content"):
        meta_description = (meta_desc_tag["content"] or "").strip()

    # --- Canonical URL ---
    canonical_url = ""
    canonical_tag = soup.find("link", attrs={"rel": "canonical"})
    if canonical_tag and canonical_tag.get("href"):
        canonical_url = (canonical_tag["href"] or "").strip()

    # --- Robots meta ---
    robots_meta = ""
    robots_tag = soup.find("meta", attrs={"name": re.compile(r"^robots$", re.I)})
    if robots_tag and robots_tag.get("content"):
        robots_meta = (robots_tag["content"] or "").strip()

    # --- Viewport meta ---
    viewport_tag = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})
    has_viewport_meta = viewport_tag is not None

    # --- Open Graph ---
    og_title = ""
    og_desc = ""
    og_image = ""
    for prop, target in [("og:title", "og_title"), ("og:description", "og_desc"), ("og:image", "og_image")]:
        tag = soup.find("meta", attrs={"property": prop})
        if tag and tag.get("content"):
            val = (tag["content"] or "").strip()
            if target == "og_title":
                og_title = val
            elif target == "og_desc":
                og_desc = val
            else:
                og_image = val

    # --- Hreflang ---
    hreflang_tags: list[str] = []
    for link in soup.find_all("link", attrs={"rel": "alternate", "hreflang": True}):
        lang_val = (link.get("hreflang") or "").strip()
        if lang_val and lang_val not in hreflang_tags:
            hreflang_tags.append(lang_val)

    # --- Headings ---
    h1_tags = soup.find_all("h1")
    h1_count = len(h1_tags)
    h1_texts = [h.get_text(strip=True)[:120] for h in h1_tags[:5]]
    h2_count = len(soup.find_all("h2"))
    h3_count = len(soup.find_all("h3"))

    # --- Word count (visible text only) ---
    visible_text = soup.get_text(separator=" ", strip=True)
    word_count = len(visible_text.split()) if visible_text else 0

    # --- Links ---
    internal_links = 0
    external_links = 0
    for a in soup.find_all("a", href=True):
        href = (a["href"] or "").strip()
        if not href or href.startswith("#") or href.lower().startswith(("javascript:", "mailto:", "tel:")):
            continue
        if href.startswith("/"):
            internal_links += 1
            continue
        try:
            resolved = urlparse(urljoin(base_url, href))
            resolved_host = (resolved.netloc or "").lower()
            if resolved_host == base_domain:
                internal_links += 1
            elif resolved_host:
                external_links += 1
        except Exception:
            continue

    # --- Images ---
    all_images = soup.find_all("img")
    total_images = len(all_images)
    missing_alt_images = 0
    for img in all_images:
        alt = img.get("alt")
        if alt is None or (isinstance(alt, str) and alt.strip() == ""):
            missing_alt_images += 1

    return {
        "title": title,
        "meta_description": meta_description,
        "h1_count": h1_count,
        "h2_count": h2_count,
        "h3_count": h3_count,
        "word_count": word_count,
        "internal_links": internal_links,
        "external_links": external_links,
        "missing_alt_images": missing_alt_images,
        "total_images": total_images,
        "canonical_url": canonical_url,
        "robots_meta": robots_meta,
        "has_viewport_meta": has_viewport_meta,
        "og_title": og_title,
        "og_description": og_desc,
        "og_image": og_image,
        "has_structured_data": len(structured_data_types) > 0,
        "structured_data_types": structured_data_types,
        "hreflang_tags": hreflang_tags[:10],
        "h1_texts": h1_texts,
        "http_status": http_status,
        "response_time_ms": response_time_ms,
    }
