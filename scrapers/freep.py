"""Freep - verzamelplatform voor interim/freelance opdrachten bij de overheid.

Publieke JSON-API, geen login nodig. De site (Nuxt) haalt de lijst op via
GET api.freep.nl/v1/assignments, dat in één keer alle openstaande opdrachten
teruggeeft (zonder paginering), maar zonder sluitingsdatum en omschrijving.
Die staan in de detail-endpoint api.freep.nl/v1/assignment/<slug>/ (zelfde
call als de opdrachtpagina doet), samen met plaats, startdatum en tarief.

Freep bundelt opdrachten uit allerlei achterliggende inhuurportalen (Flex West
Brabant, Inhuurdesk, Striive, Yacht, ...); overlap met andere bronnen is dus
te verwachten.
"""

from concurrent.futures import ThreadPoolExecutor

import requests
from bs4 import BeautifulSoup

BRON = "freep"

APP = "https://www.freep.nl"
API = "https://api.freep.nl/v1"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

WERKERS = 4  # parallelle detailverzoeken


def _getal(waarde):
    """Tarief komt als tekst ("82"); 0 of leeg betekent: niet opgegeven."""
    try:
        getal = float(waarde)
    except (TypeError, ValueError):
        return None
    if getal <= 0:
        return None
    return int(getal) if getal.is_integer() else getal


def _oms(html):
    if not html:
        return None
    tekst = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
    return tekst or None


def _uit_opdracht(a):
    slug = a.get("slug")
    rij = {
        "tender_id": str(a.get("id")),
        "nummer": None,
        "titel": a.get("title"),
        "organisatie": a.get("company_name"),
        "status": "Open",
        "deadline": None,
        "publicatiedatum": a.get("created_date"),
        "locatie": a.get("location_province"),
        "url": f"{APP}/opdracht/{slug}" if slug else f"{APP}/opdrachten",
    }
    if a.get("hours"):
        rij["uren_per_week"] = str(a["hours"])
    tarief = _getal(a.get("rate_max"))
    if tarief:
        rij["tarief_max"] = tarief
    return rij, slug


def _vul_detail(sessie, rij, slug):
    """Vult deadline, plaats, status, omschrijving en minimumtarief aan uit de
    detail-endpoint. Fouten negeren we: de rij uit de lijst blijft dan staan."""
    try:
        r = sessie.get(f"{API}/assignment/{slug}/", timeout=20)
        if not r.ok:
            return
        d = r.json()
    except (requests.RequestException, ValueError):
        return

    rij["deadline"] = d.get("closing_date")
    if d.get("status"):
        rij["status"] = d["status"].capitalize()
    if d.get("location_name"):
        # "Amersfoort (Utrecht)": plaats is preciezer, provincie als context
        prov = d.get("location_province")
        rij["locatie"] = f"{d['location_name']} ({prov})" if prov else d["location_name"]
    rij["omschrijving"] = _oms(d.get("content"))
    tarief_min = _getal(d.get("rate_min"))
    if tarief_min:
        rij["tarief_min"] = tarief_min


def haal_op():
    """Wordt aangeroepen door run.py. Geeft een lijst dicts terug."""
    sessie = requests.Session()
    sessie.headers.update({"user-agent": UA, "accept": "application/json"})

    r = sessie.get(f"{API}/assignments", timeout=30)
    r.raise_for_status()
    lijst = r.json()
    if isinstance(lijst, dict):  # mocht de API ooit gaan pagineren
        lijst = lijst.get("results") or []

    paren = [_uit_opdracht(a) for a in lijst if a.get("id")]
    rijen = [rij for rij, _ in paren]
    print(f"  {len(rijen)} opdrachten in de lijst")

    with ThreadPoolExecutor(WERKERS) as pool:
        list(pool.map(lambda p: _vul_detail(sessie, *p), [p for p in paren if p[1]]))

    met = sum(1 for r in rijen if r.get("deadline"))
    print(f"  {len(rijen)} opdrachten opgehaald, {met} met deadline")
    return rijen
