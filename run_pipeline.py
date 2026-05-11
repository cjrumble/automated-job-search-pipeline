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
    GREENHOUSE_COMPANIES  (comma-separated, e.g. "stripe,airbnb,shopify")
    LEVER_COMPANIES       (comma-separated, e.g. "netflix,datadog")
    LINKEDIN_ENABLED      (set to "true" to enable — requires chromedriver)
    OPENAI_API_KEY        (optional — enables AI job parsing)
"""

import os
from dotenv import load_dotenv

load_dotenv()                            # must come before any other local imports

from advanced_fit_score import advanced_fit_score
from dedupe_jobs        import dedupe_jobs
from estimate_salary    import estimate_salary
from priority_ranking   import rank_jobs, get_top_jobs
from scrape_greenhouse  import scrape_greenhouse
from scrape_lever       import scrape_lever
from scrape_indeed      import scrape_indeed
from send_email         import send_email
from send_slack_alert   import send_slack_alert
from sync_to_sheets     import sync_jobs_to_sheet

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

    # Greenhouse  (public API, no auth needed, most reliable)
    greenhouse_companies = _parse_companies("GREENHOUSE_COMPANIES") or ["stripe"]
    for company in greenhouse_companies:
        print(f"\n[Pipeline] Greenhouse → {company}")
        all_jobs.extend(scrape_greenhouse(company))

    # Lever  (public API, no auth needed)
    lever_companies = _parse_companies("LEVER_COMPANIES")
    for company in lever_companies:
        print(f"[Pipeline] Lever → {company}")
        all_jobs.extend(scrape_lever(company))

    # RemoteOK  (public JSON API — replaced Indeed which blocks all scrapers)
    print("[Pipeline] RemoteOK → scraping...")
    all_jobs.extend(scrape_indeed(
        role=os.getenv("TARGET_ROLE",     "QA Automation Engineer"),
        location=os.getenv("TARGET_LOCATION", "Remote")
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

    print("\n" + "=" * 60)
    print(f"  Pipeline complete — {len(ranked_jobs)} jobs processed.")
    print("=" * 60)

    return ranked_jobs


if __name__ == "__main__":
    run_pipeline()
