# automated-job-search-pipeline

Daily Real-time Job Scraping Automation in Python

Fully autonomous, daily, production-grade job search pipeline that runs on
GitHub Actions every morning and delivers ranked results to Google Sheets,
email, and Slack — no manual work required.

## What it does

Every time it runs:
- Scrapes 3+ job boards (Greenhouse, Lever, RemoteOK) for fresh listings
- Deduplicates across all sources
- Scores each job 1–10 based on keyword fit and seniority
- Ranks by priority (#1 = apply first)
- Creates a new dated tab in Google Sheets with all results
- Sends a styled HTML email digest of the top 10 matches
- Posts a Slack alert with the top 5

## Architecture

```
[RemoteOK]  [Greenhouse]  [Lever]  [LinkedIn*]
      ↓           ↓           ↓         ↓
         [Unified Scraper Layer]
                     ↓
         [Deduplication Engine]
                     ↓
         [AI Job Parser + Scorer]
                     ↓
         [Salary Estimator]
                     ↓
         [Priority Ranking Engine]
                     ↓
    [Google Sheets Sync + Daily Tab]
                     ↓
         [Slack + Email Alerts]
```

\* LinkedIn requires `LINKEDIN_ENABLED=true` and a local Chrome + chromedriver installation.

## Setup

1. Clone the repo
2. Copy `.env.example` → `.env` and fill in your credentials
3. Add your Google service account key as `credentials.json`
4. `pip install -r requirements.txt`
5. `python run_pipeline.py`

See `.env.example` for all required environment variables and where to get each one.

**Never commit `.env` or `credentials.json`** — they are in `.gitignore`.

## Automated hosting (free)

A GitHub Actions workflow (`.github/workflows/daily_pipeline.yml`) runs the
pipeline daily at 9 AM UTC. All secrets are stored in GitHub Repository Secrets
— nothing sensitive lives in the codebase.

## Tech stack

Python 3.11 · requests · BeautifulSoup · gspread · pandas · python-dotenv · OpenAI API (optional)
