"""
daily_job_automation.py — legacy standalone script (superseded by run_pipeline.py)

This was the original entry point. It uses Selenium to scrape Indeed directly,
which is now blocked (Indeed returns 403). The production pipeline uses
run_pipeline.py instead, which sources jobs from Greenhouse, Lever, and RemoteOK.

Kept here for reference only. Run with: python daily_job_automation.py
Requires: Chrome + chromedriver installed and in PATH.
"""

import time
import pandas as pd
import datetime
import os
import bs4
from scrape_greenhouse import scrape_greenhouse

CSV_FILE = "job_applications.csv"
MAX_JOBS = 20
SEARCH_URL = "https://www.indeed.com/jobs?q=QA+Automation&l=Remote"


def calculate_fit_score(title, location):
    score = 5
    title_lower = title.lower()
    keywords = ["sdet", "automation", "cypress", "selenium", "api"]
    score += sum(1 for k in keywords if k in title_lower)
    if "senior" in title_lower:
        score += 1
    if "remote" in location.lower():
        score += 1
    return min(score, 10)


def main():
    try:
        from selenium import webdriver
    except ImportError:
        print("selenium is not installed. Run: pip install selenium")
        return

    options = webdriver.ChromeOptions()
    options.add_argument("--headless")

    try:
        driver = webdriver.Chrome(options=options)
    except Exception as e:
        print(f"Chrome/chromedriver not available: {e}")
        print("Use run_pipeline.py instead — it doesn't require Chrome.")
        return

    driver.get(SEARCH_URL)
    time.sleep(5)

    for _ in range(6):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)

    soup = bs4.BeautifulSoup(driver.page_source, "html.parser")
    job_cards = soup.find_all("div", class_="job_seen_beacon")
    is_blocked = soup.title and soup.title.text and "blocked" in soup.title.text.lower()

    results = []

    if is_blocked:
        try:
            for job in scrape_greenhouse("stripe")[:MAX_JOBS]:
                fit_score = calculate_fit_score(job.get("title", ""), job.get("location", ""))
                results.append({
                    "Company": job.get("company", "Unknown"),
                    "Job Title": job.get("title", ""),
                    "Link": job.get("link", ""),
                    "Date Posted": datetime.datetime.today().strftime("%Y-%m-%d"),
                    "Salary": "N/A",
                    "Fit Score": fit_score,
                    "Priority": 0,
                    "Application Status": "Not Applied",
                })
        except Exception:
            pass
    else:
        for job in job_cards[:MAX_JOBS]:
            try:
                title = job.find("h3").text.strip()
                company = job.find("h4").text.strip()
                location = job.find("span").text.strip()
                link = job.find("a")["href"]
                results.append({
                    "Company": company,
                    "Job Title": title,
                    "Link": link,
                    "Date Posted": datetime.datetime.today().strftime("%Y-%m-%d"),
                    "Salary": "N/A",
                    "Fit Score": calculate_fit_score(title, location),
                    "Priority": 0,
                    "Application Status": "Not Applied",
                })
            except Exception:
                continue

    driver.quit()

    df = pd.DataFrame(results)
    if not df.empty and "Fit Score" in df.columns:
        df = df.sort_values(by="Fit Score", ascending=False)
        df["Priority"] = range(1, len(df) + 1)

    if os.path.exists(CSV_FILE):
        try:
            existing_df = pd.read_csv(CSV_FILE)
            df = pd.concat([existing_df, df], ignore_index=True)
        except pd.errors.EmptyDataError:
            pass

    if "Fit Score" in df.columns:
        df = df.sort_values(by="Fit Score", ascending=False)
        df["Priority"] = range(1, len(df) + 1)

    df.to_csv(CSV_FILE, index=False)
    print(f"Added {len(df)} jobs to {CSV_FILE}")


if __name__ == "__main__":
    main()
