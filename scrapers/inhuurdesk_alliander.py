"""Inhuurdesk Alliander - inhuuraanvragen van Alliander.

Publieke lijst op inhuurdeskalliander.nl/aanvragen (WordPress met de
Headfirst-plugin "headfirst-assignments"). De kaarten worden client-side
geladen uit een JSON-API (/wp-json/headfirst-assignments/search, 30 per
pagina) die per aanvraag alle velden teruggeeft: sluitingsdatum, uren,
locatie en de volledige omschrijving. Geen login of token nodig.

De aanvragen komen uit Nétive VMS (staffingdesk.my.site.com, zelfde platform
als staffingms.py); het SRQ-nummer staat in 'nummer'.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

BRON = "inhuurdesk-alliander"

BASE = "https://inhuurdeskalliander.nl"
API = f"{BASE}/wp-json/headfirst-assignments/search"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

BLOK = 30  # vaste paginagrootte van de plugin
MAX_PAGINA = 30  # veiligheidsgrens
OPEN = 2  # jobStatus 2 = open aanvraag (de site toont andere als 'closed')
NL = ZoneInfo("Europe/Amsterdam")


def _tijd(waarde):
    """'2026-10-27T16:00:00' (lokale tijd, zonder zone) -> ISO met NL-tijdzone."""
    if not waarde:
        return None
    try:
        return datetime.fromisoformat(waarde).replace(tzinfo=NL).isoformat()
    except ValueError:
        return waarde


def _oms(html):
    if not html:
        return None
    tekst = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    return tekst or None


def _uren(job):
    laag, hoog = job.get("hoursPerWeekMin"), job.get("hoursPerWeekMax")
    if not hoog:
        return None
    if laag and laag != hoog:
        return f"{laag}-{hoog}"
    return str(hoog)


def _uit_job(job):
    jid = job.get("id")
    rij = {
        "tender_id": str(jid),
        "nummer": job.get("referenceCode") or job.get("recordId"),
        "titel": job.get("title"),
        "organisatie": job.get("clientName") or "Alliander",
        "status": "Open" if job.get("jobStatus") == OPEN else "Gesloten",
        "deadline": _tijd(job.get("closingDateClient")),
        "publicatiedatum": _tijd(job.get("publishedDate")),
        "locatie": job.get("location"),
        "omschrijving": _oms(job.get("content")),
        "uren_per_week": _uren(job),
        "url": f"{BASE}/aanvragen/{job.get('clientNameSlug') or 'alliander'}/"
               f"{job.get('titleSlug')}/{jid}",
    }
    # tarief alleen als veld gevuld (meestal 0; het max-tarief staat dan in de tekst)
    if job.get("hourlyRateMin"):
        rij["tarief_min"] = job["hourlyRateMin"]
    if job.get("hourlyRateMax"):
        rij["tarief_max"] = job["hourlyRateMax"]
    return rij


def haal_op():
    """Wordt aangeroepen door run.py. Geeft een lijst dicts terug."""
    sessie = requests.Session()
    headers = {"user-agent": UA, "accept": "application/json"}

    rijen = []
    gezien = set()
    totaal = None

    for pagina in range(1, MAX_PAGINA + 1):
        r = sessie.get(API, params={"size": BLOK, "page": pagina},
                       headers=headers, timeout=30)
        r.raise_for_status()
        data = r.json()

        if totaal is None:
            totaal = data.get("total") or 0
            print(f"  {totaal} aanvragen gemeld")

        blok = data.get("data") or []
        if not blok:
            break

        for job in blok:
            if job.get("id") and job["id"] not in gezien:
                gezien.add(job["id"])
                rijen.append(_uit_job(job))

        if pagina * BLOK >= totaal:
            break

    print(f"  {len(rijen)} aanvragen opgehaald, "
          f"{sum(1 for r in rijen if r['deadline'])} met deadline")
    return rijen
