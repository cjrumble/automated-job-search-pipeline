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
| `myworkdayjobs.com`, `oraclecloud.com`, `adp.com` | `scrape_js.py` | Headless Chromium via Playwright — see below |
| anything else          | `scrape_generic.py`    | Best-effort static HTML scrape |

**JS-rendered sites (Workday, Oracle Cloud, ADP):** these render listings
client-side, so plain `requests` can't see them. `scrape_js.py` uses
Playwright to load the page in headless Chromium, wait for the listings to
actually appear, then extract them — with a tailored CSS selector for each
known ATS and a generic link-text fallback for anything else. One shared
browser instance is used for the whole batch per run (launching a new
browser per company would make the pipeline dramatically slower). If
Playwright isn't installed, these companies are skipped with a warning
instead of crashing the run — see "Adding Playwright" below to enable them.

**Fully custom/unknown sites:** `scrape_generic.py` only fetches static
HTML — if a company's board isn't on the JS-rendered list above and also
isn't in the raw HTML, it will legitimately return no results.

You can still target companies the old way, too — `GREENHOUSE_COMPANIES` and
`LEVER_COMPANIES` env vars are read and merged with `companies.json` (with
duplicates removed) for backward compatibility.

Malformed entries in `companies.json` (missing `name`/`url`, blank values,
non-object entries) are skipped individually with a warning instead of
crashing the run. If the file itself is missing or not valid JSON, the
pipeline logs that and falls back to the env-var lists only.

**Placeholder entries (`"url": null`):** `companies.json` can contain
entries with a known company name but no URL yet — `{ "name": "Boeing",
"url": null }`. These are companies worth tracking once a real careers URL
is found and verified, but not yet researched. The loader excludes them
from scraping entirely (they never reach any scraper, so they can never
produce a 404) and prints a single summary line — `Skipped N companies
with no url yet` — rather than one warning per entry, since there can
legitimately be hundreds of these while the list is being filled in.
To activate a placeholder, just fill in its `"url"`.

## Adding Playwright (JS-rendered boards)

`scrape_js.py` and the `js_rendered` routing already ship in this repo — this
is what you need to run to actually enable it locally/in CI:

1. **Install the Python package** (already in `requirements.txt`):
   ```
   pip install -r requirements.txt
   ```
2. **Download the browser binary** — this is a separate step from `pip
   install`; Playwright ships the driver as a Python package but the actual
   Chromium binary is downloaded on demand:
   ```
   playwright install chromium
   ```
   (Use `playwright install --with-deps chromium` on a bare Linux box/CI
   runner — the `--with-deps` flag also installs the OS libraries Chromium
   needs, e.g. `libnss3`, fonts. `.github/workflows/daily_pipeline.yml`
   already has this step added.)
3. **Nothing else to configure** — `company_loader.classify_url()` already
   routes `myworkdayjobs.com` / `oraclecloud.com` / `adp.com` URLs to
   `scrape_js.py` automatically; `run_pipeline.py` calls
   `scrape_js_sites()` with that batch as its own pipeline stage.
4. **Add selectors for ATS platforms you use that aren't covered yet** — the
   three built in (`_ATS_SELECTORS` in `scrape_js.py`) were written from
   general knowledge of those platforms' DOM structure, not verified
   against a live board from this sandbox (its network is locked to package
   registries — see "Limitations" below). Before relying on results,
   open one real board from each ATS you use in a real browser, inspect the
   job-title element, and confirm/update the selector:
   ```python
   _ATS_SELECTORS = {
       "myworkdayjobs.com": "a[data-automation-id='jobTitle']",
       "oraclecloud.com":   "a[data-qa='searchResultsJobTitle'], a.job-title-link",
       "adp.com":           "a.job-tile, a[data-automation='job-title']",
   }
   ```
   If a selector doesn't match, `scrape_js.py` logs a selector-timeout
   warning naming the company rather than failing silently — that's your
   signal to go update the selector.
5. **Run it**:
   ```
   python run_pipeline.py
   ```
   Look for a `[Pipeline] JS-rendered → scraping N companies with
   Playwright...` line, followed by one `[scrape_js] Found K jobs at
   '<company>' (rendered).` line per company.

**Limitations to know about:**
- Headless Chromium is much heavier than `requests` — expect the JS-rendered
  stage to take noticeably longer than Greenhouse/Lever/generic, especially
  as the company list grows. `scrape_js_sites()` reuses one browser for the
  whole batch to keep this manageable, but each page still needs its own
  navigation + render wait.
- CI runners need the `--with-deps` install step (already added) or
  Chromium will fail to launch with missing shared-library errors.
