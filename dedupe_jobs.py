def dedupe_jobs(jobs):
    seen = set()
    unique = []

    for job in jobs:
        key = (job["company"], job["title"])
        if key not in seen:
            seen.add(key)
            unique.append(job)

    return unique
