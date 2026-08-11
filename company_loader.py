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
are the two sources the pipeline can scrape automatically without a browser.
Workday, Oracle Cloud/Taleo, and ADP render their listings client-side with
JavaScript, so those are routed to the Playwright-based scraper instead of
the plain-HTML one. Anything else falls back to a best-effort static scrape
— see scrape_generic.py and scrape_js.py for what each actually does.
"""

import json
from urllib.parse import urlparse

REQUIRED_KEYS = ("name", "url")

# Hostname fragments for ATS platforms known to render job listings with
# client-side JS. requests+BeautifulSoup can't see into these — they need
# scrape_js.py (Playwright) instead of scrape_generic.py.
_JS_RENDERED_HOSTS = (
    "myworkdayjobs.com",   # Workday
    "oraclecloud.com",     # Oracle Cloud / Fusion HCM "CX" boards
    "adp.com",             # ADP (myjobs.adp.com)
)


class CompanyListError(ValueError):
    """Raised when companies.json is missing, unreadable, or malformed."""


def load_companies(path="companies.json"):
    """
    Loads and validates the company list from a JSON file.

    Args:
        path: path to a JSON file containing a list of {"name", "url"} objects.
    Returns:
        list of dicts: [{"name": str, "url": str}, ...] — only entries with
        both a name and a url. Entries with a name but no url (or a blank
        url) are treated as placeholders — companies you've listed but
        haven't found/verified a careers URL for yet — and are silently
        excluded with a single summary count, not a per-entry warning,
        since companies.json may legitimately hold hundreds of these while
        they're being researched. Entries missing a name, or that aren't
        objects at all, are structural problems and still get an individual
        warning.
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
    placeholder_count = 0
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            print(f"[company_loader] Skipping entry {i}: not an object.")
            continue

        name = entry.get("name")
        if not name or not str(name).strip():
            print(f"[company_loader] Skipping entry {i}: missing 'name'.")
            continue

        url = entry.get("url")
        if not url or not str(url).strip():
            # Intentional placeholder — name known, URL not yet researched.
            # Don't spam one warning per entry; just tally and summarize.
            placeholder_count += 1
            continue

        companies.append({"name": str(name).strip(), "url": str(url).strip()})

    if placeholder_count:
        print(
            f"[company_loader] Skipped {placeholder_count} companies with no "
            f"url yet (placeholders) — add a url in companies.json to enable them."
        )

    return companies


def classify_url(url):
    """
    Determines which scraper can handle a given careers-site URL.

    Returns one of: "greenhouse", "lever", "js_rendered", "generic"
    """
    host = urlparse(url).netloc.lower()

    if "greenhouse.io" in host:
        return "greenhouse"
    if "lever.co" in host:
        return "lever"
    if any(fragment in host for fragment in _JS_RENDERED_HOSTS):
        return "js_rendered"
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
          "js_rendered":      [{"name": str, "url": str}, ...],
          "generic":          [{"name": str, "url": str}, ...],
        }
    """
    greenhouse_slugs, lever_slugs, js_rendered, generic = [], [], [], []

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
        elif board == "js_rendered":
            js_rendered.append(company)
        else:
            generic.append(company)

    return {
        "greenhouse_slugs": greenhouse_slugs,
        "lever_slugs": lever_slugs,
        "js_rendered": js_rendered,
        "generic": generic,
    }
