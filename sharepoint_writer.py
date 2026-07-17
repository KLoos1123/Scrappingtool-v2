"""Schrijft de database naar een Excel-bestand in SharePoint.

Elke run wordt tenders.xlsx volledig overschreven (net als voorheen bij
Google Sheets). Authenticatie via een Azure AD app-registratie
(client-credentials flow, Microsoft Graph API).
"""
import os
from datetime import datetime, timezone
from io import BytesIO

import requests
from openpyxl import Workbook

TENANT_ID = os.environ.get("SHAREPOINT_TENANT_ID")
CLIENT_ID = os.environ.get("SHAREPOINT_CLIENT_ID")
CLIENT_SECRET = os.environ.get("SHAREPOINT_CLIENT_SECRET")

HOSTNAME = "houseofhr.sharepoint.com"
SITE_PAD = "/sites/o365-nlpro-saperp20"
MAP_PAD = "General/Scrappingtool"
BESTANDSNAAM = "tenders.xlsx"

GRAPH = "https://graph.microsoft.com/v1.0"


def _token():
    if not (TENANT_ID and CLIENT_ID and CLIENT_SECRET):
        raise RuntimeError(
            "SHAREPOINT_TENANT_ID, SHAREPOINT_CLIENT_ID of SHAREPOINT_CLIENT_SECRET ontbreekt"
        )

    r = requests.post(
        f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "scope": "https://graph.microsoft.com/.default",
            "grant_type": "client_credentials",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _site_id(token):
    r = requests.get(
        f"{GRAPH}/sites/{HOSTNAME}:{SITE_PAD}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["id"]


def _plat(v):
    """Excel slikt geen dicts/lijsten."""
    if v is None:
        return ""
    if isinstance(v, (dict, list)):
        return str(v)
    return v


def _werkboek(rijen):
    kolommen = list(rijen[0].keys())

    wb = Workbook()
    ws = wb.active
    ws.title = "tenders"
    ws.append(kolommen)
    for r in rijen:
        ws.append([_plat(r.get(k)) for k in kolommen])

    meta = wb.create_sheet("meta")
    meta.append(["laatste_run", datetime.now(timezone.utc).isoformat(timespec="seconds")])
    meta.append(["aantal_rijen", len(rijen)])

    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def sync(rijen):
    """rijen: list van dicts of sqlite3.Row. Overschrijft het hele Excel-bestand."""
    rijen = [dict(r) for r in rijen]
    if not rijen:
        print(f"  {BESTANDSNAAM}: niets te syncen")
        return 0

    token = _token()
    site_id = _site_id(token)
    inhoud = _werkboek(rijen)

    r = requests.put(
        f"{GRAPH}/sites/{site_id}/drive/root:/{MAP_PAD}/{BESTANDSNAAM}:/content",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        },
        data=inhoud,
        timeout=60,
    )
    r.raise_for_status()

    print(f"  {BESTANDSNAAM}: {len(rijen)} rijen gesynct naar SharePoint")
    return len(rijen)
