def run_pipeline():
    jobs = []

    jobs += scrape_greenhouse("stripe")
    jobs += scrape_lever("netflix")
    jobs += scrape_indeed()

    jobs = dedupe_jobs(jobs)

    for job in jobs:
        job["Fit Score"] = advanced_fit_score(job)
        job["Salary"] = estimate_salary(job["title"])

    # Convert to DataFrame → rank → push to Sheets

    send_slack_alert(jobs)
    send_email(jobs)
