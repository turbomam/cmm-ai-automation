"""Google Sheets integration for CMM data access.

This module provides utilities for reading and writing data from Google Sheets,
specifically designed for the BER CMM Data spreadsheet.

Authentication:
    Uses Google Service Account credentials. Set the GOOGLE_APPLICATION_CREDENTIALS
    environment variable to the path of your service account JSON file, or place
    the credentials in ~/.config/gspread/service_account.json

Example:
    >>> from cmm_ai_automation.gsheets import get_sheet_data
    >>> df = get_sheet_data("BER CMM Data for AI - for editing", "media_ingredients")
"""

import os
from pathlib import Path

import gspread
import pandas as pd
from google.oauth2.service_account import Credentials

# Default scopes for Google Sheets API
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

# Known spreadsheet IDs (can be extended)
KNOWN_SHEETS = {
    "BER CMM Data for AI - for editing": "1h-kOdyvVb1EJPqgTiklTN9Z8br_8bP8KGmxA19clo7Q",
}


def get_gspread_client(credentials_path: str | None = None) -> gspread.Client:
    """Get an authenticated gspread client.

    Args:
        credentials_path: Path to service account JSON file. If None, checks
            GOOGLE_APPLICATION_CREDENTIALS env var, then default gspread location.

    Returns:
        Authenticated gspread Client

    Raises:
        FileNotFoundError: If no credentials file is found
    """
    if credentials_path is None:
        credentials_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

    if credentials_path is None:
        default_path = Path.home() / ".config" / "gspread" / "service_account.json"
        if default_path.exists():
            credentials_path = str(default_path)

    if credentials_path is None:
        raise FileNotFoundError(
            "No Google credentials found. Set GOOGLE_APPLICATION_CREDENTIALS "
            "or place credentials in ~/.config/gspread/service_account.json"
        )

    creds = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    return gspread.authorize(creds)


def get_spreadsheet(name_or_id: str, credentials_path: str | None = None) -> gspread.Spreadsheet:
    """Open a Google Spreadsheet by name or ID.

    Args:
        name_or_id: Spreadsheet name (from KNOWN_SHEETS) or Google Sheets ID
        credentials_path: Optional path to service account credentials

    Returns:
        gspread Spreadsheet object
    """
    client = get_gspread_client(credentials_path)

    # Check if it's a known sheet name
    sheet_id = KNOWN_SHEETS.get(name_or_id, name_or_id)

    # Try to open by ID first (more reliable)
    if len(sheet_id) > 30:  # Likely a Google Sheets ID
        return client.open_by_key(sheet_id)
    else:
        return client.open(name_or_id)


def list_worksheets(name_or_id: str, credentials_path: str | None = None) -> list[str]:
    """List all worksheet (tab) names in a spreadsheet.

    Args:
        name_or_id: Spreadsheet name or ID
        credentials_path: Optional path to service account credentials

    Returns:
        List of worksheet names
    """
    spreadsheet = get_spreadsheet(name_or_id, credentials_path)
    return [ws.title for ws in spreadsheet.worksheets()]


def get_sheet_records(
    spreadsheet_name: str,
    worksheet_name: str | None = None,
    credentials_path: str | None = None,
) -> list[dict[str, str | int | float]]:
    """Read data from a Google Sheets worksheet as a list of dicts.

    Handles sheets with trailing empty columns (which cause duplicate header errors
    in gspread's get_all_records).

    Args:
        spreadsheet_name: Name or ID of the spreadsheet
        worksheet_name: Name of the worksheet/tab. If None, uses the first sheet.
        credentials_path: Optional path to service account credentials

    Returns:
        List of dicts, one per row (keys are column headers)
    """
    spreadsheet = get_spreadsheet(spreadsheet_name, credentials_path)
    worksheet = spreadsheet.worksheet(worksheet_name) if worksheet_name else spreadsheet.sheet1

    # Use get_all_values to avoid errors from trailing empty columns that would
    # cause duplicate header issues in get_all_records
    all_values = worksheet.get_all_values()
    if not all_values:
        return []

    # Get headers and strip trailing empty columns
    headers = all_values[0]
    # Find last non-empty header
    last_valid_idx = len(headers) - 1
    while last_valid_idx >= 0 and not headers[last_valid_idx].strip():
        last_valid_idx -= 1

    if last_valid_idx < 0:
        return []  # No valid headers

    # Trim headers to valid columns
    headers = headers[: last_valid_idx + 1]

    # Validate: check for empty or duplicate headers in the trimmed set
    # (empty/duplicate headers would cause silent data loss with dict())
    empty_header_positions = [i for i, h in enumerate(headers) if not h.strip()]
    if empty_header_positions:
        raise ValueError(
            f"Empty column header(s) at position(s) {empty_header_positions}. "
            "Please add column names or remove empty columns from the spreadsheet."
        )

    seen_headers: dict[str, int] = {}
    duplicate_headers: list[tuple[str, int, int]] = []
    for i, h in enumerate(headers):
        if h in seen_headers:
            duplicate_headers.append((h, seen_headers[h], i))
        else:
            seen_headers[h] = i

    if duplicate_headers:
        details = ", ".join(f"'{h}' at columns {first} and {second}" for h, first, second in duplicate_headers)
        raise ValueError(f"Duplicate column header(s): {details}. Please rename duplicate columns in the spreadsheet.")

    # Build records from trimmed data
    records: list[dict[str, str | int | float]] = []
    for row in all_values[1:]:
        trimmed_row = row[: last_valid_idx + 1]
        # Pad row if shorter than headers
        while len(trimmed_row) < len(headers):
            trimmed_row.append("")
        records.append(dict(zip(headers, trimmed_row, strict=False)))

    return records


def get_sheet_data(
    spreadsheet_name: str,
    worksheet_name: str | None = None,
    credentials_path: str | None = None,
) -> pd.DataFrame:
    """Read data from a Google Sheets worksheet into a DataFrame.

    Args:
        spreadsheet_name: Name or ID of the spreadsheet
        worksheet_name: Name of the worksheet/tab. If None, uses the first sheet.
        credentials_path: Optional path to service account credentials

    Returns:
        pandas DataFrame with the sheet data
    """
    records = get_sheet_records(spreadsheet_name, worksheet_name, credentials_path)
    return pd.DataFrame(records)


def update_sheet_data(
    spreadsheet_name: str,
    worksheet_name: str,
    df: pd.DataFrame,
    credentials_path: str | None = None,
    clear_first: bool = True,
) -> None:
    """Write a DataFrame to a Google Sheets worksheet.

    Args:
        spreadsheet_name: Name or ID of the spreadsheet
        worksheet_name: Name of the worksheet/tab
        df: DataFrame to write
        credentials_path: Optional path to service account credentials
        clear_first: If True, clear the worksheet before writing
    """
    spreadsheet = get_spreadsheet(spreadsheet_name, credentials_path)
    worksheet = spreadsheet.worksheet(worksheet_name)

    if clear_first:
        worksheet.clear()

    # Convert DataFrame to list of lists (including header)
    data = [df.columns.tolist(), *df.values.tolist()]
    worksheet.update(data, "A1")
