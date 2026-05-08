from advanced_fit_score import advanced_fit_score
from dedupe_jobs import dedupe_jobs
from estimate_salary import estimate_salary
from scrape_greenhouse import scrape_greenhouse

def run_pipeline():
    jobs = []
    jobs += scrape_greenhouse("stripe")

    jobs = dedupe_jobs(jobs)

    for job in jobs:
        job["Fit Score"] = advanced_fit_score(job)
        job["Salary"] = estimate_salary(job["title"])

    return jobs


if __name__ == "__main__":
    run_pipeline()
