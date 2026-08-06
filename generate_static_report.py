"""
generate_static_report.py — writes the latest ranked job results out as a
static HTML page (site/index.html) that Netlify can host.

This does NOT run the scrapers itself — call it from run_pipeline.py (or
after it) with the ranked_jobs list. Netlify hosts static sites; it has no
Python runtime, so the pipeline must keep running on GitHub Actions (see
README "Deploying the dashboard to Netlify") and just publish its output
here for Netlify to serve.
"""

import datetime
import html
import json
import os

SITE_DIR = "site"


def generate_static_report(ranked_jobs, out_dir=SITE_DIR):
    """
    Writes site/index.html and site/jobs.json from a list of ranked job dicts.

    Args:
        ranked_jobs: list of job dicts (output of priority_ranking.rank_jobs)
        out_dir: directory to write the static site into (default "site")
    Returns:
        path to the generated index.html
    """
    os.makedirs(out_dir, exist_ok=True)

    generated_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    with open(os.path.join(out_dir, "jobs.json"), "w", encoding="utf-8") as f:
        json.dump(ranked_jobs, f, indent=2, default=str)

    rows = "\n".join(_job_row(job) for job in ranked_jobs)

    index_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Job Search Pipeline — Results</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }}
  h1 {{ margin-bottom: 0.25rem; }}
  .meta {{ color: #666; margin-bottom: 1.5rem; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid #e0e0e0; }}
  th {{ background: #fafafa; }}
  a {{ color: #0b5fff; text-decoration: none; }}
  a:hover {{ text-decoration: underline; }}
</style>
</head>
<body>
  <h1>Job Search Pipeline — Results</h1>
  <p class="meta">Last updated {generated_at} · {len(ranked_jobs)} jobs</p>
  <table>
    <thead>
      <tr><th>#</th><th>Fit</th><th>Title</th><th>Company</th><th>Location</th><th>Salary</th></tr>
    </thead>
    <tbody>
      {rows}
    </tbody>
  </table>
</body>
</html>
"""

    index_path = os.path.join(out_dir, "index.html")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(index_html)

    print(f"[generate_static_report] Wrote {index_path} ({len(ranked_jobs)} jobs).")
    return index_path


def _job_row(job):
    title = html.escape(str(job.get("title", "")))
    company = html.escape(str(job.get("company", "")))
    location = html.escape(str(job.get("location", "")))
    link = html.escape(str(job.get("link", "#")))
    salary = html.escape(str(job.get("Salary", "")))
    fit = html.escape(str(job.get("Fit Score", "")))
    priority = html.escape(str(job.get("Priority", "")))
    return (
        f"<tr><td>{priority}</td><td>{fit}/10</td>"
        f'<td><a href="{link}" target="_blank" rel="noopener">{title}</a></td>'
        f"<td>{company}</td><td>{location}</td><td>{salary}</td></tr>"
    )
