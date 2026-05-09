import os
import requests                          # FIX 1: was missing — caused NameError
from bs4 import BeautifulSoup
from urllib.parse import quote_plus


def scrape_indeed(role=None, location=None, max_jobs=20):
    """
    Scrapes Indeed for job listings matching role + location.
    Falls back to env vars TARGET_ROLE / TARGET_LOCATION if not passed in.

    Note: Indeed aggressively blocks automated requests. If you keep getting
    blocked, install JobSpy (pip install python-jobspy) and swap the body of
    this function for the JobSpy version shown in FIX_GUIDE.md.
    """
    role     = role     or os.getenv("TARGET_ROLE",     "QA Automation Engineer")
    location = location or os.getenv("TARGET_LOCATION", "Remote")

    url = (
        f"https://www.indeed.com/jobs"
        f"?q={quote_plus(role)}&l={quote_plus(location)}&sort=date"
    )

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"[scrape_indeed] Request failed: {e}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")

    # Check for bot-blocking page
    page_title = soup.title.text.lower() if soup.title else ""
    if "blocked" in page_title or "captcha" in page_title:
        print("[scrape_indeed] Request was blocked by Indeed. Try JobSpy instead.")
        return []

    jobs = []
    # FIX 9 (also): correct Indeed selector — was "base-card" (LinkedIn's class)
    for card in soup.select(".job_seen_beacon"):
        try:
            title_el   = card.select_one("h2 span")
            company_el = card.select_one(".companyName")
            loc_el     = card.select_one(".companyLocation")
            anchor     = card.select_one("h2 a")

            title   = title_el.get_text(strip=True)   if title_el   else ""
            company = company_el.get_text(strip=True)  if company_el else "Indeed Listing"
            loc     = loc_el.get_text(strip=True)      if loc_el     else location
            link    = ("https://www.indeed.com" + anchor["href"]) if anchor else ""

            if not title:
                continue

            jobs.append({
                "company":     company,
                "title":       title,
                "link":        link,
                "location":    loc,
                "description": ""
            })

            if len(jobs) >= max_jobs:
                break

        except (AttributeError, TypeError, KeyError):
            continue

    print(f"[scrape_indeed] Found {len(jobs)} jobs.")
    return jobs
