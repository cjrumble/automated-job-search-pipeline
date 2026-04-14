import requests

def scrape_greenhouse(company):
    url = f"https://boards-api.greenhouse.io/v1/boards/{company}/jobs"
    res = requests.get(url).json()

    jobs = []
    for job in res["jobs"]:
        jobs.append({
            "company": company,
            "title": job["title"],
            "link": job["absolute_url"],
            "location": job["location"]["name"],
            "description": job.get("content", "")
        })
    return jobs
