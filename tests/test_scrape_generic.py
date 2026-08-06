import os
import sys
from unittest.mock import Mock, patch

import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrape_generic import scrape_generic


SAMPLE_HTML_WITH_JOBS = """
<html><body>
  <nav><a href="/about">About</a></nav>
  <ul>
    <li><a href="/careers/job/123">Senior QA Automation Engineer</a></li>
    <li><a href="/careers/job/456">Technical Project Manager</a></li>
  </ul>
  <footer><a href="/privacy">Privacy</a></footer>
</body></html>
"""

SAMPLE_HTML_NO_JOBS = """
<html><body>
  <nav><a href="/about">About</a></nav>
  <p>This board is rendered by JavaScript — no static links here.</p>
</body></html>
"""


def _mock_response(html, status_ok=True):
    resp = Mock()
    resp.text = html
    if status_ok:
        resp.raise_for_status = Mock()
    else:
        resp.raise_for_status = Mock(side_effect=requests.HTTPError("500 error"))
    return resp


@patch("scrape_generic.requests.get")
def test_scrape_generic_finds_job_like_links(mock_get):
    mock_get.return_value = _mock_response(SAMPLE_HTML_WITH_JOBS)

    jobs = scrape_generic("Acme Co", "https://careers.acme.example/")

    assert len(jobs) == 2
    titles = {j["title"] for j in jobs}
    assert "Senior QA Automation Engineer" in titles
    assert "Technical Project Manager" in titles
    for job in jobs:
        assert job["company"] == "Acme Co"
        assert job["link"].startswith("https://careers.acme.example/")


@patch("scrape_generic.requests.get")
def test_scrape_generic_returns_empty_for_js_rendered_board(mock_get):
    mock_get.return_value = _mock_response(SAMPLE_HTML_NO_JOBS)

    jobs = scrape_generic("Workday Co", "https://x.wd1.myworkdayjobs.com/x")

    assert jobs == []


@patch("scrape_generic.requests.get")
def test_scrape_generic_handles_request_exception_gracefully(mock_get):
    mock_get.side_effect = requests.ConnectionError("DNS failure")

    jobs = scrape_generic("Broken Co", "https://not-a-real-domain.example/")

    assert jobs == []


@patch("scrape_generic.requests.get")
def test_scrape_generic_handles_http_error_gracefully(mock_get):
    mock_get.return_value = _mock_response("<html></html>", status_ok=False)

    jobs = scrape_generic("Error Co", "https://careers.error.example/")

    assert jobs == []


@patch("scrape_generic.requests.get")
def test_scrape_generic_dedupes_repeated_links(mock_get):
    html = """
    <html><body>
      <a href="/careers/job/1">QA Engineer</a>
      <a href="/careers/job/1">QA Engineer (duplicate link)</a>
    </body></html>
    """
    mock_get.return_value = _mock_response(html)

    jobs = scrape_generic("Dup Co", "https://careers.dup.example/")

    assert len(jobs) == 1


@patch("scrape_generic.requests.get")
def test_scrape_generic_respects_max_jobs(mock_get):
    links = "".join(f'<a href="/careers/job/{i}">Job Opening {i}</a>' for i in range(30))
    mock_get.return_value = _mock_response(f"<html><body>{links}</body></html>")

    jobs = scrape_generic("Big Co", "https://careers.big.example/", max_jobs=5)

    assert len(jobs) == 5
