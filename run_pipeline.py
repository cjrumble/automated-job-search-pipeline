"""
run_pipeline.py  —  FIX 9: Complete rewrite

Original only called scrape_greenhouse("stripe") and returned a list.
It never called send_email, send_slack_alert, or any Sheets sync.
All scrapers and outputs are now wired together and driven by .env config.

Usage:
    python run_pipeline.py

Required .env vars:
    TARGET_ROLE, TARGET_LOCATION
    EMAIL_SENDER, EMAIL_RECIPIENT, EMAIL_PASSWORD
    SLACK_WEBHOOK
    GOOGLE_SHEET_NAME, GOOGLE_CREDENTIALS_PATH
    GREENHOUSE_COMPANIES  (optional, comma-separated, e.g. "stripe,airbnb")
    LEVER_COMPANIES       (optional, comma-separated, e.g. "netflix,datadog")
    COMPANIES_JSON_PATH   (optional — defaults to "companies.json"; a JSON
                            list of {"name","url"} company career pages,
                            auto-routed to the Greenhouse/Lever/generic
                            scraper — see company_loader.py)
    LINKEDIN_ENABLED      (set to "true" to enable — requires chromedriver)
    OPENAI_API_KEY        (optional — enables AI job parsing)
"""

import os
from dotenv import load_dotenv

load_dotenv()                            # must come before any other local imports

from advanced_fit_score import advanced_fit_score
from company_loader     import load_companies, build_source_lists, CompanyListError
from dedupe_jobs        import dedupe_jobs
from estimate_salary    import estimate_salary
from generate_static_report import generate_static_report
from priority_ranking   import rank_jobs, get_top_jobs
from scrape_generic     import scrape_generic
from scrape_js          import scrape_js_sites
from scrape_greenhouse  import scrape_greenhouse
from scrape_lever       import scrape_lever
from scrape_remoteok    import scrape_remoteok
from send_email         import send_email
from send_slack_alert   import send_slack_alert
from sync_to_sheets     import sync_jobs_to_sheet

COMPANIES_JSON_PATH = os.getenv("COMPANIES_JSON_PATH", "companies.json")

# AI parsing is optional — only runs when OPENAI_API_KEY is set
AI_PARSING_ENABLED = bool(os.getenv("OPENAI_API_KEY"))
if AI_PARSING_ENABLED:
    try:
        from job_smart_matching import parse_job
    except Exception:
        AI_PARSING_ENABLED = False


def _parse_companies(env_key):
    """Reads a comma-separated env var and returns a clean list of strings."""
    raw = os.getenv(env_key, "")
    return [c.strip() for c in raw.split(",") if c.strip()]


