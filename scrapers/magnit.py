"""Magnit (voorheen Brainnet) - supplier job requests achter de login.

Logt in op portal.magnitglobal.com met e-mail/wachtwoord (secrets
MAGNIT_EMAIL / MAGNIT_WACHTWOORD) en onderschept de retrievejobrequests-
response die de aanvragenpagina zelf ophaalt. Er worden geen tokens
geprint of opgeslagen.
"""

import os
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

    onderschept = {"body": None}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="nl-NL")
        page = ctx.new_page()

        def on_resp(resp):
            try:
                if "retrievejobrequests" in resp.url:
                    tekst = resp.text()
                    if '"jobRequests"' in tekst:
                        onderschept["body"] = tekst
            except Exception:
                pass

        page.on("response", on_resp)

        _login(page, email, wachtwoord)
        page.wait_for_timeout(6000)

        # forceer de aanvragenlijst (triggert retrievejobrequests)
        for sel in ["a:has-text('Aanvragen')", "text=AANVRAGEN",
                    "a:has-text('Naar alle aanvragen')"]:
            try:
                el = page.query_selector(sel)
                if el:
                    el.click()
                    break
            except Exception:
                continue
        page.wait_for_timeout(6000)

        # vangnet: opnieuw laden om de call te forceren
        if not onderschept["body"]:
            try:
                page.goto(START, timeout=60000, wait_until="domcontentloaded")
                page.wait_for_timeout(9000)
            except Exception:
                pass

        if not onderschept["body"]:
            try:
                page.screenshot(path="debug_magnit.png", full_page=True)
            except Exception:
                pass
        browser.close()

    if not onderschept["body"]:
        raise RuntimeError("retrievejobrequests niet onderschept na login")

    data = json.loads(onderschept["body"])
    jobs = ((data or {}).get("value") or {}).get("jobRequests") or []
    rijen = [_uit_jobrequest(j) for j in jobs if j.get("jobRequestId")]

    print(f"  {len(rijen)} aanvragen opgehaald")
    return rijen
