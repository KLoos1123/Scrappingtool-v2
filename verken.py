"""Verkenning regionale inhuurdesks (TIJDELIJK).

Doel: per portaal vaststellen op welk platform het draait (Striive,
Flextender, Nétive, InhuurDesk, ...) en of er een publieke
opdrachtenlijst is die we zonder login kunnen scrapen.
"""

import re
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

SITES = {
    "werkeninnoordhollandnoord": "https://www.werkeninnoordhollandnoord.nl/",
    "werkeninnoordoostbrabant": "https://www.werkeninnoordoostbrabant.nl/",
    "werkeninzuidoostbrabant": "https://www.werkeninzuidoostbrabant.nl/",
    "flexwestbrabant": "https://www.flexwestbrabant.nl/",
    "inhuurgelderland": "https://www.inhuurgelderland.nl/",
    "inhuurdesk-amstelveen": "https://inhuurdesk.amstelveen.nl/",
    "inhuurdesk-capelle": "https://inhuurdesk.capelleaandenijssel.nl/",
    "flexschiedam": "https://www.flexwerkschiedam.nl/",
}

MARKERS = [
    "striive", "flextender", "kbs_flx", "netive", "my-flexforce", "flexforce",
    "negometrix", "mercell", "ctmsolution", "inhuurdesk", "staffingdesk",
    "staffing management", "hireserve", "radancy", "carerix", "otys",
    "easycruit", "workday", "successfactors", "tangram", "connexys",
    "recruitnow", "jobsrepublic", "solviteers", "matchr",
]

ANKER_PATRONEN = ["/opdracht", "/vacature", "/aanvraag", "/inhuur",
                  "/assignment", "/job"]

API_HINT = re.compile(r"(/api/|/wp-json|graphql|\.json|search|opdracht|vacature|aanvraag)", re.I)
STATIC = re.compile(r"\.(png|jpe?g|gif|svg|webp|woff2?|ttf|css|ico|mp4)(\?|$)", re.I)


def verken(naam, url, ctx):
    print(f"\n{'='*70}\n### {naam}  ->  {url}\n{'='*70}")
    page = ctx.new_page()
    api_calls = []

    def on_response(resp):
        u = resp.url
        if STATIC.search(u):
            return
        ct = resp.headers.get("content-type", "")
        if "json" in ct or API_HINT.search(u):
            api_calls.append((resp.request.method, resp.status, ct.split(";")[0], u))

    page.on("response", on_response)

    try:
        page.goto(url, timeout=45000, wait_until="domcontentloaded")
        page.wait_for_timeout(5000)
    except Exception as e:
        print(f"  goto fout: {e}")
        page.close()
        return

    print(f"-- titel: {page.title()!r}")
    print(f"-- eind-url: {page.url}")

    html = page.content().lower()
    gevonden = [m for m in MARKERS if m in html]
    print(f"-- platform-markers: {gevonden or 'geen'}")

    hrefs = page.eval_on_selector_all(
        "a[href]", "els => els.map(e => e.getAttribute('href'))")
    for pat in ANKER_PATRONEN:
        matches = [h for h in hrefs if h and pat in h.lower()]
        if matches:
            uniek = list(dict.fromkeys(matches))
            print(f"-- ankers met '{pat}': {len(uniek)} (eerste 5)")
            for h in uniek[:5]:
                print(f"     {h}")

    gezien = set()
    print(f"-- {len(api_calls)} interessante netwerk-calls:")
    for method, status, ct, u in api_calls:
        key = u.split("?")[0]
        if key in gezien:
            continue
        gezien.add(key)
        print(f"   [{method} {status} {ct}] {u[:160]}")

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
