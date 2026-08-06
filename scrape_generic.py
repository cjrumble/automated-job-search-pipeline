"""
scrape_generic.py — best-effort fallback scraper for company career sites
that don't run on Greenhouse or Lever (e.g. Workday, Oracle Cloud/Taleo, ADP,
or a fully custom careers page).

IMPORTANT LIMITATION: unlike Greenhouse/Lever, these sites have no public,
documented JSON API. Most of them (Workday, Oracle Cloud "CX" boards, ADP)
render listings via client-side JavaScript, which a plain requests+BeautifulSoup
GET request cannot execute. This scraper does a static HTML fetch and looks
for anchor tags that look like job postings; it will legitimately return an
empty list for JS-rendered boards. That's expected, not a bug — see the
README's "Generic sites" section for what to do about those companies
(a headless-browser scraper, or the company's own ATS-specific integration,
would be required).
"""

import re
import requests

# Words that suggest an <a> tag points at an individual job posting rather
# than a nav link, footer link, etc.
_JOB_LINK_HINTS = re.compile(
    r"(job|career|posting|position|opening|req)", re.IGNORECASE
)


def scrape_generic(name, url, max_jobs=25):
    """
    Attempts a static-HTML best-effort scrape of a company's careers page.

    Args:
        name: company display name (for tagging results / logging)
        url:  the careers page URL from companies.json
        max_jobs: cap on returned listings
    Returns:
        list of job dicts with keys: company, title, link, location, description
        Returns [] on any error, or if the page has no JS-independent job
        links (e.g. Workday/Oracle boards that render client-side).
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[scrape_generic] Request failed for '{name}': {e}")
        return []

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("[scrape_generic] beautifulsoup4 is not installed — skipping.")
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    jobs = []
    seen_links = set()

    for a in soup.find_all("a", href=True):
        link_text = a.get_text(strip=True)
        href = a["href"]

        if not link_text or len(link_text) < 4:
            continue
        if not _JOB_LINK_HINTS.search(href) and not _JOB_LINK_HINTS.search(link_text):
            continue

        absolute_link = requests.compat.urljoin(url, href)
        if absolute_link in seen_links:
            continue
        seen_links.add(absolute_link)

        jobs.append({
            "company":     name,
            "title":       link_text,
            "link":        absolute_link,
            "location":    "Unknown",
            "description": "",
        })

        if len(jobs) >= max_jobs:
            break

    if not jobs:
        print(
            f"[scrape_generic] No static job links found for '{name}' "
            f"({url}) — likely a JS-rendered board (Workday/Oracle/ADP)."
        )
    else:
        print(f"[scrape_generic] Found {len(jobs)} candidate links at '{name}' (unverified — static scrape).")

    return jobs
