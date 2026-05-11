# Architecture & File Reference

This document explains every file in the repository — what it does, when it runs
during the pipeline, what it reads in, and what it produces.

---

## How to run

```bash
# Local
python run_pipeline.py

# Automated (GitHub Actions — runs daily at 9 AM UTC automatically)
# Or trigger manually: Actions tab → Daily Job Search Pipeline → Run workflow
```

---

## Execution flow

When `run_pipeline.py` is invoked, it executes seven sequential stages:

```
START
  │
  ▼
Stage 1 ── Scrape ──────────────────────────────────────────────────
  │   scrape_greenhouse.py   → Greenhouse public API (per company slug)
  │   scrape_lever.py        → Lever public API (per company slug)
  │   scrape_remoteok.py     → RemoteOK public API (keyword-based)
  │   scrape_linkedin.py     → LinkedIn (opt-in, disabled by default)
  │
  ▼
Stage 2 ── Deduplicate ─────────────────────────────────────────────
  │   dedupe_jobs.py         → Remove duplicate (company, title) pairs
  │
  ▼
Stage 3 ── Score & Enrich ──────────────────────────────────────────
  │   advanced_fit_score.py  → Keyword scoring (1–10)
  │   estimate_salary.py     → Title-based salary range lookup
  │   job_smart_matching.py  → OpenAI parsing (optional, if OPENAI_API_KEY set)
  │
  ▼
Stage 4 ── Rank ────────────────────────────────────────────────────
  │   priority_ranking.py    → Sort by Fit Score, assign Priority #
  │
  ▼
Stage 5 ── Google Sheets ───────────────────────────────────────────
  │   sync_to_sheets.py      → Write ranked jobs to a new dated tab
  │   credentials.json       → Service account key (not in repo — local only)
  │
  ▼
Stage 6 ── Email ───────────────────────────────────────────────────
  │   send_email.py          → Styled HTML digest of top 10 jobs via Gmail
  │
  ▼
Stage 7 ── Slack ───────────────────────────────────────────────────
      send_slack_alert.py    → Slack message with top 5 jobs via webhook

END
```

---

## File reference

### Entry point

#### `run_pipeline.py`
**When accessed:** First — it is the program. Run directly with `python run_pipeline.py`.

**What it does:**
Orchestrates all seven pipeline stages in sequence. Reads environment variables
(from `.env` locally, from GitHub Secrets in CI) to configure which companies
to scrape, where to send results, and whether optional features are enabled.

**Reads:**
- `.env` (via `python-dotenv`) for all configuration
- All scraper, scoring, and output modules (via imports)

**Produces:**
- Console output showing progress through each stage
- Returns a list of ranked job dicts (used by tests or callers)

**Key env vars it reads:**
`TARGET_ROLE`, `TARGET_LOCATION`, `GREENHOUSE_COMPANIES`, `LEVER_COMPANIES`,
`LINKEDIN_ENABLED`, `GOOGLE_SHEET_NAME`, `GOOGLE_CREDENTIALS_PATH`,
`EMAIL_SENDER`, `EMAIL_RECIPIENT`, `EMAIL_PASSWORD`, `SLACK_WEBHOOK`,
`OPENAI_API_KEY`

---

### Stage 1 — Scrapers

#### `scrape_greenhouse.py`
**When accessed:** Stage 1, first — called once per company in `GREENHOUSE_COMPANIES`.

**What it does:**
Calls the Greenhouse public job board REST API (`boards-api.greenhouse.io`).
No authentication required. Returns all open positions for a given company slug.

**Input:** company slug string (e.g. `"stripe"`, `"airbnb"`)

**Output:** list of job dicts:
```python
{
  "company":     "stripe",
  "title":       "Senior QA Engineer",
  "link":        "https://stripe.com/jobs/search?gh_jid=...",
  "location":    "San Francisco, CA",
  "description": ""   # Greenhouse basic API omits full description
}
```

