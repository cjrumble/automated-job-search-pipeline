def advanced_fit_score(job):
    score = 5
    text = (job["title"] + job["description"]).lower()

    keywords = ["selenium", "cypress", "api", "python", "automation"]

    for k in keywords:
        if k in text:
            score += 1

    if "senior" in text:
        score += 1

    if "remote" in job["location"].lower():
        score += 1

    return min(score, 10)
