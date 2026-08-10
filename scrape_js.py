"""
scrape_js.py — headless-browser scraper for career boards that render job
listings with client-side JavaScript (Workday, Oracle Cloud/Fusion HCM, ADP).

requests+BeautifulSoup (scrape_generic.py) can't see this content because it
never runs the page's JS. This module uses Playwright to actually load the
page in headless Chromium, wait for the listings to render, then extract them.

One-time setup (see README "Adding Playwright"):
    pip install -r requirements.txt
    playwright install chromium

Usage:
    from scrape_js import scrape_js_sites
    jobs = scrape_js_sites(companies)   # companies: [{"name","url"}, ...]

scrape_js_sites() launches ONE browser for the whole batch (launching Chromium
per-company would make the pipeline dramatically slower) and reuses it across
every company, closing it when done.
"""

import re
from urllib.parse import urlparse

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

PAGE_TIMEOUT_MS = 15000
SELECTOR_TIMEOUT_MS = 8000

# Per-ATS CSS selector for the job link/title element, when known. Falls back
# to a generic <a> text/href heuristic (same one scrape_generic.py uses) for
# hosts not listed here.
_ATS_SELECTORS = {
    "myworkdayjobs.com": "a[data-automation-id='jobTitle']",
    "oraclecloud.com":   "a[data-qa='searchResultsJobTitle'], a.job-title-link",
    "adp.com":           "a.job-tile, a[data-automation='job-title']",
}

_JOB_LINK_HINTS = re.compile(r"(job|career|posting|position|opening|req)", re.IGNORECASE)


def _selector_for(url):
    host = urlparse(url).netloc.lower()
    for fragment, selector in _ATS_SELECTORS.items():
        if fragment in host:
            return selector
    return None


def _extract_with_selector(page, selector, base_url):
    elements = page.eval_on_selector_all(
        selector,
        "els => els.map(e => ({text: e.textContent.trim(), href: e.getAttribute('href')}))",
    )
    jobs = []
    for el in elements:
        if not el["text"] or not el["href"]:
            continue
        jobs.append({
            "title": el["text"],
            "link": page.evaluate("([h, b]) => new URL(h, b).href", [el["href"], base_url]),
        })
    return jobs


def _extract_generic_fallback(page, base_url):
    anchors = page.eval_on_selector_all(
        "a[href]",
        "els => els.map(e => ({text: e.textContent.trim(), href: e.getAttribute('href')}))",
    )
    jobs, seen = [], set()
    for a in anchors:
        text, href = a["text"], a["href"]
        if not text or len(text) < 4 or not href:
            continue
        if not (_JOB_LINK_HINTS.search(href) or _JOB_LINK_HINTS.search(text)):
            continue
        absolute = page.evaluate("([h, b]) => new URL(h, b).href", [href, base_url])
        if absolute in seen:
            continue
        seen.add(absolute)
        jobs.append({"title": text, "link": absolute})
    return jobs


def scrape_js_site(page, name, url, max_jobs=25):
    """
    Scrapes a single JS-rendered careers page using an already-open Playwright
    page. Returns [] on any failure (timeout, navigation error, no matches)
    so one bad company never takes down the batch.
    """
    try:
        page.goto(url, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")
    except PlaywrightTimeoutError:
        print(f"[scrape_js] Timed out loading '{name}' ({url}).")
        return []
    except PlaywrightError as e:
        print(f"[scrape_js] Navigation failed for '{name}': {e}")
        return []

    selector = _selector_for(url)

    try:
        if selector:
            page.wait_for_selector(selector, timeout=SELECTOR_TIMEOUT_MS)
            raw_jobs = _extract_with_selector(page, selector, url)
        else:
            # No known selector for this host — give the page a moment to
            # finish rendering, then fall back to the generic link heuristic.
            page.wait_for_timeout(1500)
            raw_jobs = _extract_generic_fallback(page, url)
    except PlaywrightTimeoutError:
        print(f"[scrape_js] '{name}': listings never appeared (selector timeout) — page may need a longer wait or a different selector.")
        return []

    jobs = [{
        "company": name,
        "title": j["title"],
        "link": j["link"],
        "location": "Unknown",
        "description": "",
    } for j in raw_jobs[:max_jobs]]

    print(f"[scrape_js] Found {len(jobs)} jobs at '{name}' (rendered).")
    return jobs


def scrape_js_sites(companies, max_jobs=25):
    """
    Scrapes a batch of JS-rendered companies, reusing a single browser
    instance for all of them.

    Args:
        companies: [{"name": str, "url": str}, ...]
    Returns:
        combined list of job dicts across all companies (possibly empty)
    """
    if not PLAYWRIGHT_AVAILABLE:
        print(
            "[scrape_js] playwright is not installed — skipping "
            f"{len(companies)} JS-rendered companies. Run:\n"
            "  pip install playwright && playwright install chromium"
        )
        return []

    if not companies:
        return []

    all_jobs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            for company in companies:
                all_jobs.extend(scrape_js_site(page, company["name"], company["url"], max_jobs=max_jobs))
        finally:
            browser.close()

    return all_jobs
