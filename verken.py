"""Ingelogde recon (TIJDELIJK). Leest response-bodies IN de handler zodat ze
niet uit de cache verdwijnen. Print geen wachtwoorden/tokens.
"""

import os
import json
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def _accept_cookies(page):
    for txt in ["Accepteer alles", "Akkoord", "Accept", "Alles accepteren",
                "Alles toestaan", "Accepteren"]:
        try:
            b = page.query_selector(f"button:has-text('{txt}')")
            if b:
                b.click()
                page.wait_for_timeout(800)
                return
        except Exception:
            pass


def _knip(s, n):
    return s if len(s) <= n else s[:n] + f"...<+{len(s)-n}>"


# ---------------------------------------------------------------- freelance
def freelance(ctx):
    print(f"\n{'='*70}\n### freelance.nl (ingelogd)\n{'='*70}")
    email = os.environ.get("FREELANCE_EMAIL")
    pw = os.environ.get("FREELANCE_WACHTWOORD")
    if not email or not pw:
        print("  secrets ontbreken"); return
    page = ctx.new_page()
    calls = []  # (post_data, body) meteen gelezen

    def handler(r):
        try:
            if "/graphql" in r.url and r.request.method == "POST":
                calls.append((r.request.post_data or "", r.text()))
        except Exception:
            pass

    page.on("response", handler)

    page.goto("https://mijn.freelance.nl/inloggen", timeout=60000, wait_until="domcontentloaded")
    _accept_cookies(page)
    page.wait_for_timeout(1500)
    try:
        page.fill("input[name='email']", email)
        page.fill("input[name='password']", pw)
        btn = page.query_selector("button[type='submit']") or page.query_selector("button:has-text('Inloggen')")
        btn.click()
    except Exception as e:
        print(f"  login-invoer fout: {e}")
    page.wait_for_timeout(6000)
    print(f"  na login: {page.url}")

    calls.clear()
    page.goto("https://mijn.freelance.nl/opdracht-vinden/zoeken?resultaten=36",
              timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(9000)

    print(f"  {len(calls)} graphql-calls op de zoekpagina")
    for pd, body in calls:
        low = (pd + body).lower()
        if ("assignment" in low or "opdracht" in low or "search" in low) and len(body) > 1500:
            try:
                qname = json.loads(pd).get("operationName") or json.loads(pd).get("query", "")[:60]
            except Exception:
                qname = pd[:80]
            print(f"\n  >>> operation={qname}")
            print(f"      QUERY: {_knip(pd, 700)}")
            print(f"      BODY:  {_knip(body, 2600)}")
    page.close()


# ---------------------------------------------------------------- stedin-vms
def stedinvms(ctx):
    print(f"\n{'='*70}\n### Stedin-VMS (Salesforce/Netive)\n{'='*70}")
    email = os.environ.get("STEDINVMS_EMAIL")
    pw = os.environ.get("STEDINVMS_WACHTWOORD")
    if not email or not pw:
        print("  secrets ontbreken"); return
    page = ctx.new_page()
    aura = []

    def handler(r):
        try:
            if "/aura" in r.url and r.request.method == "POST":
                aura.append((r.request.post_data or "", r.text()))
        except Exception:
            pass

    page.on("response", handler)

    page.goto("https://stedin-vms.my.site.com/vms/s/login", timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    try:
        page.fill("input[name='username']", email)
        page.fill("input[name='password']", pw)
        page.click("button:has-text('Login')")
    except Exception as e:
        print(f"  login-invoer fout: {e}")
    page.wait_for_timeout(9000)
    print(f"  na login: {page.url}")

    # probeer naar opdrachten/aanvragen te navigeren
    aura.clear()
    for sel in ["a:has-text('Opdrachten')", "a:has-text('Aanvragen')",
                "a:has-text('Assignments')", "a:has-text('Marktplaats')",
                "a:has-text('Jobs')", "a:has-text('Requests')"]:
        try:
            el = page.query_selector(sel)
            if el:
                print(f"  klik op {sel}")
                el.click()
                page.wait_for_timeout(7000)
                break
        except Exception:
            pass
    page.wait_for_timeout(4000)

    # dump nav-links zodat we de juiste pagina kennen
    try:
        links = page.eval_on_selector_all(
            "a[href]", "els => els.map(e => (e.textContent||'').trim()+' | '+e.getAttribute('href'))")
        print("  navigatielinks:")
        for l in links[:40]:
            if l.strip(" |"):
                print(f"    {l}")
    except Exception:
        pass

    print(f"\n  {len(aura)} aura-POSTs")
    for pd, body in aura:
        # zoek records met veldnamen als jRequest__c e.d.
        if len(body) > 2000 and ("__c" in body or '"records"' in body or "jRequest" in body):
            acties = [w for w in ["getItems", "getRecord", "jRequest", "jCandidateRequest",
                                  "Opdracht", "Assignment", "search", "getList", "ui-force"]
                      if w in pd or w in body]
            print(f"\n  >>> aura body={len(body)} acties~{acties}")
            print(f"      {_knip(body, 3000)}")
    page.close()


# ---------------------------------------------------------------- ret
def ret(ctx):
    print(f"\n{'='*70}\n### RET (portaal-link)\n{'='*70}")
    page = ctx.new_page()
    page.goto("https://werkenbijderet.nl/over-ons/inhuur", timeout=60000, wait_until="domcontentloaded")
    _accept_cookies(page)
    page.wait_for_timeout(3000)
    hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))")
    for h in dict.fromkeys(hrefs):
        if h and any(w in h.lower() for w in ["negometrix", "mercell", "s2c", "inhuur",
                     "portal", "opdracht", "tender", "vms"]):
            print(f"   [portaal?] {h}")
    page.close()


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="nl-NL")
        for fn in (freelance, stedinvms, ret):
            try:
                fn(ctx)
            except Exception as e:
                print(f"### {fn.__name__} MISLUKT: {e}")
        browser.close()


if __name__ == "__main__":
    main()
