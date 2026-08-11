import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from company_loader import (
    CompanyListError,
    build_source_lists,
    classify_url,
    extract_slug,
    load_companies,
)


# ── load_companies ──────────────────────────────────────────────

def test_load_companies_valid_file(tmp_path):
    data = [
        {"name": "Postman", "url": "https://job-boards.greenhouse.io/postman/"},
        {"name": "Mainspring Energy", "url": "https://jobs.lever.co/mainspringenergy"},
    ]
    path = tmp_path / "companies.json"
    path.write_text(json.dumps(data))

    companies = load_companies(str(path))

    assert companies == data


def test_load_companies_missing_file_raises():
    with pytest.raises(CompanyListError):
        load_companies("does_not_exist.json")


def test_load_companies_invalid_json_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not valid json")

    with pytest.raises(CompanyListError):
        load_companies(str(path))


def test_load_companies_top_level_not_a_list_raises(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"name": "Postman", "url": "https://example.com"}))

    with pytest.raises(CompanyListError):
        load_companies(str(path))


def test_load_companies_skips_entries_missing_required_keys(tmp_path, capsys):
    data = [
        {"name": "Postman", "url": "https://job-boards.greenhouse.io/postman/"},
        {"name": "No URL Co"},                      # missing url -> placeholder
        {"url": "https://example.com"},              # missing name -> structural warning
        {"name": "", "url": "https://example.com"},  # blank name -> structural warning
        "not even an object",                         # wrong type -> structural warning
    ]
    path = tmp_path / "companies.json"
    path.write_text(json.dumps(data))

    companies = load_companies(str(path))

    assert len(companies) == 1
    assert companies[0]["name"] == "Postman"
    out = capsys.readouterr().out
    # structural problems (missing name / wrong type) still warn individually
    assert "Skipping entry" in out
    # placeholders (name but no url) are summarized once, not per-entry
    assert "Skipped 1 companies with no url yet" in out


def test_load_companies_placeholder_entries_are_silently_excluded(tmp_path, capsys):
    """
    A company with a name but no url yet (url is null, missing, or blank)
    is a legitimate placeholder — companies.json may hold hundreds of these
    while URLs are being researched. They should not appear in the returned
    list, and should not produce one warning line each.
    """
    data = [
        {"name": "Boeing", "url": None},
        {"name": "Chevron"},                 # url key entirely absent
        {"name": "Walmart", "url": ""},
        {"name": "Postman", "url": "https://job-boards.greenhouse.io/postman/"},
    ]
    path = tmp_path / "companies.json"
    path.write_text(json.dumps(data))

    companies = load_companies(str(path))

    assert [c["name"] for c in companies] == ["Postman"]
    out = capsys.readouterr().out
    assert out.count("Skipping entry") == 0
    assert "Skipped 3 companies with no url yet" in out


def test_load_companies_strips_whitespace(tmp_path):
    data = [{"name": "  Postman  ", "url": "  https://job-boards.greenhouse.io/postman/  "}]
    path = tmp_path / "companies.json"
    path.write_text(json.dumps(data))

    companies = load_companies(str(path))

    assert companies[0]["name"] == "Postman"
    assert companies[0]["url"] == "https://job-boards.greenhouse.io/postman/"


# ── classify_url ────────────────────────────────────────────────

def test_real_companies_json_placeholder_entries_are_excluded_not_errored():
    """
    companies.json intentionally holds hundreds of placeholder entries
    (name known, url not yet researched) merged in from a legacy company
    list. load_companies must skip these without raising and without
    flooding the log with one warning per entry.
    """
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(repo_root, "companies.json")

    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    raw_placeholder_count = sum(1 for e in raw if not e.get("url"))
    assert raw_placeholder_count > 0, "expected companies.json to contain placeholder entries for this test to be meaningful"

    companies = load_companies(path)

    # every returned company has a real, non-empty url
    assert all(c["url"] for c in companies)
    assert len(companies) == len(raw) - raw_placeholder_count


