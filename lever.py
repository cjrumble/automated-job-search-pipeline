def scrape_lever(company):
    url = f"https://api.lever.co/v0/postings/{company}?mode=json"
    res = requests.get(url).json()

    jobs = []
    for job in res:
        jobs.append({
            "company": company,
            "title": job["text"],
            "link": job["hostedUrl"],
            "location": job["categories"]["location"],
            "description": job.get("description", "")
        })
    return jobs
