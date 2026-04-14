# import all external functions that are called from this function
from scrape_greenhouse.py import scrape_greenhouse()
from scrape_lever.py import scrape_lever()
from scrape_indeed.py import scrape_indeed()
from dedupe_jobs.py import dedupe_jobs()
from advanced_fit_score.py import advanced_fit_score()
from estimate_salary.py import estimate_salary()
from send_slack_alert.py import send_slack_alert()
from send_email.py import send_email()

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
