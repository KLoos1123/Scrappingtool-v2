"""Stedin - werkenbij.stedin.net (Radancy-platform).

Geen login nodig. De zoekpagina toont 15 vacatures per pagina en pagineert
via een "Volgende"-link (href /vacatures-zoeken&p=N). We renderen de pagina
met Playwright, klikken door naar de volgende pagina tot die er niet meer is,
en parsen elke pagina met BeautifulSoup.
"""

from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

BRON = "stedin"

BASE = "https://werkenbij.stedin.net"
ZOEK = f"{BASE}/vacatures-zoeken"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

KAART = "a.job-list--link[data-job-id]"
VOLGENDE = "nav.pagination a.next:not(.disabled):not([aria-disabled='true'])"
MAX_PAGINA = 30  # veiligheidsgrens


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


def haal_op():
    """Wordt aangeroepen door run.py. Geeft een lijst dicts terug."""
    rijen = []
    gezien = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(user_agent=UA, locale="nl-NL").new_page()

        page.goto(ZOEK, timeout=60000, wait_until="domcontentloaded")

        for _ in range(MAX_PAGINA):
            try:
                page.wait_for_selector(KAART, timeout=15000)
            except Exception:
                break
            page.wait_for_timeout(500)

            soup = BeautifulSoup(page.content(), "lxml")
            nieuw = 0
            for a in soup.select(KAART):
                rij = _uit_kaart(a)
                if rij and rij["tender_id"] not in gezien:
                    gezien.add(rij["tender_id"])
                    rijen.append(rij)
                    nieuw += 1

            volgende = page.query_selector(VOLGENDE)
            if not volgende or nieuw == 0:
                break
            try:
                volgende.click()
                page.wait_for_load_state("domcontentloaded", timeout=30000)
                page.wait_for_timeout(1500)
            except Exception:
                break

        browser.close()

    print(f"  {len(rijen)} vacatures gevonden")
    return rijen
