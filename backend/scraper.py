"""Homepage scraper: fetch URL and extract SEO metrics.

Extracts: title, meta_description, h1_count, h2_count, word_count,
internal_links, missing_alt_images.
Does NOT crawl subpages.
"""

from urllib.parse import urlparse, urljoin

import requests
from bs4 import BeautifulSoup

from models import ScrapedData

SAFE_DEFAULT: ScrapedData = {
    "title": "",
    "meta_description": "",
    "h1_count": 0,
    "h2_count": 0,
    "word_count": 0,
    "internal_links": 0,
    "missing_alt_images": 0,
}


def scrape_homepage(url: str) -> ScrapedData:
    """
    Fetch the homepage at `url` and return structured SEO metrics.
    On any failure (network, invalid URL, parse error), returns safe defaults.
    """
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or "utf-8"
        html = response.text
    except (requests.RequestException, ValueError, OSError):
        return SAFE_DEFAULT

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return SAFE_DEFAULT

    # Remove script and style before any text/structural extraction
    for tag in soup.find_all(["script", "style"]):
        tag.decompose()

    parsed_url = urlparse(url)
    base_domain = (parsed_url.netloc or "").lower().strip()

    # Title
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()

    # Meta description
    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    meta_description = ""
    if meta_desc_tag and meta_desc_tag.get("content"):
        meta_description = (meta_desc_tag["content"] or "").strip()

    # Heading counts
    h1_count = len(soup.find_all("h1"))
    h2_count = len(soup.find_all("h2"))

    # Word count: visible text only (script/style already removed)
    visible_text = soup.get_text(separator=" ", strip=True)
    word_count = len(visible_text.split()) if visible_text else 0

    # Internal links: same domain or path starting with /
    internal_links = 0
    base_scheme = parsed_url.scheme or "https"
    base_netloc = parsed_url.netloc or ""
    base_url = f"{base_scheme}://{base_netloc}"

    for a in soup.find_all("a", href=True):
        href = (a["href"] or "").strip()
        if not href or href.startswith("#") or href.lower().startswith(("javascript:", "mailto:", "tel:")):
            continue
        if href.startswith("/"):
            internal_links += 1
            continue
        try:
            resolved = urlparse(urljoin(base_url, href))
            if (resolved.netloc or "").lower() == base_domain:
                internal_links += 1
        except Exception:
            continue

    # Images without alt
    missing_alt_images = 0
    for img in soup.find_all("img"):
        if img.get("alt") is None or (isinstance(img.get("alt"), str) and img.get("alt").strip() == ""):
            missing_alt_images += 1

    return {
        "title": title,
        "meta_description": meta_description,
        "h1_count": h1_count,
        "h2_count": h2_count,
        "word_count": word_count,
        "internal_links": internal_links,
        "missing_alt_images": missing_alt_images,
    }