- Some boards add bot detection (CAPTCHAs, headless-browser fingerprinting)
  that plain Playwright won't get past — that's outside the scope of this
  change.
- This repo's tests (`tests/test_scrape_js.py`) run against local rendered
  HTML via `page.set_content()`, not live company sites, so they verify the
  wait/extract logic but can't confirm any specific real board's selector
  still matches — re-verify selectors periodically as ATS vendors change
  their markup.


## Architecture

```
[companies.json] ──► [company_loader.py: classify + route]
                              │
        ┌─────────────┬───────┼────────────┬───────────────┐
        ▼             ▼       ▼            ▼               ▼
   [Greenhouse]    [Lever] [JS-rendered  [Generic HTML]  [RemoteOK]   [LinkedIn*]
                            Playwright]
        └─────────────┴───────┴────────────┴───────────────┴─────────────┘
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

Unit tests cover the new company-loading/routing logic, the generic and
JS-rendered scrapers, and the static report generator. Most run fully
offline with mocked HTTP calls; `tests/test_scrape_js.py` uses real headless
Chromium against locally-set HTML (no external network needed) so it
actually exercises Playwright's render/wait/extract path rather than mocking
it away.

```
pip install -r requirements.txt
playwright install chromium   # only needed for tests/test_scrape_js.py
pytest tests/ -v
```

Current suite: 39 tests across `tests/test_company_loader.py`,
`tests/test_scrape_generic.py`, `tests/test_scrape_js.py`,
`tests/test_generate_static_report.py`, and
`tests/test_run_pipeline_companies.py`.

## Automated hosting (free)

A GitHub Actions workflow (`.github/workflows/daily_pipeline.yml`) runs the
pipeline daily at 9 AM UTC. All secrets are stored in GitHub Repository Secrets
— nothing sensitive lives in the codebase. **This is still where the Python
code actually runs** — Netlify (below) only hosts the results page.

## Troubleshooting common CI failures

These are failure modes that have actually shown up in production runs, with root cause and fix:

| Symptom in the log | Root cause | Fix |
|---|---|---|
| `[sync_to_sheets] Could not open spreadsheet: Expecting value: line 1 column 1 (char 0)` | `GOOGLE_CREDENTIALS_JSON` secret is empty/unset, so the workflow's `printf` step writes a 0-byte `credentials.json` | Set `GOOGLE_CREDENTIALS_JSON` in **Settings → Secrets and variables → Actions** to the full contents of your service-account key file. `sync_to_sheets.py` now detects this and raises a specific "credentials file is empty" error instead of a cryptic JSON error. |
| `[send_email] Gmail auth failed.` | `EMAIL_PASSWORD` secret is a regular account password, not a Gmail **App Password** | Enable 2-Step Verification on the Gmail account, generate an App Password at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords), and put that 16-character value in the `EMAIL_PASSWORD` secret. |
| Hundreds of `[scrape_greenhouse]`/`[scrape_lever] Request failed ... 404` lines, run takes several minutes longer than it should | The legacy `GREENHOUSE_COMPANIES`/`LEVER_COMPANIES` secrets still hold a large historical list of company *display names* (e.g. `"3M Company"`, `"Bain & Company"`) that mostly aren't real Greenhouse/Lever board slugs | These 404s are handled gracefully and don't fail the run, but they're pure waste. Since `companies.json` is now the source of truth, either clear both secrets entirely, or trim them down to only confirmed-working slugs (check the log for which ones returned `Found N jobs`, even `Found 0 jobs` — that means the slug is valid). |
| `[scrape_js] playwright is not installed — skipping N JS-rendered companies.` | The workflow that actually ran doesn't have `playwright` in its `pip install` line and/or is missing the `playwright install --with-deps chromium` step | Confirm `.github/workflows/daily_pipeline.yml` on the branch GitHub Actions runs from includes both — they're already present in this repo's copy; if you still see this, the live workflow file on GitHub is out of date and needs the current version merged in. |
| `[scrape_generic] Request failed for '<company>': 404 Client Error` | The URL in `companies.json` for that company is stale (site restructured) | Find the company's current careers-search URL and update its entry in `companies.json`. (Amazon, McKesson, USAA, and PG&E were fixed for this reason.) |
| Garbled characters in job titles/descriptions, e.g. `donâ€™t` instead of `don't` | `scrape_remoteok.py` let `requests` guess the response encoding via `.json()`, which occasionally mis-detects UTF-8 as Latin-1 | Fixed — the scraper now decodes the response as UTF-8 explicitly before parsing JSON. |

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

Python 3.11 · requests · BeautifulSoup · Playwright · gspread · pandas · python-dotenv · OpenAI API (optional) · pytest