def run_pipeline():
    print("=" * 60)
    print("  Job Search Pipeline — Starting")
    print("=" * 60)

    all_jobs = []

    # ── Stage 1: Scrape all sources ───────────────────────────

    # companies.json  (preferred source — name+url pairs, auto-routed to
    # the Greenhouse/Lever/JS-rendered/generic scraper based on the URL's ATS)
    greenhouse_slugs, lever_slugs, js_rendered_companies, generic_companies = [], [], [], []
    try:
        companies = load_companies(COMPANIES_JSON_PATH)
        sources = build_source_lists(companies)
        greenhouse_slugs      = sources["greenhouse_slugs"]
        lever_slugs           = sources["lever_slugs"]
        js_rendered_companies = sources["js_rendered"]
        generic_companies     = sources["generic"]
        print(
            f"[Pipeline] Loaded {len(companies)} companies from "
            f"'{COMPANIES_JSON_PATH}' → {len(greenhouse_slugs)} Greenhouse, "
            f"{len(lever_slugs)} Lever, {len(js_rendered_companies)} JS-rendered, "
            f"{len(generic_companies)} generic."
        )
    except CompanyListError as e:
        print(f"[Pipeline] {e} Falling back to GREENHOUSE_COMPANIES/LEVER_COMPANIES env vars only.")

    # Greenhouse  (public API, no auth needed, most reliable)
    greenhouse_companies = _parse_companies("GREENHOUSE_COMPANIES") + greenhouse_slugs
    for company in dict.fromkeys(greenhouse_companies):  # de-dupe, preserve order
        print(f"\n[Pipeline] Greenhouse → {company}")
        all_jobs.extend(scrape_greenhouse(company))

    # Lever  (public API, no auth needed)
    lever_companies = _parse_companies("LEVER_COMPANIES") + lever_slugs
    for company in dict.fromkeys(lever_companies):
        print(f"[Pipeline] Lever → {company}")
        all_jobs.extend(scrape_lever(company))

    # Generic  (companies.json entries that aren't Greenhouse/Lever — best
    # effort static-HTML scrape; JS-rendered boards will return no results)
    for company in generic_companies:
        print(f"[Pipeline] Generic → {company['name']}")
        all_jobs.extend(scrape_generic(company["name"], company["url"]))

    # JS-rendered  (Workday / Oracle Cloud / ADP — one shared headless
    # browser instance handles the whole batch; see scrape_js.py)
    if js_rendered_companies:
        print(f"[Pipeline] JS-rendered → scraping {len(js_rendered_companies)} companies with Playwright...")
        all_jobs.extend(scrape_js_sites(js_rendered_companies))

    # RemoteOK  (public JSON API — replaced Indeed which blocks all scrapers)
    print("[Pipeline] RemoteOK → scraping...")
    all_jobs.extend(scrape_remoteok(
        role=os.getenv("TARGET_ROLE"),
        location=os.getenv("TARGET_LOCATION")
    ))

    # LinkedIn  (opt-in — requires chromedriver, set LINKEDIN_ENABLED=true)
    if os.getenv("LINKEDIN_ENABLED", "false").lower() == "true":
        try:
            from scrape_linkedin import scrape_linkedin
            print("[Pipeline] LinkedIn → scraping...")
            all_jobs.extend(scrape_linkedin(
                role=os.getenv("TARGET_ROLE"),
                location=os.getenv("TARGET_LOCATION")
            ))
        except Exception as e:
            print(f"[Pipeline] LinkedIn scraper skipped: {e}")

    print(f"\n[Pipeline] Raw jobs collected: {len(all_jobs)}")

    # ── Stage 2: Deduplicate ──────────────────────────────────
    all_jobs = dedupe_jobs(all_jobs)
    print(f"[Pipeline] After deduplication: {len(all_jobs)} jobs")

    if not all_jobs:
        print("[Pipeline] No jobs found. Check your scrapers and try again.")
        return []

    # ── Stage 3: Score each job ───────────────────────────────
    for job in all_jobs:
        job.setdefault("description", "")     # guard against missing key
        job["Fit Score"] = advanced_fit_score(job)
        job["Salary"]    = estimate_salary(job["title"])

        # Optional AI structured parsing
        if AI_PARSING_ENABLED and job["description"]:
            parsed = parse_job(job["description"])
            job["AI Skills"]    = ", ".join(parsed.get("skills", []))
            job["AI Seniority"] = parsed.get("seniority", "")

    # ── Stage 4: Rank by Fit Score ────────────────────────────
    ranked_jobs = rank_jobs(all_jobs)
    top_jobs    = get_top_jobs(ranked_jobs, n=10)

    print("\n[Pipeline] Top 10 by Fit Score:")
    for job in top_jobs:
        print(
            f"  #{job['Priority']:>2}  {job['Fit Score']}/10  "
            f"{job['title']} @ {job['company']}"
        )

    # ── Stage 5: Google Sheets sync ───────────────────────────
    print("\n[Pipeline] Syncing to Google Sheets...")
    sync_jobs_to_sheet(ranked_jobs)

    # ── Stage 6: Email digest ─────────────────────────────────
    print("[Pipeline] Sending email digest...")
    send_email(ranked_jobs)

    # ── Stage 7: Slack alert ──────────────────────────────────
    print("[Pipeline] Sending Slack alert...")
    send_slack_alert(top_jobs)

    # ── Stage 8: Static site (for Netlify) ────────────────────
    print("[Pipeline] Writing static report to site/ ...")
    generate_static_report(ranked_jobs)

    print("\n" + "=" * 60)
    print(f"  Pipeline complete — {len(ranked_jobs)} jobs processed.")
    print("=" * 60)

    return ranked_jobs


if __name__ == "__main__":
    run_pipeline()
