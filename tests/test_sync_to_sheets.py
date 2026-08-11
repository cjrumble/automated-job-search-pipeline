import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sync_to_sheets import _get_sheet


def test_empty_credentials_file_gives_actionable_error(tmp_path, monkeypatch):
    """
    Reproduces the exact CI failure: `printf '%s' "$GOOGLE_CREDS" > credentials.json`
    silently writes a 0-byte file when the GOOGLE_CREDENTIALS_JSON secret is
    empty/unset, which used to surface only as a cryptic
    'Expecting value: line 1 column 1 (char 0)' JSONDecodeError.
    """
    creds_path = tmp_path / "credentials.json"
    creds_path.write_text("")  # 0 bytes, exactly as printf produces when $GOOGLE_CREDS is empty
    monkeypatch.setenv("GOOGLE_CREDENTIALS_PATH", str(creds_path))

    with pytest.raises(ValueError) as exc_info:
        _get_sheet("Some Sheet")

    msg = str(exc_info.value)
    assert "empty" in msg.lower()
    assert "GOOGLE_CREDENTIALS_JSON" in msg


def test_malformed_json_credentials_gives_actionable_error(tmp_path, monkeypatch):
    creds_path = tmp_path / "credentials.json"
    creds_path.write_text("{this is not valid json")
    monkeypatch.setenv("GOOGLE_CREDENTIALS_PATH", str(creds_path))

    with pytest.raises(ValueError) as exc_info:
        _get_sheet("Some Sheet")

    assert "not valid JSON" in str(exc_info.value)


def test_valid_json_but_wrong_key_type_gives_actionable_error(tmp_path, monkeypatch):
    """E.g. an API key or OAuth client JSON pasted in instead of a service-account key."""
    creds_path = tmp_path / "credentials.json"
    creds_path.write_text(json.dumps({"api_key": "abc123"}))
    monkeypatch.setenv("GOOGLE_CREDENTIALS_PATH", str(creds_path))

    with pytest.raises(ValueError) as exc_info:
        _get_sheet("Some Sheet")

    msg = str(exc_info.value)
    assert "missing expected service-account key" in msg
    assert "client_email" in msg


def test_missing_credentials_file_still_raises_file_not_found(tmp_path, monkeypatch):
    monkeypatch.setenv("GOOGLE_CREDENTIALS_PATH", str(tmp_path / "does_not_exist.json"))

    with pytest.raises(FileNotFoundError):
        _get_sheet("Some Sheet")
