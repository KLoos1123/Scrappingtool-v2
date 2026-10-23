"""Synchroniseert gescrapete tenders/omschrijvingen naar Supabase.

Supabase is de databron voor het live dashboard (real-time, met een
per-tender workflow-status die gebruikers zelf zetten). Dit script raakt
de status / status_gewijzigd_door / status_gewijzigd_op kolommen NOOIT aan
-- dat zijn door gebruikers gezette waarden uit het dashboard en worden
hier bewust nooit overschreven (zie upsert_tenders_bulk in
supabase_migration.sql).

Vereiste env vars (zet als GitHub Actions secrets):
    SUPABASE_URL                 bv. https://xxxx.supabase.co
    SUPABASE_SERVICE_ROLE_KEY    service_role key (NOOIT de anon key hier
                                  gebruiken -- deze bypassed row level
                                  security en mag alleen server-side draaien)
"""

import os
from datetime import datetime, timezone

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

BATCH = 500  # rijen per request; houdt de payload en de plpgsql-loop overzichtelijk


def _configured():
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


def _headers(extra=None):
    if not _configured():
        raise RuntimeError(
            "SUPABASE_URL en/of SUPABASE_SERVICE_ROLE_KEY ontbreken. "
            "Zet ze als secrets in de GitHub Action (zie SETUP_SUPABASE.md)."
        )
    headers = {
        "apikey": SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


def _chunks(lijst, grootte):
    for i in range(0, len(lijst), grootte):
        yield lijst[i:i + grootte]


def sync_tenders(rijen):
    """rijen: dicts zoals verzameld in run.py (bron, tender_id, nummer, titel,
    organisatie, status [= bron-status, zoals de scraper 'm aanlevert],
    deadline, publicatiedatum, locatie, url).

    Slaat rijen zonder bron of tender_id over. Geeft het aantal gesyncte
    rijen terug.
    """
    payload = [
        {
            "bron": r.get("bron"),
            "tender_id": str(r.get("tender_id") if r.get("tender_id") is not None else r.get("nummer") or ""),
            "nummer": r.get("nummer"),
            "titel": r.get("titel"),
            "organisatie": r.get("organisatie"),
            "bron_status": r.get("status"),
            "deadline": r.get("deadline"),
            "publicatiedatum": r.get("publicatiedatum"),
            "locatie": r.get("locatie"),
            "url": r.get("url"),
        }
        for r in rijen
        if r.get("bron") and (r.get("tender_id") or r.get("nummer"))
    ]
    if not payload:
        return 0

    url = f"{SUPABASE_URL}/rest/v1/rpc/upsert_tenders_bulk"
    n = 0
    for chunk in _chunks(payload, BATCH):
        resp = requests.post(url, headers=_headers(), json={"rows": chunk}, timeout=60)
        if not resp.ok:
            raise RuntimeError(f"upsert_tenders_bulk mislukt ({resp.status_code}): {resp.text[:500]}")
        n += len(chunk)
    return n


def sync_beschrijvingen(rijen):
    """rijen: dicts met minimaal bron, tender_id, omschrijving.

    Overschrijft omschrijving + opgehaald_op altijd (zelfde gedrag als
    beschrijvingen.py). Geeft het aantal gesyncte rijen terug.
    """
    nu = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = []
    for r in rijen:
        tekst = (r.get("omschrijving") or "").strip()
        bron = r.get("bron")
        tid = r.get("tender_id")
        if not tekst or not bron or tid is None:
            continue
        payload.append({
            "bron": bron,
            "tender_id": str(tid),
            "omschrijving": tekst[:4000],
            "opgehaald_op": nu,
        })
    if not payload:
        return 0

    url = f"{SUPABASE_URL}/rest/v1/beschrijvingen"
    headers = _headers({"Prefer": "resolution=merge-duplicates"})
    n = 0
    for chunk in _chunks(payload, BATCH):
        resp = requests.post(url, headers=headers, json=chunk, timeout=60)
        if not resp.ok:
            raise RuntimeError(f"beschrijvingen-sync mislukt ({resp.status_code}): {resp.text[:500]}")
        n += len(chunk)
    return n


def sync_verrijkingen(rijen):
    """rijen: zoals db.verrijkingen() ze teruggeeft. Overschrijft bestaande
    verrijkingen. Geeft het aantal gesyncte rijen terug."""
    payload = [
        {
            "bron": r["bron"],
            "tender_id": str(r["tender_id"]),
            "eindklant": r["data"].get("eindklant"),
            "eindklant_zekerheid": r["data"].get("eindklant_zekerheid"),
            "senioriteit": r["data"].get("senioriteit"),
            "modules": r["data"].get("modules") or [],
            "data": r["data"],
            "model": r.get("model"),
            "verrijkt_op": r["verrijkt_op"],
        }
        for r in rijen
    ]
    if not payload:
        return 0

    url = f"{SUPABASE_URL}/rest/v1/verrijkingen"
    headers = _headers({"Prefer": "resolution=merge-duplicates"})
    n = 0
    for chunk in _chunks(payload, BATCH):
        resp = requests.post(url, headers=headers, json=chunk, timeout=60)
        if not resp.ok:
            raise RuntimeError(f"verrijkingen-sync mislukt ({resp.status_code}): {resp.text[:500]}")
        n += len(chunk)
    return n


def sync_tarieven(rijen):
    """rijen: zoals tarieven.verzamel() ze teruggeeft (tarief en/of uren).
    Overschrijft bestaande rijen. Geeft het aantal gesyncte rijen terug.

    Zonder supabase/uren.sql kent de tabel nog geen uren- en kenmerken-kolommen
    en moet het tarief gevuld zijn; dan sturen we alleen de tarieven."""
    nu = datetime.now(timezone.utc).isoformat(timespec="seconds")
    payload = [
        {
            "bron": r["bron"],
            "tender_id": str(r["tender_id"]),
            "tarief": r.get("tarief"),
            "tarief_min": r.get("tarief_min"),
            "tarief_max": r.get("tarief_max"),
            "herkomst": r.get("herkomst"),
            "uren": r.get("uren"),
            "uren_min": r.get("uren_min"),
            "uren_max": r.get("uren_max"),
            "contractvorm": r.get("contractvorm"),
            "startdatum": r.get("startdatum"),
            "duur": r.get("duur"),
            "verlenging": r.get("verlenging"),
            "gevonden_op": nu,
        }
        for r in rijen
    ]
    if not payload:
        return 0

    url = f"{SUPABASE_URL}/rest/v1/tarieven"
    headers = _headers({"Prefer": "resolution=merge-duplicates"})

    def stuur(rijen_):
        n = 0
        for chunk in _chunks(rijen_, BATCH):
            resp = requests.post(url, headers=headers, json=chunk, timeout=60)
            if not resp.ok:
                raise RuntimeError(f"tarieven-sync mislukt ({resp.status_code}): {resp.text[:500]}")
            n += len(chunk)
        return n

    kenm = ("contractvorm", "startdatum", "duur", "verlenging")
    uren = ("uren", "uren_min", "uren_max")
    try:
        return stuur(payload)
    except RuntimeError as e:
        if not any(k in str(e) for k in kenm + uren + ("tarief",)):
            raise
    # oudere tabel: eerst zonder kenmerken, en zo nodig ook zonder uren
    try:
        n = stuur([{k: v for k, v in r.items() if k not in kenm} for r in payload if r["tarief"] or r["uren"]])
        print("  tabel tarieven kent nog geen kenmerken (voer supabase/uren.sql uit); tarieven en uren gesynct")
        return n
    except RuntimeError as e:
        if not any(k in str(e) for k in uren + ("tarief",)):
            raise
    print("  tabel tarieven kent nog geen uren/kenmerken (voer supabase/uren.sql uit); alleen tarieven gesynct")
    return stuur([{k: v for k, v in r.items() if k not in kenm + uren} for r in payload if r["tarief"]])
