import time
import pandas as pd
from datetime import datetime
from selenium import webdriver
from bs4 import BeautifulSoup
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# ---------------- CONFIG ----------------
SEARCH_URL = "https://www.linkedin.com/jobs/search/?keywords=SDET%20QA%20Automation&location=United%20States"
MAX_JOBS = 25

# ---------------- GOOGLE SHEETS ----------------
scope = ["https://spreadsheets.google.com/feeds",
         "https://www.googleapis.com/auth/drive"]

creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)

SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1q1qRIyIQFFNFSYsngkgHPzWUL6vCcXqD"
sheet = client.open_by_url(SPREADSHEET_URL)

today_tab = datetime.today().strftime("%Y-%m-%d")
worksheet = sheet.add_worksheet(title=today_tab, rows="100", cols="10")

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

soup = BeautifulSoup(driver.page_source, "html.parser")
jobs = soup.find_all("div", class_="base-card")

results = []

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
            "Date Posted": datetime.today().strftime("%Y-%m-%d"),
            "Salary": "N/A",
            "Fit Score": fit_score,
            "Priority": 0,
            "Status": "Not Applied"
        })

    except:
        continue

driver.quit()

# ---------------- PRIORITY RANKING ----------------
df = pd.DataFrame(results)

df = df.sort_values(by="Fit Score", ascending=False)
df["Priority"] = range(1, len(df) + 1)

# ---------------- PUSH TO SHEET ----------------
headers = ["Company","Job Title","Link","Date Posted","Salary","Fit Score","Priority","Application Status"]
worksheet.append_row(headers)

for _, row in df.iterrows():
    worksheet.append_row([
        row["Company"],
        row["Job Title"],
        row["Link"],
        row["Date Posted"],
        row["Salary"],
        row["Fit Score"],
        row["Priority"],
        row["Status"]
    ])
print(f"✅ Added {len(df)} jobs to {today_tab}")
