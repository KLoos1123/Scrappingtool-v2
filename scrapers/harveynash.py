"""Harvey Nash - interim vacatures.

Publieke lijst op harveynash.nl/vacatures, client-side gerenderd (Next.js).
De pagina bevraagt een JSON-zoek-API (/_sf/api/v1/jobs/search.json) die in
één POST alle velden teruggeeft; geen login of aparte token nodig.
"""

import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

BRON = "harveynash"

APP = "https://www.harveynash.nl"
API = f"{APP}/_sf/api/v1/jobs/search.json"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

BLOK = 50
MAX_PAGINA = 20  # veiligheidsgrens


def _payload(offset):
    return {
        "job_search": {
            "query": "",
            "location": {"address": "", "radius": 5, "region": "NL", "radius_units": "miles"},
            "filters": {},
            "commute_filter": {},
            "offset": offset,
            "jobs_per_page": BLOK,
        }
    }


def _categorie(job, naam):
    for c in job.get("categories") or []:
        if c.get("name") == naam:
            waarden = c.get("values") or []
            return waarden[0].get("name") if waarden else None
    return None


def _tijd(epoch):
    if not epoch:
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat(timespec="seconds")


def _oms(job):
    html = job.get("description")
    if not html:
        return None
    tekst = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    return tekst or None


def _uit_job(job):
    jid = job.get("id")
    slug = job.get("url_slug")
    return {
        "tender_id": str(jid),
        "nummer": job.get("external_reference"),
        "titel": job.get("title"),
        "organisatie": _categorie(job, "Clients"),
        "status": "Open",
        "deadline": _tijd(job.get("expires_at")),
        "publicatiedatum": _tijd(job.get("published_at")),
        "locatie": (job.get("addresses") or [None])[0] or job.get("original_location"),
        "omschrijving": _oms(job),
        "url": f"{APP}/vacatures/{slug}" if slug else f"{APP}/vacatures",
    }


def haal_op():
    """Wordt aangeroepen door run.py. Geeft een lijst dicts terug."""
    sessie = requests.Session()
    headers = {"user-agent": UA, "content-type": "application/json", "accept": "application/json"}

    rijen = []
    offset = 0
    totaal = None

    for _ in range(MAX_PAGINA):
        r = sessie.post(API, json=_payload(offset), headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()

        if totaal is None:
            totaal = data.get("total_size") or 0
            print(f"  {totaal} vacatures gemeld")

        blok = [res.get("job") for res in (data.get("results") or []) if res.get("job")]
        if not blok:
            break

        rijen.extend(_uit_job(j) for j in blok if j.get("id"))

        offset += BLOK
        if offset >= (totaal or 0):
            break

    print(f"  {len(rijen)} vacatures opgehaald")
    return rijen
