"""
company_loader.py — reads companies.json and routes each company to the
scraper that can actually handle its careers site.

companies.json format (list of objects):
    [
      { "name": "Postman", "url": "https://job-boards.greenhouse.io/postman/" },
      { "name": "Mainspring Energy", "url": "https://jobs.lever.co/mainspringenergy" },
      ...
    ]

Only Greenhouse and Lever expose a public, unauthenticated JSON API, so those
are the two sources the pipeline can scrape automatically. Every other URL
(Workday, Oracle Cloud/Taleo, ADP, a company's own custom careers page, etc.)
is routed to scrape_generic, a best-effort HTML scraper — see scrape_generic.py
for its limits.
"""

import json
from urllib.parse import urlparse

REQUIRED_KEYS = ("name", "url")


class CompanyListError(ValueError):
    """Raised when companies.json is missing, unreadable, or malformed."""


def load_companies(path="companies.json"):
    """
    Loads and validates the company list from a JSON file.

    Args:
        path: path to a JSON file containing a list of {"name", "url"} objects.
    Returns:
        list of dicts: [{"name": str, "url": str}, ...] — entries missing a
        required key or with a blank value are skipped (with a printed
        warning) rather than crashing the whole pipeline.
    Raises:
        CompanyListError: if the file is missing, isn't valid JSON, or the
        top-level JSON value isn't a list.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        raise CompanyListError(f"Company list not found at '{path}'.")
    except json.JSONDecodeError as e:
        raise CompanyListError(f"'{path}' is not valid JSON: {e}")

    if not isinstance(raw, list):
        raise CompanyListError(
            f"'{path}' must contain a JSON list of company objects."
        )

    companies = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            print(f"[company_loader] Skipping entry {i}: not an object.")
            continue

        missing = [k for k in REQUIRED_KEYS if not entry.get(k)]
        if missing:
            print(f"[company_loader] Skipping entry {i}: missing {missing}.")
            continue

        companies.append({"name": entry["name"].strip(), "url": entry["url"].strip()})

    return companies


def classify_url(url):
    """
    Determines which scraper can handle a given careers-site URL.

    Returns one of: "greenhouse", "lever", "generic"
    """
    host = urlparse(url).netloc.lower()

    if "greenhouse.io" in host:
        return "greenhouse"
    if "lever.co" in host:
        return "lever"
    return "generic"


def extract_slug(url, board):
    """
    Pulls the ATS board slug out of a Greenhouse or Lever URL.

    Examples:
        https://job-boards.greenhouse.io/postman/        -> "postman"
        https://boards.greenhouse.io/stripe/jobs/12345    -> "stripe"
        https://jobs.lever.co/mainspringenergy            -> "mainspringenergy"

    Returns None if no slug-shaped path segment is found.
    """
    path_parts = [p for p in urlparse(url).path.split("/") if p]

    if board == "greenhouse":
        # First path segment after the host is always the board slug.
        return path_parts[0] if path_parts else None

    if board == "lever":
        return path_parts[0] if path_parts else None

    return None


def build_source_lists(companies):
    """
    Splits a company list (as returned by load_companies) into the buckets
    each scraper expects.

    Returns:
        {
          "greenhouse_slugs": [str, ...],
          "lever_slugs":      [str, ...],
          "generic":          [{"name": str, "url": str}, ...],
        }
    """
    greenhouse_slugs, lever_slugs, generic = [], [], []

    for company in companies:
        board = classify_url(company["url"])

        if board == "greenhouse":
            slug = extract_slug(company["url"], board)
            if slug:
                greenhouse_slugs.append(slug)
            else:
                print(f"[company_loader] Couldn't parse Greenhouse slug for '{company['name']}' — skipping.")
        elif board == "lever":
            slug = extract_slug(company["url"], board)
            if slug:
                lever_slugs.append(slug)
            else:
                print(f"[company_loader] Couldn't parse Lever slug for '{company['name']}' — skipping.")
        else:
            generic.append(company)

    return {
        "greenhouse_slugs": greenhouse_slugs,
        "lever_slugs": lever_slugs,
        "generic": generic,
    }
