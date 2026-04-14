# automated-job-search-pipeline
Daily Real-time Job Scraping Automation in Python

Fully autonomous, daily, production-grade automation job search pipeline.
Every time it runs:
✅ Multi-source ingestion
✅ Pulls real job listings (not career pages)
✅ Scores each job (5–10)
✅ Assigns Priority Rank (#1 = apply first)
✅ Creates a new tab like: 2026-04-15
✅ Inserts clean structured data
✅ Defaults all statuses → Not Applied
✅ Real-time alerts via Slack & email

ARCHITECTURE
[LinkedIn]   [Indeed]   [Greenhouse]   [Lever]
     ↓           ↓           ↓             ↓
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

Google Sheets API Client ID -        86184433151-ii9qboa180mgmtktirnpdkmh23kaucd2.apps.googleusercontent.com
Client Secret - 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
Service Email - sheets-service-account@automated-job-search-pipeline.iam.gserviceaccount.com
