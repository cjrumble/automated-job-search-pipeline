import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from generate_static_report import generate_static_report

SAMPLE_JOBS = [
    {"Priority": 1, "Fit Score": 9, "title": "Senior SDET", "company": "postman",
     "location": "Remote", "link": "https://example.com/1", "Salary": "$120k-$150k"},
    {"Priority": 2, "Fit Score": 7, "title": "QA <Lead>", "company": "acme & co",
     "location": "SF", "link": "https://example.com/2", "Salary": "$110k"},
]


def test_generates_index_html_and_jobs_json(tmp_path):
    out_dir = tmp_path / "site"

    index_path = generate_static_report(SAMPLE_JOBS, out_dir=str(out_dir))

    assert os.path.exists(index_path)
    assert os.path.exists(out_dir / "jobs.json")

    with open(out_dir / "jobs.json") as f:
        assert json.load(f) == SAMPLE_JOBS


def test_index_html_contains_job_titles_and_count(tmp_path):
    out_dir = tmp_path / "site"
    generate_static_report(SAMPLE_JOBS, out_dir=str(out_dir))

    content = (out_dir / "index.html").read_text()

    assert "Senior SDET" in content
    assert "2 jobs" in content


def test_index_html_escapes_untrusted_job_fields(tmp_path):
    """A job title/company containing HTML-special chars must not break the page."""
    out_dir = tmp_path / "site"
    generate_static_report(SAMPLE_JOBS, out_dir=str(out_dir))

    content = (out_dir / "index.html").read_text()

    assert "<Lead>" not in content       # raw tag must be escaped
    assert "&lt;Lead&gt;" in content
    assert "acme &amp; co" in content


def test_handles_empty_job_list(tmp_path):
    out_dir = tmp_path / "site"
    generate_static_report([], out_dir=str(out_dir))

    content = (out_dir / "index.html").read_text()
    assert "0 jobs" in content
