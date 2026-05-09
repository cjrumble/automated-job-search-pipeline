"""
scrape_linkedin.py  —  NEW FILE (implements the missing LinkedIn scraper)

LinkedIn is listed in the README architecture diagram but no scraper existed.

Uses linkedin_jobs_scraper which operates via your local Chrome session,
making it less likely to be blocked than raw HTTP requests.

Install: pip install linkedin_jobs_scraper
         Also needs Chrome + matching chromedriver in PATH.

Enable by setting LINKEDIN_ENABLED=true in your .env file.
"""

import os

try:
    from linkedin_jobs_scraper import LinkedinScraper
    from linkedin_jobs_scraper.events import Events, EventData
    from linkedin_jobs_scraper.query import Query, QueryOptions, QueryFilters
    from linkedin_jobs_scraper.filters import RelevanceFilters, TimeFilters, TypeFilters
    LINKEDIN_SCRAPER_AVAILABLE = True
except ImportError:
    LINKEDIN_SCRAPER_AVAILABLE = False

# Results accumulate here between the async callback and the return value
_collected_jobs = []


def _on_data(data: "EventData"):
    _collected_jobs.append({
        "company":     data.company     or "",
        "title":       data.title       or "",
        "link":        data.link        or "",
        "location":    data.place       or "",
        "description": data.description or ""
    })


def _on_error(error):
    print(f"[scrape_linkedin] Scraper error: {error}")


def scrape_linkedin(role=None, location=None, max_results=25):
    """
    Scrapes LinkedIn Jobs for matching postings.

    Args:
        role:        job title to search, e.g. "QA Automation Engineer"
        location:    location string, e.g. "Remote" or "San Francisco, CA"
        max_results: maximum number of jobs to return (default 25)

    Returns:
        list of job dicts with keys: company, title, link, location, description

    Requirements:
        pip install linkedin_jobs_scraper
        Chrome + chromedriver installed and in PATH
        LINKEDIN_ENABLED=true in .env
    """
    global _collected_jobs
    _collected_jobs = []

    if not LINKEDIN_SCRAPER_AVAILABLE:
        print(
            "[scrape_linkedin] linkedin_jobs_scraper not installed.\n"
            "Run: pip install linkedin_jobs_scraper"
        )
        return []

    role     = role     or os.getenv("TARGET_ROLE",     "QA Automation Engineer")
    location = location or os.getenv("TARGET_LOCATION", "Remote")

    try:
        scraper = LinkedinScraper(
            chrome_executable_path=None,   # uses chromedriver from PATH
            headless=True,
            max_workers=1,
            slow_mo=1.5,                   # polite delay between requests (seconds)
            page_load_timeout=30
        )

        scraper.on(Events.DATA,  _on_data)
        scraper.on(Events.ERROR, _on_error)

        scraper.run([
            Query(
                query=role,
                options=QueryOptions(
                    locations=[location],
                    limit=max_results,
                    filters=QueryFilters(
                        relevance=RelevanceFilters.RECENT,
                        time=TimeFilters.DAY,             # posted in last 24 hours
                        type=[TypeFilters.FULL_TIME]
                    )
                )
            )
        ])

    except Exception as e:
        print(
            f"[scrape_linkedin] Scraper failed: {e}\n"
            "Check that Chrome and chromedriver are installed and in your PATH."
        )
        return []

    result = _collected_jobs[:max_results]
    print(f"[scrape_linkedin] Found {len(result)} LinkedIn jobs.")
    return result
