"""Striive Supplier - job requests.

Login via Auth0 (auth.striive.com); de app wisselt dit in voor sessiecookies
op supplier.striive.com. Die cookies hergebruiken we voor gewone
requests-calls naar de API, in plaats van de hele (virtueel gescrollde)
lijst via Playwright te scrapen.

De inlogpagina toont een OneTrust-cookiebanner (niet aanwezig toen deze
scraper voor het eerst werkte) die we eerst wegklikken voor de zekerheid.

We controleren niet meer op een specifieke cookie-naam ("SESSION"): een
debug-screenshot liet zien dat de login gewoon slaagt (volledig
gerenderd, ingelogd dashboard) terwijl striive.com de sessiecookie
kennelijk niet meer zo noemt. De API-call hieronder gebruikt toch alle
cookies van het domein, dus een harde naam-check was overbodig en gaf
een vals-negatieve fout; een echte auth-fout komt nu naar boven via de
HTTP-statuscode van de job-requests-call zelf.
"""

import os
import requests
from playwright.sync_api import sync_playwright

BRON = "striive"

APP = "https://supplier.striive.com"
API = f"{APP}/api/v2/job-requests"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"


# ---------------------------------------------------------------- login

def _accept_cookies(page):
    for txt in ["Alle cookies accepteren", "Alles accepteren", "Accepteren"]:
        try:
            b = page.query_selector(f"button:has-text('{txt}')")
            if b and b.is_visible():
                b.click()
                page.wait_for_timeout(600)
                return
        except Exception:
            pass


def _sessie_cookies():
    email = os.environ.get("STRIIVE_EMAIL")
    wachtwoord = os.environ.get("STRIIVE_WACHTWOORD")
    if not email or not wachtwoord:
        raise RuntimeError("STRIIVE_EMAIL of STRIIVE_WACHTWOORD ontbreekt")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        page.goto(f"{APP}/dashboard", timeout=60000)
        page.wait_for_selector("#username", timeout=30000)
        _accept_cookies(page)
        page.fill("#username", email)
        page.fill("#password", wachtwoord)
        page.click("button[type='submit']")

        try:
            page.wait_for_url(f"{APP}/**", timeout=30000)
        except Exception:
            pass
        page.wait_for_timeout(5000)

        cookies = {
            c["name"]: c["value"]
            for c in context.cookies()
            if "striive.com" in c["domain"]
        }

        if not cookies:
            try:
                page.screenshot(path="debug_striive_login.png", full_page=True)
            except Exception:
                pass

        browser.close()

    if not cookies:
        raise RuntimeError("Geen cookies ontvangen na login, zie debug_striive_login.png")

    return cookies


# ---------------------------------------------------------------- ophalen

def _job_requests(cookies, blok=1000):
    """Haalt alle job requests op, gepagineerd."""
    sessie = requests.Session()
    sessie.cookies.update(cookies)
    headers = {"user-agent": UA, "accept": "application/json"}

    alles = []
    pagina_nr = 0

    while True:
        r = sessie.get(
            API,
            params={
                "page": pagina_nr,
                "size": blok,
                "maxRadius": 50,
                "sortBy": "",
                "sortOrder": "ASCENDING",
                "clientNames": "",
                "professionalTypes": "",
                "remoteAllowed": "",
                "locations": "",
                "skills": "",
            },
            headers=headers,
            timeout=30,
        )
        r.raise_for_status()

        pagina = r.json()
        if not pagina:
            break

        alles.extend(pagina)
        if len(pagina) < blok:
            break
        pagina_nr += 1

    return alles


# ---------------------------------------------------------------- normaliseren

def _uit_job(j):
    jid = j.get("id")
    client = j.get("client") or {}
    return {
        "tender_id": str(jid),
        "nummer": j.get("referenceCode"),
        "titel": j.get("title"),
        "organisatie": client.get("name"),
        "status": j.get("state"),
        "deadline": j.get("closingDateOffer"),
        "publicatiedatum": j.get("publishedAt"),
        "locatie": j.get("locationName"),
        "url": f"{APP}/inbox/all/{jid}",
    }


# ---------------------------------------------------------------- publiek

def haal_op():
    """Wordt aangeroepen door run.py. Geeft een lijst dicts terug."""
    cookies = _sessie_cookies()
    print("  ingelogd")

    jobs = _job_requests(cookies)
    print(f"  {len(jobs)} opdrachten gevonden")

    return [_uit_job(j) for j in jobs]
