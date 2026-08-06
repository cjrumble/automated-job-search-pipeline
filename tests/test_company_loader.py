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
        {"name": "No URL Co"},                      # missing url
        {"url": "https://example.com"},              # missing name
        {"name": "", "url": "https://example.com"},  # blank name
        "not even an object",                         # wrong type
    ]
    path = tmp_path / "companies.json"
    path.write_text(json.dumps(data))

    companies = load_companies(str(path))

    assert len(companies) == 1
    assert companies[0]["name"] == "Postman"
    # warnings were printed rather than raising
    assert "Skipping entry" in capsys.readouterr().out


def test_load_companies_strips_whitespace(tmp_path):
    data = [{"name": "  Postman  ", "url": "  https://job-boards.greenhouse.io/postman/  "}]
    path = tmp_path / "companies.json"
    path.write_text(json.dumps(data))

    companies = load_companies(str(path))

    assert companies[0]["name"] == "Postman"
    assert companies[0]["url"] == "https://job-boards.greenhouse.io/postman/"


# ── classify_url ────────────────────────────────────────────────

@pytest.mark.parametrize("url,expected", [
    ("https://job-boards.greenhouse.io/postman/", "greenhouse"),
    ("https://boards.greenhouse.io/stripe/jobs/12345", "greenhouse"),
    ("https://jobs.lever.co/mainspringenergy", "lever"),
    ("https://www.kaiserpermanentejobs.org/", "generic"),
    ("https://aptos.wd108.myworkdayjobs.com/Aptos", "generic"),
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
    ]

    result = build_source_lists(companies)

    assert result["greenhouse_slugs"] == ["postman"]
    assert result["lever_slugs"] == ["mainspringenergy"]
    assert len(result["generic"]) == 1
    assert result["generic"][0]["name"] == "Kaiser Permanente"


def test_build_source_lists_empty_input_returns_empty_buckets():
    result = build_source_lists([])
    assert result == {"greenhouse_slugs": [], "lever_slugs": [], "generic": []}


def test_build_source_lists_against_the_real_companies_json():
    """Sanity check the repo's own companies.json loads and routes cleanly."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    companies = load_companies(os.path.join(repo_root, "companies.json"))
    result = build_source_lists(companies)

    assert len(companies) == 26
    # Postman and Baton use Greenhouse in the sample data
    assert "postman" in result["greenhouse_slugs"]
    assert "baton" in result["greenhouse_slugs"]
    # Mainspring Energy uses Lever
    assert "mainspringenergy" in result["lever_slugs"]
    # Everything else falls through to generic
    assert len(result["generic"]) == len(companies) - len(result["greenhouse_slugs"]) - len(result["lever_slugs"])
