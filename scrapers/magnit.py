"""Magnit (voorheen Brainnet) - supplier job requests achter de login.

Logt in op portal.magnitglobal.com met e-mail/wachtwoord (secrets
MAGNIT_EMAIL / MAGNIT_WACHTWOORD) en probeert eerst de retrievejobrequests-
response te onderscheppen die de aanvragenpagina zelf ophaalt (rijkste
data: klantnaam, deadline, uren). Er worden geen tokens geprint of
opgeslagen.

Die onderschepping is inmiddels niet meer betrouwbaar (het interne
verzoek heet kennelijk anders of laadt anders dan toen dit geschreven
is), terwijl de "Aanvragen"-lijst zelf gewoon gerenderd wordt (een
custom lijst-component, geen <table>). Daarom valt deze scraper terug op
het uitlezen van de platte, zichtbare tekst van de pagina als de
onderschepping niks oplevert: elke rij begint met een aanvraagnummer
("260928-MSB-001"), gevolgd door de functietitel, dan een startdatum
(of "Z.S.M.") en locatie, en tot slot de deadline (+ tijd). Door op die
twee datum/"Z.S.M."-markers te ankeren blijft dit werken ongeacht welke
HTML-tags/classes eronder zitten.
"""

import os
import re
import json
from playwright.sync_api import sync_playwright

BRON = "magnit"

PORTAL = "https://portal.magnitglobal.com"
START = f"{PORTAL}/supplier/jobrequests/new"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def _login(page, email, wachtwoord):
    page.goto(START, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_selector("input[type='password']", timeout=30000)
    page.wait_for_timeout(2500)
    veld = (page.query_selector("input[type='email']")
            or page.query_selector("input[placeholder*='mail' i]")
            or page.query_selector("input[type='text']"))
    veld.fill(email)
    page.query_selector("input[type='password']").fill(wachtwoord)
    (page.query_selector("button:has-text('Inloggen')")
     or page.query_selector("button[type='submit']")).click()
    try:
        page.wait_for_url("**portal.magnitglobal.com/supplier/**", timeout=40000)
    except Exception:
        pass


# ---------------------------------------------------------------- val terug: platte tekst

NUMMER_RE = re.compile(r"^\d{6}-[A-Za-z]+-\d+$")
MARKER_RE = re.compile(r"^(\d{1,2}\s+[A-Za-z]+\s+\d{4}|Z\.S\.M\.)$", re.I)
TIJD_RE = re.compile(r"^\d{1,2}:\d{2}\s*uur$", re.I)


def _lees_lijst(page):
    """Leest de Aanvragen-lijst uit de platte, zichtbare tekst van de pagina.

    Elke rij begint met een aanvraagnummer, gevolgd door: functietitel,
    startdatum (of "Z.S.M."), locatie, deadline(datum), deadline(tijd).
    We ankeren op het aanvraagnummer en de twee datum/"Z.S.M."-markers in
    plaats van op specifieke HTML-tags of classes.
    """
    tekst = page.inner_text("body")
    regels = [l.strip() for l in tekst.split("\n") if l.strip()]

    posities = [i for i, l in enumerate(regels) if NUMMER_RE.match(l)]
    rijen = []
    for pos, i in enumerate(posities):
        einde = posities[pos + 1] if pos + 1 < len(posities) else len(regels)
        blok = regels[i + 1:einde]

        markers = [j for j, l in enumerate(blok) if MARKER_RE.match(l)]
        if len(markers) < 2:
            continue
        m1, m2 = markers[0], markers[1]

        titel = " ".join(blok[:m1]).strip()
        locatie = " ".join(blok[m1 + 1:m2]).strip() or None
        deadline = blok[m2]
        if m2 + 1 < len(blok) and TIJD_RE.match(blok[m2 + 1]):
            deadline = f"{deadline} {blok[m2 + 1]}"

        rijen.append({
            "nummer": regels[i],
            "titel": titel or regels[i],
            "locatie": locatie,
            "deadline": deadline,
        })
    return rijen


def _uit_rij(rij):
    return {
        "tender_id": rij["nummer"],
        "nummer": rij["nummer"],
        "titel": rij["titel"],
        "organisatie": "Magnit",
        "status": "Open",
        "deadline": rij.get("deadline"),
        "publicatiedatum": None,
        "locatie": rij.get("locatie"),
        "url": START,
    }


# ---------------------------------------------------------------- normaliseren

def _uit_jobrequest(j):
    jid = j.get("jobRequestId")
    return {
        "tender_id": str(jid),
        "nummer": j.get("jobRequestNumber"),
        "titel": j.get("position") or j.get("jobRequestName"),
        "organisatie": (j.get("clientName") or j.get("companyName")
                        or j.get("customerTeamExternalName") or "Magnit"),
        "status": "Open",
        "deadline": j.get("submissionDeadLine"),
        "publicatiedatum": None,   # geen publicatiedatum in de API
        "locatie": j.get("location"),
        "start": j.get("periodStart"),
        "uren_per_week": j.get("hoursPerWeek"),
        "url": f"{PORTAL}/supplier/jobrequests/{jid}",
    }


def haal_op():
    """Wordt aangeroepen door run.py. Geeft een lijst dicts terug."""
    email = os.environ.get("MAGNIT_EMAIL")
    wachtwoord = os.environ.get("MAGNIT_WACHTWOORD")
    if not email or not wachtwoord:
        raise RuntimeError("MAGNIT_EMAIL of MAGNIT_WACHTWOORD ontbreekt")

    body = None

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="nl-NL")
        page = ctx.new_page()

        _login(page, email, wachtwoord)
        page.wait_for_timeout(5000)

        # Wacht deterministisch op de retrievejobrequests-response terwijl we
        # de pagina herladen (dat vuurt de call opnieuw). Met retries, want de
        # eerste laadpoging kan nog voor de MSAL-token uit zijn.
        for poging in range(4):
            try:
                with page.expect_response(
                    lambda r: "retrievejobrequests" in r.url
                    and r.request.method == "POST",
                    timeout=30000,
                ) as resp_info:
                    # navigeer naar de aanvragen-deeplink; dat vuurt de call
                    # (na login landt de app soms op home, waar hij niet vuurt)
                    page.goto(START, wait_until="domcontentloaded", timeout=60000)
                tekst = resp_info.value.text()
                if '"jobRequests"' in tekst:
                    body = tekst
                    break
            except Exception:
                pass
            page.wait_for_timeout(4000)

        rijen = None
        if not body:
            # onderschepping mislukt; de lijst staat er desondanks vaak gewoon,
            # dus eerst de zichtbare tekst proberen voor we opgeven.
            try:
                ruw = _lees_lijst(page)
            except Exception:
                ruw = []
            if ruw:
                rijen = [_uit_rij(r) for r in ruw]
                print(f"  retrievejobrequests niet onderschept; {len(rijen)} rijen uit zichtbare lijst")
            else:
                try:
                    page.screenshot(path="debug_magnit.png", full_page=True)
                except Exception:
                    pass
        browser.close()

    if rijen is not None:
        print(f"  {len(rijen)} aanvragen opgehaald")
        return rijen

    if not body:
        raise RuntimeError("retrievejobrequests niet onderschept na login, geen lijst gevonden")

    data = json.loads(body)
    jobs = ((data or {}).get("value") or {}).get("jobRequests") or []
    rijen = [_uit_jobrequest(j) for j in jobs if j.get("jobRequestId")]

    print(f"  {len(rijen)} aanvragen opgehaald")
    return rijen
