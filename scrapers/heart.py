"""Heart (Driessen Groep) - leveranciersportaal, vacatures.

Login via Azure AD B2C (driessenb2c.b2clogin.com, standaard MSAL-loginpagina:
#logonIdentifier / #password / #next), die na succesvol inloggen terugstuurt
naar mijn.haert.nl/supplier/Vacancies.

Vereist secrets HEART_EMAIL en HEART_WACHTWOORD.

LET OP: dit platform is (in tegenstelling tot stedin_vms/portofrotterdam/
staffingms, die alle drie dezelfde bekende Nétive-VMS-software draaien) een
eigen, onbekende applicatie. Alleen de inlogpagina kon zonder credentials
geverifieerd worden; de structuur van de Vacancies-pagina zelf is nog niet
gezien. Deze scraper probeert eerst een gewone HTML-<table> generiek uit te
lezen (koppen + celwaarden), met een val terug op kaart-achtige elementen.
Loop dit na de eerste echte run door met de debug-screenshot als die er is,
en pas de selectors in _lees_tabel/_lees_kaarten aan waar nodig.
"""

import os
import re
from playwright.sync_api import sync_playwright

BRON = "heart"

APP = "https://mijn.haert.nl"
VACATURES = f"{APP}/supplier/Vacancies"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def _login(page, email, wachtwoord):
    page.goto(VACATURES, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_selector("#logonIdentifier", timeout=30000)
    page.wait_for_timeout(1500)
    page.fill("#logonIdentifier", email)
    page.fill("#password", wachtwoord)
    page.click("#next")
    page.wait_for_timeout(6000)
    if "b2clogin.com" in page.url:
        raise RuntimeError("inloggen mislukt")


def _tekst(el):
    return (el.inner_text() or "").strip().replace("\n", " ") if el else None


def _lees_tabel(page):
    """Generieke <table>: koppen uit thead/eerste rij, waarden per td."""
    rijen = []
    tabel = page.query_selector("table")
    if not tabel:
        return rijen

    koppen = [_tekst(th) or f"kol{i}" for i, th in enumerate(tabel.query_selector_all("thead th"))]
    body_rijen = tabel.query_selector_all("tbody tr") or tabel.query_selector_all("tr")

    for tr in body_rijen:
        cellen = tr.query_selector_all("td")
        if not cellen:
            continue
        waarden = [_tekst(c) for c in cellen]
        if not any(waarden):
            continue
        link = tr.query_selector("a[href]")
        href = link.get_attribute("href") if link else None
        if href and href.startswith("/"):
            href = APP + href
        rij = {(koppen[i] if i < len(koppen) else f"kol{i}"): w for i, w in enumerate(waarden)}
        rij["_url"] = href
        rijen.append(rij)
    return rijen


def _lees_kaarten(page):
    """Val terug op kaart-achtige elementen als er geen <table> is."""
    rijen = []
    kaarten = page.query_selector_all("[class*='vacan' i], [class*='vacature' i], li, .card")
    for k in kaarten:
        link = k.query_selector("a[href]")
        titel = _tekst(link) or _tekst(k)
        if not titel or len(titel) > 200:
            continue
        href = link.get_attribute("href") if link else None
        if href and href.startswith("/"):
            href = APP + href
        rijen.append({"titel": titel, "_url": href})
    return rijen


def _norm(rij):
    def pak(*namen):
        for n in namen:
            for k, v in rij.items():
                if n.lower() in k.lower() and v:
                    return v
        return None

    titel = pak("Functie", "Titel", "Vacature") or rij.get("titel")
    nummer = pak("Nummer", "Referentie", "Kenmerk")
    url = rij.get("_url") or VACATURES
    tid = nummer or (re.sub(r"^https?://[^/]+", "", url) if url else titel)

    return {
        "tender_id": tid,
        "nummer": nummer,
        "titel": titel,
        "organisatie": pak("Opdrachtgever", "Klant", "Organisatie") or "Heart",
        "status": pak("Status") or "Open",
        "deadline": pak("Sluitingsdatum", "Reageren", "Deadline"),
        "publicatiedatum": pak("Publicatiedatum", "Geplaatst"),
        "locatie": pak("Locatie", "Standplaats"),
        "url": url,
    }


def haal_op():
    """Wordt aangeroepen door run.py. Geeft een lijst dicts terug."""
    email = os.environ.get("HEART_EMAIL")
    wachtwoord = os.environ.get("HEART_WACHTWOORD")
    if not email or not wachtwoord:
        print("  HEART_EMAIL/WACHTWOORD ontbreekt; overslaan")
        return []

    rijen = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="nl-NL")
        page = ctx.new_page()
        try:
            ingelogd = False
            for poging in range(2):
                try:
                    _login(page, email, wachtwoord)
                    ingelogd = True
                    break
                except Exception as e:
                    print(f"  login-poging {poging + 1} mislukt ({type(e).__name__})")
                    page.wait_for_timeout(4000)
            if not ingelogd:
                print("  inloggen niet gelukt; bron overgeslagen (geen data)")
                return []

            if VACATURES not in page.url:
                page.goto(VACATURES, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(6000)

            ruw = _lees_tabel(page)
            if not ruw:
                ruw = _lees_kaarten(page)
            print(f"  {len(ruw)} vacatures gevonden")
            rijen = [_norm(r) for r in ruw if r.get("titel") or r.get("_url")]
        except Exception:
            try:
                page.screenshot(path="debug_heart.png", full_page=True)
            except Exception:
                pass
            raise
        finally:
            browser.close()

    if not rijen:
        print("  (geen vacatures gevonden voor dit account)")
    return rijen
