import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

playwright_sync_api = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import sync_playwright  # noqa: E402

from scrape_js import (  # noqa: E402
    _extract_generic_fallback,
    _extract_with_selector,
    _selector_for,
    scrape_js_site,
    scrape_js_sites,
)

WORKDAY_STYLE_HTML = """
<html><body>
<div id="root">Loading...</div>
<script>
setTimeout(function () {
  document.getElementById('root').innerHTML =
    '<ul>' +
    '<li><a href="/job/1" data-automation-id="jobTitle">Senior QA Automation Engineer</a></li>' +
    '<li><a href="/job/2" data-automation-id="jobTitle">Technical Project Manager</a></li>' +
    '</ul>';
}, 200);
</script>
</body></html>
"""

GENERIC_JS_HTML = """
<html><body>
<div id="root"></div>
<script>
setTimeout(function () {
  document.getElementById('root').innerHTML =
    '<a href="/careers/job/9">Remote QA Opening</a>';
}, 200);
</script>
</body></html>
"""

NO_JOBS_HTML = "<html><body><p>Nothing rendered here.</p></body></html>"


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        yield b
        b.close()


@pytest.fixture()
def page(browser):
    pg = browser.new_page()
    yield pg
    pg.close()


# ── selector routing ────────────────────────────────────────────

def test_selector_for_known_ats_hosts():
    assert _selector_for("https://aptos.wd108.myworkdayjobs.com/Aptos") is not None
    assert _selector_for("https://ecge.fa.us2.oraclecloud.com/hcmUI/x") is not None
    assert _selector_for("https://myjobs.adp.com/tpxcareers/cx/") is not None


def test_selector_for_unknown_host_is_none():
    assert _selector_for("https://www.kaiserpermanentejobs.org/") is None


# ── real headless-render extraction ─────────────────────────────

def test_extract_with_selector_reads_js_rendered_content(page):
    page.set_content(WORKDAY_STYLE_HTML)
    page.wait_for_selector("[data-automation-id='jobTitle']", timeout=3000)

    jobs = _extract_with_selector(page, "[data-automation-id='jobTitle']", "https://example.com/board")

    titles = {j["title"] for j in jobs}
    assert titles == {"Senior QA Automation Engineer", "Technical Project Manager"}
    assert all(j["link"].startswith("https://example.com/") for j in jobs)


def test_extract_generic_fallback_reads_js_rendered_content(page):
    page.set_content(GENERIC_JS_HTML)
    page.wait_for_timeout(400)

    jobs = _extract_generic_fallback(page, "https://example.com/board")

    assert len(jobs) == 1
    assert jobs[0]["title"] == "Remote QA Opening"


def test_scrape_js_site_end_to_end_via_local_content(page, monkeypatch):
    """
    scrape_js_site() normally calls page.goto(url); we monkeypatch goto to
    load fixed local content instead, so the test exercises the real
    wait/extract logic without needing an external, JS-rendering test server.
    """
    monkeypatch.setattr(page, "goto", lambda *a, **kw: page.set_content(WORKDAY_STYLE_HTML))

    jobs = scrape_js_site(page, "Aptos", "https://aptos.wd108.myworkdayjobs.com/Aptos")

    assert len(jobs) == 2
    assert all(j["company"] == "Aptos" for j in jobs)
    assert {j["title"] for j in jobs} == {"Senior QA Automation Engineer", "Technical Project Manager"}


def test_scrape_js_site_returns_empty_when_nothing_renders(page, monkeypatch):
    monkeypatch.setattr(page, "goto", lambda *a, **kw: page.set_content(NO_JOBS_HTML))

    jobs = scrape_js_site(page, "Empty Co", "https://www.kaiserpermanentejobs.org/")

    assert jobs == []


def test_scrape_js_sites_returns_empty_list_for_empty_input():
    assert scrape_js_sites([]) == []


def test_scrape_js_sites_gracefully_skips_when_playwright_missing(monkeypatch):
    import scrape_js
    monkeypatch.setattr(scrape_js, "PLAYWRIGHT_AVAILABLE", False)

    jobs = scrape_js.scrape_js_sites([{"name": "Aptos", "url": "https://x.myworkdayjobs.com/x"}])

    assert jobs == []
