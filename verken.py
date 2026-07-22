"""Ingelogde recon: freelance.nl (GraphQL), Stedin-VMS (Aura), RET-link (TIJDELIJK).

Legt per site de data-call + structuur vast. Print geen wachtwoorden/tokens.
"""

import os
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def _accept_cookies(page):
    for txt in ["Accepteer alles", "Akkoord", "Accept", "Alles accepteren"]:
        try:
            b = page.query_selector(f"button:has-text('{txt}')")
            if b:
                b.click()
                page.wait_for_timeout(1000)
                return
        except Exception:
            pass


# ---------------------------------------------------------------- freelance
def freelance(ctx):
    print(f"\n{'='*70}\n### freelance.nl (ingelogd)\n{'='*70}")
    email = os.environ.get("FREELANCE_EMAIL")
    pw = os.environ.get("FREELANCE_WACHTWOORD")
    if not email or not pw:
        print("  secrets ontbreken"); return
    page = ctx.new_page()
    calls = []
    page.on("response", lambda r: calls.append(r) if "/graphql" in r.url and r.request.method == "POST" else None)

    page.goto("https://mijn.freelance.nl/inloggen", timeout=60000, wait_until="domcontentloaded")
    _accept_cookies(page)
    page.wait_for_timeout(1500)
    page.fill("input[name='email']", email)
    page.fill("input[name='password']", pw)
    (page.query_selector("button[type='submit']") or page.query_selector("button:has-text('Inloggen')")).click()
    page.wait_for_timeout(6000)
    print(f"  na login: {page.url}")

    page.goto("https://mijn.freelance.nl/opdracht-vinden/zoeken?resultaten=36",
              timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(9000)

    print(f"  {len(calls)} graphql-calls")
    for r in calls[-6:]:
        pd = (r.request.post_data or "")[:400]
        try:
            body = r.text()
        except Exception as e:
            body = f"<{e}>"
        if "opdracht" in (pd + body).lower() or "assignment" in (pd + body).lower() or len(body) > 3000:
            print(f"\n  >>> POST /graphql")
            print(f"      QUERY: {pd}")
            print(f"      BODY({len(body)}): {body[:1800]}")
    page.close()


# ---------------------------------------------------------------- stedin-vms
def stedinvms(ctx):
    print(f"\n{'='*70}\n### Stedin-VMS (Salesforce)\n{'='*70}")
    email = os.environ.get("STEDINVMS_EMAIL")
    pw = os.environ.get("STEDINVMS_WACHTWOORD")
    if not email or not pw:
        print("  secrets ontbreken"); return
    page = ctx.new_page()
    aura = []
    page.on("response", lambda r: aura.append(r) if "/sfsites/aura" in r.url and r.request.method == "POST" else None)

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

    # navigeer naar opdrachten/aanvragen als er zo'n link is
    for sel in ["a:has-text('Opdrachten')", "a:has-text('Aanvragen')",
                "a:has-text('Marktplaats')", "a:has-text('Jobs')"]:
        try:
            el = page.query_selector(sel)
            if el:
                el.click(); page.wait_for_timeout(6000); break
        except Exception:
            pass
    page.wait_for_timeout(4000)

    print(f"  {len(aura)} aura-POSTs")
    for r in aura:
        try:
            body = r.text()
        except Exception:
            continue
        if len(body) > 2500 and ('"records"' in body or '"Id"' in body or 'apex' in r.request.url.lower() or 'getRecord' in body):
            pd = (r.request.post_data or "")
            # welke aura-actions
            acties = [w for w in ["getItems", "getRecord", "Opdracht", "Assignment", "JobRequest", "search", "getList"] if w in pd or w in body]
            print(f"\n  >>> aura-POST (acties~{acties}) body={len(body)}")
            print(f"      {body[:2200]}")
    page.close()


# ---------------------------------------------------------------- ret
def ret(ctx):
    print(f"\n{'='*70}\n### RET (portaal-link zoeken)\n{'='*70}")
    page = ctx.new_page()
    page.goto("https://werkenbijderet.nl/over-ons/inhuur", timeout=60000, wait_until="domcontentloaded")
    _accept_cookies(page)
    page.wait_for_timeout(3000)
    hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.getAttribute('href'))")
    extern = [h for h in hrefs if h and h.startswith("http")
              and not any(s in h for s in ["werkenbijderet", "facebook", "linkedin",
              "instagram", "youtube", "twitter", "cookie", "google"])]
    print(f"  {len(set(extern))} externe links:")
    for h in dict.fromkeys(extern):
        print(f"   {h}")
    # zoek specifiek naar portaal-woorden
    for h in dict.fromkeys(hrefs):
        if h and any(w in h.lower() for w in ["negometrix", "mercell", "inhuur", "portal", "opdracht", "tender", "vms"]):
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
