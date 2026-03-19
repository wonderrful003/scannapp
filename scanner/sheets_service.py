"""
sheets_service.py
Writes scan results to Google Sheets.
Supports both local file and env-variable JSON (for Railway deployment).
"""
import os
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from django.conf import settings

_client = None
_sheet  = None


def _get_sheet():
    """Return cached gspread worksheet, reconnecting if needed."""
    global _client, _sheet
    try:
        if _sheet is None:
            scopes = [
                'https://spreadsheets.google.com/feeds',
                'https://www.googleapis.com/auth/drive',
            ]

            # Production: JSON stored as environment variable
            json_str = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
            if json_str:
                print("[SHEETS] Using service account from environment variable")
                info   = json.loads(json_str)
                creds  = Credentials.from_service_account_info(info, scopes=scopes)
                _client = gspread.authorize(creds)
            else:
                # Local dev: use file
                print("[SHEETS] Using service account from file")
                _client = gspread.service_account(
                    filename=settings.GOOGLE_SERVICE_ACCOUNT_FILE
                )

            spreadsheet = _client.open_by_key(settings.GOOGLE_SHEET_ID)
            _sheet = spreadsheet.sheet1
            print(f"[SHEETS] Connected to sheet: {spreadsheet.title}")

        return _sheet

    except Exception as e:
        print(f"[SHEETS] Connection error: {e}")
        _client = None
        _sheet  = None
        raise


def append_scan(code: str, raw_text: str = '') -> dict:
    """
    Append a row to Google Sheet:
    [Scanned Code | Timestamp | Date | Time | Raw OCR]
    """
    try:
        sheet = _get_sheet()
        now   = datetime.now()

        row = [
            code,
            now.strftime('%Y-%m-%d %H:%M:%S'),
            now.strftime('%Y-%m-%d'),
            now.strftime('%H:%M:%S'),
            raw_text[:200] if raw_text else '',
        ]

        sheet.append_row(row, value_input_option='USER_ENTERED')
        print(f"[SHEETS] Saved row: {code}")
        return {'success': True}

    except Exception as e:
        print(f"[SHEETS] Error saving: {e}")
        return {'success': False, 'error': str(e)}


def setup_headers() -> dict:
    """One-time setup: add bold header row."""
    try:
        sheet = _get_sheet()
        if sheet.row_count == 0 or not sheet.cell(1, 1).value:
            sheet.insert_row(
                ['Scanned Code', 'Full Timestamp', 'Date', 'Time', 'Raw OCR'],
                index=1
            )
            sheet.format('A1:E1', {'textFormat': {'bold': True}})
            print("[SHEETS] Headers added")
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}
