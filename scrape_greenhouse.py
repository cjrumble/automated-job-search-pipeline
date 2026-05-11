import requests


def scrape_greenhouse(company):
    """
    Fetches all job listings for a company from Greenhouse's public API.

    Args:
        company: the Greenhouse board slug (e.g. "stripe", "airbnb")
    Returns:
        list of job dicts with keys: company, title, link, location, description
        Returns [] on any error so the pipeline continues.
    """
    url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        print(f"[scrape_greenhouse] Request failed for '{company}': {e}")
        return []
    except ValueError:
        print(f"[scrape_greenhouse] Invalid JSON from Greenhouse for '{company}'")
        return []

    if "jobs" not in data:
        print(f"[scrape_greenhouse] Unexpected response format for '{company}'")
        return []

    jobs = []
    for job in data["jobs"]:
        try:
            jobs.append({
                "company":     company,
                "title":       job["title"],
                "link":        job["absolute_url"],
                "location":    job["location"]["name"],
                "description": job.get("content", ""),
            })
        except KeyError as e:
            print(f"[scrape_greenhouse] Missing field {e} in job — skipping")
            continue

    print(f"[scrape_greenhouse] Found {len(jobs)} jobs at '{company}'.")
    return jobs
