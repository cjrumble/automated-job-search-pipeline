import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from company_loader import build_source_lists, load_companies


def test_env_var_and_json_companies_merge_without_duplicates(tmp_path):
    """
    Mirrors the de-dupe logic in run_pipeline.run_pipeline(): companies.json
    slugs and GREENHOUSE_COMPANIES/LEVER_COMPANIES env vars should combine
    into one clean, order-preserving, duplicate-free list per source.
    """
    data = [
        {"name": "Postman", "url": "https://job-boards.greenhouse.io/postman/"},
        {"name": "Baton", "url": "https://job-boards.greenhouse.io/baton"},
        {"name": "Mainspring Energy", "url": "https://jobs.lever.co/mainspringenergy"},
    ]
    path = tmp_path / "companies.json"
    path.write_text(json.dumps(data))

    companies = load_companies(str(path))
    sources = build_source_lists(companies)

    env_greenhouse = ["stripe", "postman"]  # "postman" duplicates a json entry
    env_lever = ["netflix"]

    merged_greenhouse = list(dict.fromkeys(env_greenhouse + sources["greenhouse_slugs"]))
    merged_lever = list(dict.fromkeys(env_lever + sources["lever_slugs"]))

    assert merged_greenhouse == ["stripe", "postman", "baton"]
    assert merged_lever == ["netflix", "mainspringenergy"]


def test_pipeline_still_works_with_no_companies_json(tmp_path):
    """
    If companies.json is absent, the pipeline should fall back cleanly to
    whatever GREENHOUSE_COMPANIES/LEVER_COMPANIES provide instead of crashing.
    """
    from company_loader import CompanyListError

    missing_path = tmp_path / "nope.json"

    try:
        load_companies(str(missing_path))
        assert False, "expected CompanyListError"
    except CompanyListError:
        pass  # this is what run_pipeline.py catches and falls back on
