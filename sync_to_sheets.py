"""
sync_to_sheets.py  —  NEW FILE (implements the missing Google Sheets feature)

The README promises jobs are synced to a Google Sheet with a new tab per day.
This file implements that. See FIX_GUIDE.md Fix 7 for the full setup walkthrough.

Required env vars (add to .env):
    GOOGLE_SHEET_NAME       — exact name of your Google Sheet
    GOOGLE_CREDENTIALS_PATH — path to your service account JSON key file
                              (defaults to "credentials.json" in project root)
"""

import os
from datetime import datetime

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_AVAILABLE = True
except ImportError:
    GSPREAD_AVAILABLE = False
    print(
        "[sync_to_sheets] gspread not installed. Run:\n"
        "  pip install gspread google-auth"
    )

SCOPES = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

COLUMNS = [
    "Priority",
    "Job Title",
    "Company",
    "Location",
    "Fit Score",
    "Est. Salary",
    "Link",
    "Application Status",
    "Date Found"
]


def _get_sheet(spreadsheet_name):
    """Authenticates with the service account and opens the target spreadsheet."""
    creds_path = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")

    if not os.path.exists(creds_path):
        raise FileNotFoundError(
            f"Credentials file not found at '{creds_path}'.\n"
            "Follow Fix 7 in FIX_GUIDE.md to create a service account and\n"
            "download the JSON key, then set GOOGLE_CREDENTIALS_PATH in .env."
        )

    creds  = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
    client = gspread.authorize(creds)

    try:
        return client.open(spreadsheet_name)
    except gspread.SpreadsheetNotFound:
        raise FileNotFoundError(
            f"Google Sheet '{spreadsheet_name}' not found.\n"
            "Make sure:\n"
            "  1. The sheet exists in your Google Drive\n"
            "  2. It's shared with your service account email\n"
            "  3. GOOGLE_SHEET_NAME in .env matches the sheet name exactly"
        )


def sync_jobs_to_sheet(jobs, spreadsheet_name=None):
    """
    Writes ranked jobs to Google Sheets. Creates a new tab named after today's date.
    If a tab for today already exists it is replaced (idempotent — safe to re-run).

    Args:
        jobs:             list of ranked job dicts (from rank_jobs())
        spreadsheet_name: override env var GOOGLE_SHEET_NAME if needed
    Returns:
        True on success, False on failure
    """
    if not GSPREAD_AVAILABLE:
        print("[sync_to_sheets] Skipping — gspread is not installed.")
        return False

    spreadsheet_name = spreadsheet_name or os.getenv(
        "GOOGLE_SHEET_NAME", "Job Search Pipeline"
    )

    if not jobs:
        print("[sync_to_sheets] No jobs to sync.")
        return False

    try:
        spreadsheet = _get_sheet(spreadsheet_name)
    except FileNotFoundError as e:
        print(f"[sync_to_sheets] {e}")
        return False
    except Exception as e:
        print(f"[sync_to_sheets] Could not open spreadsheet: {e}")
        return False

    today     = datetime.now().strftime("%Y-%m-%d")
    today_str = today  # reused for the Date Found column

    # Delete today's tab if it already exists (makes this re-runnable)
    try:
        existing = spreadsheet.worksheet(today)
        spreadsheet.del_worksheet(existing)
        print(f"[sync_to_sheets] Replaced existing tab '{today}'.")
    except gspread.WorksheetNotFound:
        pass

    worksheet = spreadsheet.add_worksheet(
        title=today,
        rows=max(500, len(jobs) + 10),
        cols=len(COLUMNS)
    )

    # Header row
    worksheet.append_row(COLUMNS, value_input_option="RAW")

    # Format header: bold white text on blue background
    header_range = f"A1:{chr(ord('A') + len(COLUMNS) - 1)}1"
    worksheet.format(header_range, {
        "textFormat": {
            "bold": True,
            "foregroundColor": {"red": 1.0, "green": 1.0, "blue": 1.0}
        },
        "backgroundColor": {"red": 0.0, "green": 0.4, "blue": 0.8},
        "horizontalAlignment": "CENTER"
    })

    # Data rows
    rows = []
    for job in jobs:
        rows.append([
            job.get("Priority",           ""),
            job.get("title",              ""),
            job.get("company",            ""),
            job.get("location",           ""),
            job.get("Fit Score",          ""),
            job.get("Salary",             ""),
            job.get("link",               ""),
            job.get("Application Status", "Not Applied"),   # default per README
            today_str
        ])

    if rows:
        worksheet.append_rows(rows, value_input_option="RAW")

    print(
        f"[sync_to_sheets] ✅ Wrote {len(rows)} jobs to "
        f"tab '{today}' in '{spreadsheet_name}'."
    )
    return True
