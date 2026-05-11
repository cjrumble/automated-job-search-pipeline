"""
scrape_indeed.py — repointed to RemoteOK (Indeed blocks all automated scrapers)

Indeed now returns 403 Forbidden to all bots/scripts, including JobSpy.
RemoteOK (https://remoteok.com/api) is a free public JSON API for remote jobs
that requires no authentication and is intentionally open for developer use.

The function signature is unchanged so run_pipeline.py needs no edits.
"""

import os
import requests


REMOTEOK_API = "https://remoteok.com/api"


def _role_to_tags(role: str) -> list[str]:
    """Map a job-title string to RemoteOK tag keywords."""
    role_lower = role.lower()
    tags = []
    if any(k in role_lower for k in ("qa", "quality")):
        tags.append("qa")
    if any(k in role_lower for k in ("automation", "sdet", "selenium", "cypress")):
        tags.append("testing")
    if any(k in role_lower for k in ("engineer", "developer", "dev")):
        tags.append("engineer")
    return tags or ["qa", "testing"]


def scrape_indeed(role=None, location=None, max_jobs=20):
    """
    Returns remote job listings from RemoteOK's public API.

    The role/location parameters are kept for drop-in compatibility with
    run_pipeline.py. Location is ignored because RemoteOK lists remote-only jobs.

    Args:
        role:     job title / keywords (defaults to TARGET_ROLE env var)
        location: unused (all RemoteOK jobs are remote)
        max_jobs: cap on returned listings

    Returns:
        list of job dicts with keys: company, title, link, location, description
    """
    role = role or os.getenv("TARGET_ROLE", "QA Automation Engineer")
    tags = _role_to_tags(role)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    raw_jobs: list[dict] = []

    for tag in tags:
        try:
            response = requests.get(
                REMOTEOK_API,
                params={"tag": tag},
                headers=headers,
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            print(f"[scrape_indeed/remoteok] Request failed for tag={tag!r}: {e}")
            continue
        except ValueError:
            print(f"[scrape_indeed/remoteok] Invalid JSON for tag={tag!r}")
            continue

        for item in data:
            # First element of the API response is a legal-notice dict, not a job
            if not isinstance(item, dict) or "position" not in item:
                continue
            raw_jobs.append({
                "company":     item.get("company",     "Unknown"),
                "title":       item.get("position",    ""),
                "link":        item.get("url",         ""),
                "location":    "Remote",
                "description": item.get("description", ""),
            })

    # Deduplicate by job URL across tags
    seen: set[str] = set()
    unique: list[dict] = []
    for job in raw_jobs:
        url = job["link"]
        if url and url not in seen:
            seen.add(url)
            unique.append(job)

    result = unique[:max_jobs]
    print(f"[scrape_indeed] Found {len(result)} jobs via RemoteOK (tags: {tags}).")
    return result
