import time
import pandas as pd
import datetime
import os
import bs4
from selenium import webdriver
from scrape_greenhouse import scrape_greenhouse

# CSV file path
CSV_FILE = "job_applications.csv"
MAX_JOBS = 20
SEARCH_URL = "https://www.indeed.com/jobs?q=QA+Automation&l=Remote"
# ---------------- SCRAPER ----------------
options = webdriver.ChromeOptions()
options.add_argument("--headless")

driver = webdriver.Chrome(options=options)
driver.get(SEARCH_URL)
time.sleep(5)

# Scroll to load jobs
for _ in range(6):
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)

soup = bs4.BeautifulSoup(driver.page_source, "html.parser")
jobs = soup.find_all("div", class_="base-card")

results = []
is_blocked = soup.title and soup.title.text and "blocked" in soup.title.text.lower()

# ---------------- SCORING ----------------
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


if is_blocked:
    try:
        fallback_jobs = scrape_greenhouse("stripe")[:MAX_JOBS]
        for job in fallback_jobs:
            fit_score = calculate_fit_score(job.get("title", ""), job.get("location", ""))
            results.append({
                "Company": job.get("company", "Unknown"),
                "Job Title": job.get("title", ""),
                "Link": job.get("link", ""),
                "Date Posted": datetime.datetime.today().strftime("%Y-%m-%d"),
                "Salary": "N/A",
                "Fit Score": fit_score,
                "Priority": 0,
                "Application Status": "Not Applied"
            })
    except Exception:
        pass

# ---------------- PARSE JOBS ----------------
for job in jobs[:MAX_JOBS]:
    try:
        title = job.find("h3").text.strip()
        company = job.find("h4").text.strip()
        location = job.find("span").text.strip()
        link = job.find("a")["href"]  # REAL JOB LINK

        fit_score = calculate_fit_score(title, location)

        results.append({
            "Company": company,
            "Job Title": title,
            "Link": link,
            "Date Posted": datetime.datetime.today().strftime("%Y-%m-%d"),
            "Salary": "N/A",
            "Fit Score": fit_score,
            "Priority": 0,
            "Application Status": "Not Applied"
        })

    except Exception:
        continue

driver.quit()

# ---------------- PRIORITY RANKING ----------------
df = pd.DataFrame(results)

if not df.empty and "Fit Score" in df.columns:
    df = df.sort_values(by="Fit Score", ascending=False)
    df["Priority"] = range(1, len(df) + 1)

# Check if CSV exists and load existing data, or create new DataFrame
if os.path.exists(CSV_FILE):
    try:
        existing_df = pd.read_csv(CSV_FILE)
        df = pd.concat([existing_df, df], ignore_index=True)
    except pd.errors.EmptyDataError:
        pass

# Sort and assign priority after merging all data
if "Fit Score" in df.columns:
    df = df.sort_values(by="Fit Score", ascending=False)
    df["Priority"] = range(1, len(df) + 1)

# Save to CSV
df.to_csv(CSV_FILE, index=False)
print(f"✅ Added {len(df)} jobs to {CSV_FILE}")
