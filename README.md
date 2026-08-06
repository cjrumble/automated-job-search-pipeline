# automated-job-search-pipeline

Daily Real-time Job Scraping Automation in Python

Fully autonomous, daily, production-grade job search pipeline that runs on
GitHub Actions every morning and delivers ranked results to Google Sheets,
email, and Slack — no manual work required. Results are also published as a
static dashboard that can be hosted on Netlify.

## What it does

Every time it runs:
- Loads the target companies from `companies.json` and routes each one to
  the right scraper (Greenhouse, Lever, or a best-effort generic scraper)
- Also scrapes RemoteOK for role-matched remote listings
- Deduplicates across all sources
- Scores each job 1–10 based on keyword fit and seniority
- Ranks by priority (#1 = apply first)
- Creates a new dated tab in Google Sheets with all results
- Sends a styled HTML email digest of the top 10 matches
- Posts a Slack alert with the top 5
- Writes a static `site/index.html` dashboard of every ranked job (for Netlify)

## Company list (`companies.json`)

Target companies now live in `companies.json` instead of being hardcoded —
this is the change requested for this update. Format:

```json
[
  { "name": "Postman", "url": "https://job-boards.greenhouse.io/postman/" },
  { "name": "Mainspring Energy", "url": "https://jobs.lever.co/mainspringenergy" },
  { "name": "Kaiser Permanente", "url": "https://www.kaiserpermanentejobs.org/" }
]
```

`company_loader.py` reads this file and routes each entry by inspecting its
URL:

| URL contains        | Scraper used        | Notes |
|----------------------|---------------------|-------|
| `greenhouse.io`      | `scrape_greenhouse.py` | Public JSON API — reliable |
| `lever.co`            | `scrape_lever.py`      | Public JSON API — reliable |
| anything else          | `scrape_generic.py`    | Best-effort static HTML scrape — see limitation below |

**Generic-site limitation:** Workday, Oracle Cloud/Taleo, and ADP boards
(most of the sample `companies.json`) render their listings with
client-side JavaScript. `scrape_generic.py` only fetches static HTML, so it
will correctly return an empty list for those — that's expected behavior,
not a bug. Only companies whose careers page ships job links in the raw
HTML (or that already use Greenhouse/Lever) will return real results without
further work. A production fix would add a headless-browser scraper (e.g.
Playwright) for the JS-rendered boards; that's a larger addition intentionally
left out of this change so the pipeline keeps its "no browser required" setup.

You can still target companies the old way, too — `GREENHOUSE_COMPANIES` and
`LEVER_COMPANIES` env vars are read and merged with `companies.json` (with
duplicates removed) for backward compatibility.

Malformed entries in `companies.json` (missing `name`/`url`, blank values,
non-object entries) are skipped individually with a warning instead of
crashing the run. If the file itself is missing or not valid JSON, the
pipeline logs that and falls back to the env-var lists only.

## Architecture

```
[companies.json] ──► [company_loader.py: classify + route]
                              │
        ┌─────────────┬───────┴────────┬───────────────┐
        ▼             ▼                ▼               ▼
   [Greenhouse]    [Lever]       [Generic HTML]     [RemoteOK]   [LinkedIn*]
        └─────────────┴────────────────┴───────────────┴─────────────┘
                                     ▼
                       [Unified Scraper Layer]
                                     ▼
                       [Deduplication Engine]
                                     ▼
                       [AI Job Parser + Scorer]
                                     ▼
                       [Salary Estimator]
                                     ▼
                       [Priority Ranking Engine]
                                     ▼
        ┌────────────────────────────┼───────────────────────────┐
        ▼                            ▼                            ▼
[Google Sheets Sync]         [Slack + Email Alerts]     [site/index.html
                                                          for Netlify]
```

\* LinkedIn requires `LINKEDIN_ENABLED=true` and a local Chrome + chromedriver installation.

## Setup

1. Clone the repo
2. Copy `.env.example` → `.env` and fill in your credentials
3. Add your Google service account key as `credentials.json`
4. Edit `companies.json` with the companies you want to track
5. `pip install -r requirements.txt`
6. `python run_pipeline.py`

See `.env.example` for all required environment variables and where to get each one.

**Never commit `.env` or `credentials.json`** — they are in `.gitignore`.

## Testing

Unit tests cover the new company-loading/routing logic, the generic
scraper, and the static report generator — all with mocked HTTP calls, so
`pytest` runs offline with no credentials required.

```
pip install pytest
pytest tests/ -v
```

Current suite: 29 tests across `tests/test_company_loader.py`,
`tests/test_scrape_generic.py`, `tests/test_generate_static_report.py`, and
`tests/test_run_pipeline_companies.py`.

## Automated hosting (free)

A GitHub Actions workflow (`.github/workflows/daily_pipeline.yml`) runs the
pipeline daily at 9 AM UTC. All secrets are stored in GitHub Repository Secrets
— nothing sensitive lives in the codebase. **This is still where the Python
code actually runs** — Netlify (below) only hosts the results page.

## Deploying the dashboard to Netlify

Netlify doesn't run Python (its Functions runtime is JS/TS/Go only), so it
can't execute `run_pipeline.py` itself. What it's good at is hosting the
static `site/index.html` dashboard the pipeline now generates. Two ways to
wire it up, easiest first:

**Option A — Netlify auto-publishes from GitHub (recommended)**
1. Commit the generated `site/` folder as part of the daily GitHub Actions
   run (add a `git add site && git commit -m "Update results" && git push`
   step after `python run_pipeline.py` in `daily_pipeline.yml`, using the
   default `GITHUB_TOKEN` for push permission).
2. In Netlify: **Add new site → Import an existing project → GitHub** and
   pick this repo.
3. Build settings are already in `netlify.toml` (`publish = "site"`,
   no real build step needed since the file is committed).
4. Every push to `main` (including the daily Action's commit) triggers a new
   Netlify deploy automatically — your dashboard is live at
   `https://<your-site-name>.netlify.app`.

**Option B — Trigger the GitHub Action from a Netlify Scheduled Function**
If you'd rather kick things off from Netlify's side: create a Netlify
[Scheduled Function](https://docs.netlify.com/functions/scheduled-functions/)
(Node.js) that calls the GitHub REST API's
`POST /repos/{owner}/{repo}/actions/workflows/daily_pipeline.yml/dispatches`
endpoint with a GitHub PAT stored as a Netlify environment variable. The
Action still does the actual scraping/scoring; Netlify just becomes the
trigger and, once it's done, the host for `site/`.

Either way, the pipeline's compute stays on GitHub Actions — Netlify is the
delivery/hosting layer, not the runtime.

## Tech stack

Python 3.11 · requests · BeautifulSoup · gspread · pandas · python-dotenv · OpenAI API (optional) · pytest