**Error handling:** Returns `[]` on timeout, HTTP error, or malformed response.
The pipeline continues with whatever other scrapers return.

---

#### `scrape_lever.py`
**When accessed:** Stage 1, second — called once per company in `LEVER_COMPANIES`.

**What it does:**
Calls Lever's public postings API (`api.lever.co/v0/postings/{company}`).
No authentication required. Not all companies use Lever — the function returns
`[]` gracefully if the company slug doesn't match an active Lever board.

**Validated working slugs:** `jumpcloud`, `plaid`

**Input:** company slug string (e.g. `"jumpcloud"`)

**Output:** list of job dicts with the same shape as Greenhouse output.

**Error handling:** Returns `[]` on timeout, 404 (company not on Lever), or
malformed response. Each company is tried independently.

---

#### `scrape_remoteok.py`
**When accessed:** Stage 1, third — called once per run.

**What it does:**
Queries [RemoteOK's public JSON API](https://remoteok.com/api) using keyword
tags derived from `TARGET_ROLE`. RemoteOK replaced the original Indeed scraper
because Indeed blocks all automated access with a 403 Forbidden response.

RemoteOK's API is intentionally public and free. The role string is mapped to
tags (e.g. `"QA Automation Engineer"` → `["qa", "testing", "engineer"]`) and
each tag is queried separately. Results are deduplicated by URL before returning.

**Input:** `role` string (defaults to `TARGET_ROLE` env var), `max_jobs` (default 20)

**Output:** list of job dicts. All jobs have `"location": "Remote"`.

**Error handling:** Each tag query is wrapped in try/except. If one tag fails,
the others still run. Returns whatever was successfully collected.

---

#### `scrape_linkedin.py`
**When accessed:** Stage 1, fourth — **only if `LINKEDIN_ENABLED=true`** in env.

**What it does:**
Uses the `linkedin_jobs_scraper` library to search LinkedIn Jobs. Disabled by
default because it requires:
- `pip install linkedin_jobs_scraper`
- Chrome browser + matching chromedriver in PATH
- Active Chrome profile (handles LinkedIn's bot detection)

**Input:** `role`, `location` strings from env vars.

**Output:** list of job dicts (same shape as other scrapers).

**Error handling:** If the package is not installed or Chrome is unavailable,
prints a clear message and returns `[]`. The pipeline continues unaffected.

---

### Stage 2 — Deduplication

#### `dedupe_jobs.py`
**When accessed:** Stage 2 — immediately after all scrapers complete.

**What it does:**
Removes duplicate entries from the combined scraper output. Two jobs are
considered duplicates if they share the same `(company, title)` pair.
The first occurrence is kept; subsequent ones are discarded.

**Input:** combined list of all job dicts from all scrapers

**Output:** deduplicated list (typically ~5–10% reduction)

---

### Stage 3 — Scoring & Enrichment

#### `advanced_fit_score.py`
**When accessed:** Stage 3 — called once per job after deduplication.

**What it does:**
Scores each job 1–10 based on keyword relevance. Starting from a baseline of 5:
- +1 for each of: `selenium`, `cypress`, `api`, `python`, `automation` (in title or description)
- +1 for `senior` in the text
- +1 for `remote` in the location

Maximum score: 10. The score is written back to the job dict as `"Fit Score"`.

**Input:** single job dict (must have `title`, `description`, `location` keys)

**Output:** integer score 5–10 (stored as `job["Fit Score"]`)

---

#### `estimate_salary.py`
**When accessed:** Stage 3 — called once per job, alongside fit scoring.

**What it does:**
Returns a salary range string based on keywords in the job title.
Ranges are heuristic estimates, not live market data.

| Title contains | Estimated range |
|---|---|
| `senior` | $140K–$190K |
| `sdet` | $130K–$180K |
| `qa` | $110K–$150K |
| (anything else) | $100K–$140K |

**Input:** job title string

**Output:** salary range string (stored as `job["Salary"]`)

---

#### `job_smart_matching.py`
**When accessed:** Stage 3 — **only if `OPENAI_API_KEY` is set in env.**

**What it does:**
Sends each job description to OpenAI's `gpt-4o-mini` model and asks it to
extract structured data: required skills, seniority level, tools used, and
top responsibilities. Results are added to the job dict as `"AI Skills"` and
`"AI Seniority"` fields.

Falls back to returning `{}` on any failure (missing key, network error,
parse error) so the pipeline is never blocked by an OpenAI outage.

**Input:** job description text (truncated to 3,000 characters)

**Output:** dict with keys `skills`, `seniority`, `tools`, `responsibilities`
(stored as `job["AI Skills"]` and `job["AI Seniority"]`)

**Cost note:** Each job description = one API call to `gpt-4o-mini`. With 500
jobs and ~100 tokens per call, expect roughly $0.01–$0.05 per pipeline run.

---

### Stage 4 — Ranking

#### `priority_ranking.py`
**When accessed:** Stage 4 — once after all scoring is complete.

Exports two functions:

**`rank_jobs(jobs)`**
Sorts the full job list by `Fit Score` (highest first) using pandas, then
assigns sequential `Priority` numbers starting at 1. Returns the sorted list
as a list of dicts.

**`get_top_jobs(ranked_jobs, n=10)`**
Slices the first `n` entries from an already-ranked list. Used in
`run_pipeline.py` to get the top 10 for the console summary and the top 5
for the Slack alert.

**Input:** list of job dicts with `"Fit Score"` key

**Output:** same list, sorted, with `"Priority"` key added (1 = best fit)

---

### Stage 5 — Google Sheets

#### `sync_to_sheets.py`
**When accessed:** Stage 5 — once after ranking.

**What it does:**
Authenticates with Google's Sheets API using a service account key, opens the
target spreadsheet by name, and writes all ranked jobs to a new tab named
after today's date (e.g. `2026-05-10`). If a tab for today already exists it
is deleted and recreated, making the pipeline safely re-runnable.

The header row is formatted with bold white text on a blue background. Each
data row gets an `"Application Status"` of `"Not Applied"` by default, matching
the README specification.

**Columns written:** Priority · Job Title · Company · Location · Fit Score ·
Est. Salary · Link · Application Status · Date Found

**Input:** full ranked job list + `GOOGLE_SHEET_NAME` env var

**Requires:**
- `credentials.json` — Google service account JSON key (excluded from git)
- The target spreadsheet must be shared with the service account email

**Error handling:** Returns `False` and prints a clear message if credentials
are missing, the sheet doesn't exist, or the API call fails. The pipeline
continues to email and Slack regardless.

---

#### `credentials.json`
**When accessed:** Stage 5 — read by `sync_to_sheets.py` at authentication time.

**What it is:**
A Google Cloud service account JSON key file. Contains a private RSA key used
to sign requests to the Google Sheets API. **This file must never be committed
to git** (it is listed in `.gitignore`).

**Local use:** Place it in the project root directory.

**GitHub Actions use:** Paste the full JSON contents as the `GOOGLE_CREDENTIALS_JSON`
repository secret. The workflow writes it to disk at runtime before the pipeline starts.

---

### Stage 6 — Email

#### `send_email.py`
**When accessed:** Stage 6 — once after Google Sheets sync.

**What it does:**
Sends a styled HTML email digest to the configured recipient using Gmail's SMTP
server on port 587 with STARTTLS. The email shows the top 10 ranked jobs in a
formatted table with clickable job title links.

All external data (job titles, company names, URLs) is HTML-escaped before
insertion into the template. Job links are validated to allow only `http://`
and `https://` URLs.

**Input:** full ranked job list; reads `EMAIL_SENDER`, `EMAIL_RECIPIENT`,
`EMAIL_PASSWORD` from environment

**Requires:** A Gmail App Password (not your login password). Generate one at
[myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).

**Error handling:** Returns `False` with a descriptive message if any env var
is missing or if Gmail authentication fails. The pipeline continues to Slack.

---

### Stage 7 — Slack

#### `send_slack_alert.py`
**When accessed:** Stage 7 — last step in the pipeline.

**What it does:**
Posts a Slack message to a channel via an Incoming Webhook URL. The message
lists the top 5 ranked jobs with title, company, location, fit score, salary,
and a direct link.

**Input:** top 10 job list (only the first 5 are posted to Slack);
reads `SLACK_WEBHOOK` from environment

**Requires:** A Slack Incoming Webhook URL. Create one at
[api.slack.com/apps](https://api.slack.com/apps) → Incoming Webhooks.

**Error handling:** Returns `False` with a descriptive message if the webhook
is not set or the POST request fails.

---

### Configuration files

#### `.env` (local only — not in repo)
**When accessed:** First, at startup — `run_pipeline.py` calls `load_dotenv()`
before any other imports.

**What it is:** A plain-text file of `KEY=value` pairs that sets all runtime
configuration. Copy `.env.example` to `.env` and fill in your real values.
**Never commit this file** (it is in `.gitignore`).

---

#### `.env.example`
**When accessed:** Never at runtime — it is documentation only.

**What it is:** A template showing every supported environment variable with
example values and instructions for obtaining credentials. Copy it to `.env`
to get started.

---

#### `.gitignore`
**When accessed:** By git only — never at runtime.

Prevents `.env`, `credentials.json`, `__pycache__/`, `.DS_Store`, and
`job_applications.csv` from being committed to the repository.

---

#### `requirements.txt`
**When accessed:** During setup only — `pip install -r requirements.txt`.

Lists all Python package dependencies. Core packages are required; `openai` is
optional (AI parsing), `linkedin_jobs_scraper` and `selenium` are optional
(LinkedIn scraping).

---

### CI/CD

#### `.github/workflows/daily_pipeline.yml`
**When accessed:** By GitHub Actions — on the cron schedule (`0 9 * * *`,
daily 9 AM UTC) or when manually triggered from the Actions tab.

**What it does:**
1. Checks out the repository
2. Sets up Python 3.11
3. Installs core dependencies
4. Writes `credentials.json` from the `GOOGLE_CREDENTIALS_JSON` repository secret
5. Runs `python run_pipeline.py` with all secrets injected as environment variables

All secrets are stored in **GitHub Repository Secrets** (Settings → Secrets and
variables → Actions). Nothing sensitive is in the codebase.

---

### Legacy / reference files

#### `daily_job_automation.py`
**When accessed:** Never by the main pipeline. Standalone script only.

The original prototype entry point. Uses Selenium to scrape Indeed directly
(now blocked by Indeed's 403 response). Superseded entirely by `run_pipeline.py`.
Kept as a reference for the project's development history. Can be run directly
(`python daily_job_automation.py`) if Chrome + chromedriver are installed, but
results will be empty because Indeed blocks the requests.

---

## Data flow summary

```
env vars / .env
      │
      ▼
run_pipeline.py
      │
      ├─► scrape_greenhouse.py ──┐
      ├─► scrape_lever.py ───────┤
      ├─► scrape_remoteok.py ────┤─► [raw job list]
      └─► scrape_linkedin.py ────┘         │
                                           ▼
                                    dedupe_jobs.py
                                           │
                                           ▼
                             advanced_fit_score.py ─┐
                             estimate_salary.py ─────┤─► [scored job list]
                             job_smart_matching.py ──┘         │
                                                               ▼
                                                     priority_ranking.py
                                                               │
                                               ┌───────────────┼───────────────┐
                                               ▼               ▼               ▼
                                      sync_to_sheets.py  send_email.py  send_slack_alert.py
                                               │               │               │
                                               ▼               ▼               ▼
                                       Google Sheet       Gmail inbox     Slack channel
```
