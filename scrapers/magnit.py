"""Magnit (voorheen Brainnet) - supplier job requests achter de login.

Logt in op portal.magnitglobal.com met e-mail/wachtwoord (secrets
MAGNIT_EMAIL / MAGNIT_WACHTWOORD), leest de MSAL-accesstoken en de actieve
member uit localStorage, en haalt de aanvragen op via de retrievejobrequests-
API. Er worden geen tokens geprint of opgeslagen.
"""

import os
from playwright.sync_api import sync_playwright

BRON = "magnit"

PORTAL = "https://portal.magnitglobal.com"
START = f"{PORTAL}/supplier/jobrequests/new"
API = ("https://gtw004vw5s5j74c2hio.azurewebsites.net"
       "/web/v1/recruitment/retrievejobrequests")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

BLOK = 100
MAX_PAGINA = 20


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
    # terug op het portaal na de B2C-redirect
    try:
        page.wait_for_url("**portal.magnitglobal.com/supplier/**", timeout=40000)
    except Exception:
        pass


def _token_en_member(page):
    return page.evaluate("""() => {
        let token = null, fallback = null, member = null;
        for (let i = 0; i < localStorage.length; i++) {
            const k = localStorage.key(i);
            if (k.includes('accesstoken')) {
                try {
                    const o = JSON.parse(localStorage.getItem(k));
                    if (o && o.secret) {
                        if (k.includes('access_api') ||
                            (o.target && String(o.target).includes('access_api'))) {
                            token = o.secret;
                        } else {
                            fallback = o.secret;
                        }
                    }
                } catch (e) {}
            }
            if (k === 'activemember') {
                const v = localStorage.getItem(k);
                try { const o = JSON.parse(v); member = o.id || o.memberId || o.value || v; }
                catch (e) { member = v; }
            }
        }
        return { token: token || fallback, member };
    }""")


def _wacht_op_token(page, seconden=40):
    """MSAL schrijft de token async na de redirect; poll tot hij er is."""
    for _ in range(seconden // 2):
        creds = _token_en_member(page)
        if creds.get("token"):
            return creds
        page.wait_for_timeout(2000)
    return _token_en_member(page)


def _uit_jobrequest(j):
    jid = j.get("jobRequestId")
    return {
        "tender_id": str(jid),
        "nummer": j.get("jobRequestNumber") or j.get("requestNumber") or j.get("number"),
        "titel": j.get("position"),
        "organisatie": j.get("customerName") or j.get("customerTeamExternalName") or "Magnit",
        "status": "Open",
        "deadline": (j.get("closingDate") or j.get("deadline")
                     or j.get("responseDeadline") or j.get("endDate")),
        "publicatiedatum": (j.get("publicationDate") or j.get("publishedDate")
                            or j.get("createdDate") or j.get("startPublicationDate")),
        "locatie": (j.get("location") or j.get("workLocation") or j.get("city")),
        "url": f"{PORTAL}/supplier/jobrequests/{jid}",
    }


def haal_op():
    """Wordt aangeroepen door run.py. Geeft een lijst dicts terug."""
    email = os.environ.get("MAGNIT_EMAIL")
    wachtwoord = os.environ.get("MAGNIT_WACHTWOORD")
    if not email or not wachtwoord:
        raise RuntimeError("MAGNIT_EMAIL of MAGNIT_WACHTWOORD ontbreekt")

    rijen = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="nl-NL")
        page = ctx.new_page()

        _login(page, email, wachtwoord)
        creds = _wacht_op_token(page)
        if not creds.get("token"):
            try:
                page.screenshot(path="debug_magnit_login.png", full_page=True)
            except Exception:
                pass
            browser.close()
            raise RuntimeError("Geen accesstoken gevonden na login")
        print(f"  ingelogd (member: {creds.get('member')})")

        headers = {
            "authorization": f"Bearer {creds['token']}",
            "content-type": "application/json",
            "origin": PORTAL,
            "x-language-locale": "nl",
        }
        if creds.get("member"):
            headers["x-active-member"] = creds["member"]

        eerste = True
        for categorie in ("JobRequestNew",):
            pagina = 0
            while pagina < MAX_PAGINA:
                payload = {"attachableCriteria": {
                    "currentCategory": categorie,
                    "orderDescriptors": [],
                    "searchValue": "",
                    "filters": {},
                    "paginationArgs": {"pageSize": BLOK, "pageNumber": pagina},
                }}
                r = ctx.request.post(API, headers=headers, data=payload, timeout=45000)
                if not r.ok:
                    print(f"    {categorie} p{pagina}: status {r.status}")
                    break
                blok = ((r.json() or {}).get("value") or {}).get("jobRequests") or []
                if eerste and blok:
                    print(f"    velden: {list(blok[0].keys())}")
                    eerste = False
                if not blok:
                    break
                rijen.extend(_uit_jobrequest(j) for j in blok if j.get("jobRequestId"))
                if len(blok) < BLOK:
                    break
                pagina += 1

        browser.close()

    print(f"  {len(rijen)} aanvragen opgehaald")
    return rijen
