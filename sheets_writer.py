"""Schrijft de database naar Google Sheets.
De Sheet is een view op de SQLite database, geen tweede bron van waarheid.
Elke run wordt de tab volledig overschreven.
"""
import os
import json
from datetime import datetime, timezone

import gspread
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _client():
    raw = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
    if not raw:
        raise RuntimeError("Secret GOOGLE_SERVICE_ACCOUNT_JSON ontbreekt.")
    creds = Credentials.from_service_account_info(json.loads(raw), scopes=SCOPES)
    return gspread.authorize(creds)


def _plat(v):
    """Sheets slikt geen None, datetimes of nested types."""
    if v is None:
        return ""
    if isinstance(v, datetime):
        return v.isoformat(timespec="seconds")
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False)
    return str(v)


def sync(rijen, tab="tenders"):
    """rijen: list van dicts of sqlite3.Row. Overschrijft de hele tab."""
    rijen = [dict(r) for r in rijen]
    if not rijen:
        print(f"  {tab}: niets te syncen")
        return 0

    sheet_id = os.environ.get("SHEET_ID")
    if not sheet_id:
        raise RuntimeError("Secret SHEET_ID ontbreekt.")

    kolommen = list(rijen[0].keys())
    matrix = [kolommen] + [[_plat(r.get(k)) for k in kolommen] for r in rijen]

    gc = _client()
    sh = gc.open_by_key(sheet_id)

    try:
        ws = sh.worksheet(tab)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=tab, rows=max(len(matrix) + 100, 1000),
                              cols=len(kolommen))

    benodigd = len(matrix) + 50
    if ws.row_count < benodigd:
        ws.add_rows(benodigd - ws.row_count)
    if ws.col_count < len(kolommen):
        ws.add_cols(len(kolommen) - ws.col_count)

    ws.clear()
    ws.update(values=matrix, range_name="A1", value_input_option="RAW")
    ws.freeze(rows=1)

    print(f"  {tab}: {len(rijen)} rijen gesynct naar Sheets")
    return len(rijen)


def schrijf_meta(aantal, tab="meta"):
    """Zet het tijdstip van de laatste run in een aparte tab."""
    print(os.environ)
    sheet_id = os.environ["SHEET_ID"]
    gc = _client()
    sh = gc.open_by_key(sheet_id)
    try:
        ws = sh.worksheet(tab)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=tab, rows=10, cols=2)
    ws.clear()
    ws.update(values=[
        ["laatste_run", datetime.now(timezone.utc).isoformat(timespec="seconds")],
        ["aantal_rijen", str(aantal)],
    ], range_name="A1", value_input_option="RAW")