@pytest.mark.parametrize("url,expected", [
    ("https://job-boards.greenhouse.io/postman/", "greenhouse"),
    ("https://boards.greenhouse.io/stripe/jobs/12345", "greenhouse"),
    ("https://jobs.lever.co/mainspringenergy", "lever"),
    ("https://aptos.wd108.myworkdayjobs.com/Aptos", "js_rendered"),
    ("https://ecge.fa.us2.oraclecloud.com/hcmUI/CandidateExperience/en/sites/CX_1003/jobs", "js_rendered"),
    ("https://myjobs.adp.com/tpxcareers/cx/", "js_rendered"),
    ("https://www.kaiserpermanentejobs.org/", "generic"),
])
def test_classify_url(url, expected):
    assert classify_url(url) == expected


# ── extract_slug ────────────────────────────────────────────────

def test_extract_slug_greenhouse():
    assert extract_slug("https://job-boards.greenhouse.io/postman/", "greenhouse") == "postman"
    assert extract_slug("https://boards.greenhouse.io/stripe/jobs/12345", "greenhouse") == "stripe"


def test_extract_slug_lever():
    assert extract_slug("https://jobs.lever.co/mainspringenergy", "lever") == "mainspringenergy"


def test_extract_slug_no_path_returns_none():
    assert extract_slug("https://job-boards.greenhouse.io/", "greenhouse") is None


# ── build_source_lists ──────────────────────────────────────────

def test_build_source_lists_routes_each_company_correctly():
    companies = [
        {"name": "Postman", "url": "https://job-boards.greenhouse.io/postman/"},
        {"name": "Mainspring Energy", "url": "https://jobs.lever.co/mainspringenergy"},
        {"name": "Kaiser Permanente", "url": "https://www.kaiserpermanentejobs.org/"},
        {"name": "Aptos", "url": "https://aptos.wd108.myworkdayjobs.com/Aptos"},
    ]

    result = build_source_lists(companies)

    assert result["greenhouse_slugs"] == ["postman"]
    assert result["lever_slugs"] == ["mainspringenergy"]
    assert len(result["generic"]) == 1
    assert result["generic"][0]["name"] == "Kaiser Permanente"
    assert len(result["js_rendered"]) == 1
    assert result["js_rendered"][0]["name"] == "Aptos"


def test_build_source_lists_empty_input_returns_empty_buckets():
    result = build_source_lists([])
    assert result == {"greenhouse_slugs": [], "lever_slugs": [], "js_rendered": [], "generic": []}


def test_build_source_lists_against_the_real_companies_json():
    """Sanity check the repo's own companies.json loads and routes cleanly."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    companies = load_companies(os.path.join(repo_root, "companies.json"))
    result = build_source_lists(companies)

    # companies.json now holds many placeholder entries (name known, url not
    # yet researched) alongside verified ones — load_companies excludes the
    # placeholders, so this should be comfortably smaller than the raw file's
    # total entry count, but still cover the companies we know have real URLs.
    assert len(companies) >= 40
    # Postman and Baton use Greenhouse in the sample data
    assert "postman" in result["greenhouse_slugs"]
    assert "baton" in result["greenhouse_slugs"]
    # Mainspring Energy uses Lever
    assert "mainspringenergy" in result["lever_slugs"]
    # Aptos (Workday), Blue Shield + BNY (Oracle Cloud), TPX (ADP) are JS-rendered
    js_names = {c["name"] for c in result["js_rendered"]}
    assert {"Aptos", "Blue Shield of California", "BNY", "TPX"} <= js_names
    # Everything else falls through to generic
    total_routed = (
        len(result["greenhouse_slugs"]) + len(result["lever_slugs"])
        + len(result["js_rendered"]) + len(result["generic"])
    )
    assert total_routed == len(companies)
