"""Werken in Gelderland - inhuuropdrachten.

Publieke lijst op werkeningelderland.nl/inhuur/, server-side gerenderd
(WordPress), paginering via /inhuur/page/N/. Kaarten zijn
li.vacancies__item met detailregels (Reageren t/m, Plaatsingsdatum).

De lijst toont geen organisatie (alleen een logo zonder alt/title) en de
locatieregel is leeg. Die staan wel op de detailpagina: de omschrijving in
section.content__main, de organisatie als .about__title in de zijbalk met
daaronder het bezoekadres ("7201 DN Zutphen"). Die pagina's halen we
parallel op met requests; lukt dat niet, dan blijven de velden leeg
(locatie valt dan terug op "Gelderland").
"""

import re
from concurrent.futures import ThreadPoolExecutor

import requests
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

BRON = "gelderland"

BASE = "https://www.werkeningelderland.nl"
LIJST = f"{BASE}/inhuur/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

MAX_PAGINA = 40
WERKERS = 4  # parallelle detailpagina's
REGIO = "Gelderland"  # alle opdrachtgevers op dit portaal zitten in Gelderland

MAANDEN = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "augustus": 8, "september": 9, "oktober": 10, "november": 11,
    "december": 12,
    "january": 1, "february": 2, "march": 3, "may": 5, "june": 6, "july": 7,
    "august": 8, "october": 10,
}


def _iso(tekst):
    """'06 August 2026 09:00' / '20 juli 2026' -> ISO-string, anders origineel."""
    if not tekst:
        return None
    m = re.search(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})(?:\s+(\d{1,2}):(\d{2}))?", tekst)
    if not m:
        return tekst
    dag, maand, jaar, uur, minuut = m.groups()
    mnd = MAANDEN.get(maand.lower())
    if not mnd:
        return tekst
    datum = f"{jaar}-{mnd:02d}-{int(dag):02d}"
    if uur:
        datum += f"T{int(uur):02d}:{minuut}"
    return datum


def _detail(kaart, label):
    for li in kaart.select("li.vacancy__detail"):
        titel = li.select_one(".vacancy__detail__title")
        if titel and titel.get_text(strip=True).lower() == label:
            waarde = li.select_one(".vacancy__detail__value")
            return waarde.get_text(strip=True) if waarde else None
    return None


def _uit_item(li):
    a = li.find("a", href=True)
    if not a or "/opdracht/" not in a["href"]:
        return None
    url = a["href"]
    slug = url.rstrip("/").rsplit("/", 1)[-1]

    titel = li.select_one(".vacancy__title")
    locatie = li.select_one(".vacancy__location")
    org = li.select_one(".vacancy__sidebar img[title], .vacancy__sidebar img[alt]")

    return {
        "tender_id": slug,
        "nummer": None,
        "titel": titel.get_text(strip=True) if titel else None,
        "organisatie": (org.get("title") or org.get("alt")) if org else None,
        "status": "Open",
        "deadline": _iso(_detail(li, "reageren t/m")),
        "publicatiedatum": _iso(_detail(li, "plaatsingsdatum")),
        "locatie": (locatie.get_text(strip=True) or None) if locatie else None,
        "omschrijving": None,
        "url": url,
    }


def _plaats(soup):
    """Plaatsnaam uit het bezoekadres in de zijbalk ('7201 DN Zutphen')."""
    for li in soup.select(".about__details .about__detail"):
        m = re.match(r"\d{4}\s?[A-Z]{2}\s+(.+)", li.get_text(" ", strip=True))
        if m:
            return m.group(1).strip()
    return None


def _vul_detail(sessie, rij):
    """Haalt de detailpagina op en vult omschrijving, organisatie en locatie
    aan (fouten negeren we; locatie valt terug op de regio)."""
    try:
        r = sessie.get(rij["url"], timeout=15)
        if r.ok:
            soup = BeautifulSoup(r.text, "lxml")
            oms = soup.select_one(".single-vacancy__content .content__main")
            if oms:
                # standaardblok over de Wet DBA staat bovenaan elke opdracht en
                # zou de opgeslagen 4000 tekens grotendeels opeten
                for p in oms.find_all("p"):
                    if p.get_text(strip=True).startswith("Uitvoeringsvoorwaarde"):
                        p.decompose()
                rij["omschrijving"] = oms.get_text(" ", strip=True) or None
            org = soup.select_one(".about__title")
            if org and not rij["organisatie"]:
                rij["organisatie"] = org.get_text(strip=True) or None
            loc = soup.select_one(".single-vacancy__location")
            if not rij["locatie"]:
                rij["locatie"] = (loc.get_text(strip=True) if loc else None) or _plaats(soup)
    except Exception:
        pass
    if not rij["locatie"]:
        rij["locatie"] = REGIO


def haal_op():
    """Wordt aangeroepen door run.py. Geeft een lijst dicts terug."""
    rijen = []
    gezien = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="nl-NL")

        for pagina in range(1, MAX_PAGINA + 1):
            url = LIJST if pagina == 1 else f"{LIJST}page/{pagina}/"
            r = ctx.request.get(url, timeout=30000)
            if not r.ok:
                break

            items = BeautifulSoup(r.text(), "lxml").select("li.vacancies__item")
            nieuw = 0
            for li in items:
                rij = _uit_item(li)
                if rij and rij["tender_id"] not in gezien:
                    gezien.add(rij["tender_id"])
                    rijen.append(rij)
                    nieuw += 1
            if nieuw == 0:
                break

        browser.close()

    sessie = requests.Session()
    sessie.headers["User-Agent"] = UA
    with ThreadPoolExecutor(WERKERS) as pool:
        list(pool.map(lambda r: _vul_detail(sessie, r), rijen))

    oms = sum(1 for r in rijen if r["omschrijving"])
    print(f"  {len(rijen)} opdrachten gevonden, {oms} met omschrijving")
    return rijen
