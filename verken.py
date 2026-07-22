"""Login-mechanisme-recon voor RET, Stedin-VMS en freelance.nl (TIJDELIJK).

Navigeert (zonder in te loggen) naar elke inlogpagina en dumpt: invoervelden,
knoppen, platform-markers (Salesforce/Aura, Striive, Flextender, ...) en
netwerk-calls. Print geen wachtwoorden.
"""

from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

SITES = {
    "ret": "https://werkenbijderet.nl/over-ons/inhuur",
    "stedinvms": "https://stedin-vms.my.site.com/vms/s",
    "freelance": "https://mijn.freelance.nl/opdracht-vinden/zoeken?resultaten=36",
}

MARKERS = ["aura", "lightning", "salesforce", "sfdc", "forcedotcom", "visualforce",
           "striive", "flextender", "kbs_flx", "negometrix", "mercell", "netive",
           "inhuurdesk", "wp-json", "wp-content", "__next_data__", "__nuxt__",
           "b2clogin", "auth0", "okta", "msal", "cognito", "keycloak"]

import re
API_HINT = re.compile(r"(/api/|/aura|/webruntime|/services/|/graphql|\.json|opdracht|vacature|aanvra|search|login|token)", re.I)
STATIC = re.compile(r"\.(png|jpe?g|gif|svg|webp|woff2?|ttf|css|ico|mp4)(\?|$)", re.I)


def verken(naam, url, ctx):
    print(f"\n{'='*70}\n### {naam}  ->  {url}\n{'='*70}")
    page = ctx.new_page()
    calls = []

    def on_resp(resp):
        u = resp.url
        if STATIC.search(u) or "google" in u or "cookiefirst" in u:
            return
        ct = resp.headers.get("content-type", "")
        if "json" in ct or API_HINT.search(u):
            calls.append((resp.request.method, resp.status, ct.split(";")[0], u))

    page.on("response", on_resp)
    try:
        page.goto(url, timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(6000)
    except Exception as e:
        print(f"  goto fout: {e}")
        page.close()
        return

    print(f"-- titel: {page.title()!r}")
    print(f"-- eind-url: {page.url}")

    html = page.content().lower()
    gevonden = [m for m in MARKERS if m in html]
    print(f"-- platform-markers: {gevonden or 'geen'}")

    velden = page.eval_on_selector_all(
        "input, button, a[role=button]",
        """els => els.slice(0,30).map(e => ({t:e.tagName, type:e.getAttribute('type'),
           name:e.getAttribute('name'), id:e.id,
           ph:e.getAttribute('placeholder'), txt:(e.innerText||'').trim().slice(0,30)}))""")
    print("-- interactieve elementen:")
    for v in velden:
        if v.get("type") or v.get("name") or v.get("ph") or v.get("txt"):
            print(f"   {v}")

    gezien = set()
    print(f"-- {len(calls)} netwerk-calls (uniek):")
    for m, s, ct, u in calls:
        k = u.split("?")[0]
        if k in gezien:
            continue
        gezien.add(k)
        print(f"   [{m} {s} {ct}] {u[:150]}")
    page.close()


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="nl-NL")
        for naam, url in SITES.items():
            try:
                verken(naam, url, ctx)
            except Exception as e:
                print(f"\n### {naam} MISLUKT: {e}")
        browser.close()


if __name__ == "__main__":
    main()
