import requests                          # FIX 2: was missing — caused NameError


def scrape_lever(company):
    """
    Fetches job listings from Lever's public posting API.
    Works for any company that uses Lever as their ATS.
    Examples: scrape_lever("netflix"), scrape_lever("datadog")
    """
    url = f"https://api.lever.co/v0/postings/{company}?mode=json"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        print(f"[scrape_lever] Request failed for '{company}': {e}")
        return []
    except ValueError:
        print(f"[scrape_lever] Invalid JSON from Lever for '{company}'")
        return []

    # Lever returns a flat list, not wrapped in a key
    if not isinstance(data, list):
        print(f"[scrape_lever] Unexpected response format for '{company}'")
        return []

    jobs = []
    for job in data:
        try:
            jobs.append({
                "company":     company,
                "title":       job["text"],
                "link":        job["hostedUrl"],
                "location":    job.get("categories", {}).get("location", "Remote"),
                "description": job.get("descriptionPlain", "")
            })
        except KeyError as e:
            print(f"[scrape_lever] Missing field {e} — skipping job")
            continue

    print(f"[scrape_lever] Found {len(jobs)} jobs at '{company}'.")
    return jobs
