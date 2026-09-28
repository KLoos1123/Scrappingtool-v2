"""Hero Interim Professionals - opdrachtenlijst.

Publieke pagina, geen login nodig. De site is verhuisd van
interimprofessionals.hero.eu (WordPress/JetEngine) naar hero.eu (Next.js,
server-side gerenderd) -- oude selectors matchten niets meer, vandaar de
herschrijving. Alle opdrachten staan nog steeds op één pagina, geen
paginering aangetroffen.
"""

import re
import requests
from bs4 import BeautifulSoup

BRON = "hero"

APP = "https://hero.eu"
URL = f"{APP}/interim-opdrachten"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

MAANDEN = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "augustus": 8, "september": 9, "oktober": 10, "november": 11,
    "december": 12,
}

# gesloten set aan waarden voor vakgebied/werkvorm, zodat we die kunnen
# onderscheiden van de locatie (het aantal spans per opdracht varieert)
WERKVORMEN = re.compile(r"^(hybride|op locatie|thuis|remote)", re.I)


def _datum(tekst):
    m = re.match(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", (tekst or "").strip().lower())
    if not m:
        return None
    dag, maand, jaar = m.groups()
    mnd = MAANDEN.get(maand)
    return f"{jaar}-{mnd:02d}-{int(dag):02d}" if mnd else None


def _slug_id(url):
    return url.rstrip("/").rsplit("/", 1)[-1]


def _uit_item(li):
    link = li.select_one("h5 a[href]")
    if not link:
        return None

    href = link["href"]
    url = href if href.startswith("http") else APP + href

    # elke span (behalve de laatste) bevat een geneste "·"-scheidingsteken
    delen = [s.get_text(strip=True).rstrip("·").strip()
             for s in li.select(".hero-caption > span.whitespace-nowrap")]
    publicatiedatum = _datum(delen[0]) if delen else None

    locatie = None
    for deel in delen[1:]:
        if not deel or "uur/week" in deel.lower() or WERKVORMEN.match(deel):
            continue
        if deel in ("ICT & Data", "Project & Programma", "Overig", "Marketing & Communicatie"):
            continue
        locatie = deel
        break

    return {
        "tender_id": _slug_id(url),
        "nummer": None,
        "titel": link.get_text(strip=True),
        "organisatie": None,
        "status": "Open",
        "deadline": None,
        "publicatiedatum": publicatiedatum,
        "locatie": locatie,
        "url": url,
    }


def haal_op():
    """Wordt aangeroepen door run.py. Geeft een lijst dicts terug."""
    r = requests.get(URL, headers={"User-Agent": UA}, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    items = soup.select("h5 a[href^='/interim-opdrachten/']")
    items = [a.find_parent("li") or a for a in items]
    print(f"  {len(items)} opdrachten gevonden")

    return [rij for rij in (_uit_item(i) for i in items) if rij]
