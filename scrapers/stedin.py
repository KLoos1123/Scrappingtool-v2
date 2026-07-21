"""Stedin - werkenbij.stedin.net (Radancy-platform).

Geen login nodig. De zoekpagina toont de eerste ~15 vacatures en laadt de
rest bij via AJAX (de ?page-parameter wordt genegeerd). We renderen de
pagina daarom met Playwright en scrollen/klikken tot het aantal vacatures
niet meer groeit, en parsen dan de DOM met BeautifulSoup.
"""

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

BRON = "stedin"

BASE = "https://werkenbij.stedin.net"
ZOEK = f"{BASE}/vacatures-zoeken"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

KAART = "a.job-list--link[data-job-id]"
MEER_KNOP = (
    "button.load-more, a.load-more, [class*='load-more'], "
    "button[class*='more'], a[class*='pagination-next'], "
    "a[rel='next'], .pagination-load-more a"
)
MAX_RONDES = 40


def _tekst(el):
    return el.get_text(strip=True) if el else None


def _uit_kaart(a):
    href = a.get("href")
    jid = a.get("data-job-id")
    if not jid:
        return None

    return {
        "tender_id": str(jid),
        "nummer": None,
        "titel": _tekst(a.find("h3")),
        "organisatie": "Stedin",
        "status": "Open",
        "deadline": None,
        "publicatiedatum": None,
        "locatie": _tekst(a.find("span", class_="job-location")),
        "categorie": _tekst(a.find("span", class_="category")),
        "url": BASE + href if href else None,
    }


def _laad_alles(page):
    """Scrollt en klikt tot het aantal vacaturekaarten stabiel blijft."""
    vorig = -1
    stabiel = 0
    for _ in range(MAX_RONDES):
        aantal = page.locator(KAART).count()
        if aantal == vorig:
            stabiel += 1
            if stabiel >= 2:
                break
        else:
            stabiel = 0
        vorig = aantal

        # probeer een "meer laden"-knop
        try:
            knop = page.locator(MEER_KNOP).first
            if knop.is_visible(timeout=500):
                knop.click(timeout=2000)
        except Exception:
            pass

        page.mouse.wheel(0, 12000)
        page.wait_for_timeout(1500)


def haal_op():
    """Wordt aangeroepen door run.py. Geeft een lijst dicts terug."""
    rijen = []
    gezien = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(user_agent=UA, locale="nl-NL").new_page()

        page.goto(ZOEK, timeout=60000, wait_until="networkidle")
        page.wait_for_timeout(2000)
        _laad_alles(page)

        soup = BeautifulSoup(page.content(), "lxml")
        browser.close()

    for a in soup.select(KAART):
        rij = _uit_kaart(a)
        if rij and rij["tender_id"] not in gezien:
            gezien.add(rij["tender_id"])
            rijen.append(rij)

    print(f"  {len(rijen)} vacatures gevonden")
    return rijen
