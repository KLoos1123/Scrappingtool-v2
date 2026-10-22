"""Flex West-Brabant - inhuuraanvragen van West-Brabantse gemeenten.

Publieke lijst op de homepage (article.job), server-side gerenderd op een
Salesforce-achtergrond. Per aanvraag: datum (h5), titel + /aanvragen/{id}-
link, organisatie (li.org) en een SRQ-aanvraagnummer. De sluitingsdatum
staat alleen op de detailpagina (h5 "Sluitingsdatum <strong>...</strong>").
"""

import re
from concurrent.futures import ThreadPoolExecutor
import requests
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

BRON = "flexwestbrabant"

BASE = "https://flexwestbrabant.nl"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

MAANDEN = {
    "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
    "juli": 7, "augustus": 8, "september": 9, "oktober": 10, "november": 11,
    "december": 12,
}


def _iso(tekst):
    """'20 juli 2026 06:00' -> '2026-07-20T06:00'."""
    if not tekst:
        return None
    m = re.search(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})(?:\s+(\d{1,2}):(\d{2}))?",
                  tekst.lower())
    if not m:
        return tekst
    dag, maand, jaar, uur, minuut = m.groups()
    mnd = MAANDEN.get(maand)
    if not mnd:
        return tekst
    datum = f"{jaar}-{mnd:02d}-{int(dag):02d}"
    if uur:
        datum += f"T{int(uur):02d}:{minuut}"
    return datum


def _uit_artikel(art):
    a = art.select_one("h2 a[href*='/aanvragen/']")
    if not a:
        return None
    sfid = a["href"].rstrip("/").rsplit("/", 1)[-1]

    org = art.select_one("ul.meta-data li.org")
    nummer = None
    for li in art.select("ul.meta-data li"):
        m = re.search(r"Aanvraagnummer:\s*(\S+)", li.get_text(strip=True))
        if m:
            nummer = m.group(1)
            break

    datum = art.select_one("header h5")

    return {
        "tender_id": sfid,
        "nummer": nummer,
        "titel": a.get_text(strip=True).rstrip(" →"),
        "organisatie": org.get_text(strip=True) if org else None,
        "status": "Open",
        "deadline": None,
        "publicatiedatum": _iso(datum.get_text(strip=True)) if datum else None,
        "locatie": "West-Brabant",
        "url": BASE + a["href"],
    }


def _deadline(url):
    """Sluitingsdatum van de detailpagina, of None."""
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
        r.raise_for_status()
    except Exception:
        return None
    for h5 in BeautifulSoup(r.text, "lxml").select("h5"):
        if h5.get_text(strip=True).lower().startswith("sluitingsdatum"):
            sterk = h5.find("strong")
            return _iso(sterk.get_text(strip=True)) if sterk else None
    return None


def haal_op():
    """Wordt aangeroepen door run.py. Geeft een lijst dicts terug."""
    rijen = []
    gezien = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="nl-NL")

        # homepage bevat de actuele lijst; /aanvragen als mogelijke volledige lijst
        for pad in ("/", "/aanvragen", "/aanvragen/"):
            try:
                r = ctx.request.get(BASE + pad, timeout=30000)
            except Exception:
                continue
            if not r.ok:
                continue
            for art in BeautifulSoup(r.text(), "lxml").select("article.job"):
                rij = _uit_artikel(art)
                if rij and rij["tender_id"] not in gezien:
                    gezien.add(rij["tender_id"])
                    rijen.append(rij)

        browser.close()

    # deadline van de detailpagina's, een paar tegelijk
    with ThreadPoolExecutor(max_workers=4) as pool:
        for rij, deadline in zip(rijen, pool.map(_deadline, [r["url"] for r in rijen])):
            rij["deadline"] = deadline

    print(f"  {len(rijen)} aanvragen gevonden, "
          f"{sum(1 for r in rijen if r['deadline'])} met deadline")
    return rijen
