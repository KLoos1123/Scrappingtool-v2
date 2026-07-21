"""Eenmalig verkenningsscript (TIJDELIJK).

Doel: de echte structuur van de nieuw toe te voegen sites achterhalen, omdat
de ontwikkelomgeving deze sites niet kan bereiken. Draait in GitHub Actions.

Voor elke site:
  - laadt de lijstpagina met een echte browser (Playwright)
  - logt alle netwerk-requests die op een API/feed lijken (json, /api/, /wp-json,
    algolia, 'vacature'/'opdracht'/'job'/'search' in de url)
  - detecteert het framework (__NEXT_DATA__, __NUXT__, wp-json, ...)
  - telt kandidaat-DOM-selectors en print de outerHTML van de eerste "kaart"
  - print ankers die op detail-URL's lijken

Dit bestand mag na de verkenning weer verwijderd worden.
"""

import json
import re
from playwright.sync_api import sync_playwright

SITES = {
    "freelancenl": "https://www.freelance.nl/opdrachten",
    "mipublic": "https://mipublic.nl/zzp-opdrachten-overheid/",
    "ns": "https://www.werkenbijns.nl/vacatures",
    "stedin": "https://werkenbij.stedin.net/vacatures-zoeken",
}

API_HINT = re.compile(
    r"(/api/|/wp-json|algolia|/search|graphql|\.json|vacature|opdracht|jobs?\b|feed)",
    re.I,
)
STATIC = re.compile(r"\.(png|jpe?g|gif|svg|webp|woff2?|ttf|css|ico|mp4)(\?|$)", re.I)

CARD_HINTS = [
    "vacature", "opdracht", "job", "card", "listing", "result", "vacancy",
    "position", "search-result", "list-item", "tile",
]


def verken(naam, url, page):
    print(f"\n{'='*70}\n### {naam}  ->  {url}\n{'='*70}")

    api_calls = []

    def on_response(resp):
        u = resp.url
        if STATIC.search(u):
            return
        ct = resp.headers.get("content-type", "")
        interessant = "json" in ct or API_HINT.search(u)
        if interessant:
            api_calls.append((resp.request.method, resp.status, ct.split(";")[0], u))

    page.on("response", on_response)

    try:
        page.goto(url, timeout=60000, wait_until="domcontentloaded")
    except Exception as e:
        print(f"  goto fout: {e}")
    page.wait_for_timeout(6000)
    try:
        page.mouse.wheel(0, 4000)
        page.wait_for_timeout(2500)
    except Exception:
        pass

    print(f"\n-- titel: {page.title()!r}")
    print(f"-- eind-url: {page.url}")

    # Framework-detectie
    html = page.content()
    for marker in ["__NEXT_DATA__", "__NUXT__", "window.__INITIAL_STATE__",
                   "wp-json", "wp-content", "data-server-rendered", "ng-version"]:
        if marker in html:
            print(f"-- framework-marker gevonden: {marker}")

    # __NEXT_DATA__ dumpen (keys)
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if m:
        try:
            data = json.loads(m.group(1))
            pp = data.get("props", {}).get("pageProps", {})
            print(f"-- __NEXT_DATA__ pageProps keys: {list(pp.keys())}")
            print(f"-- buildId: {data.get('buildId')}")
            blob = json.dumps(pp)[:1500]
            print(f"-- pageProps sample: {blob}")
        except Exception as e:
            print(f"-- __NEXT_DATA__ parse fout: {e}")

    # Interessante netwerk-calls
    print(f"\n-- {len(api_calls)} mogelijk interessante netwerk-calls:")
    gezien = set()
    for method, status, ct, u in api_calls:
        key = u.split("?")[0]
        if key in gezien:
            continue
        gezien.add(key)
        print(f"   [{method} {status} {ct}] {u[:180]}")

    # Kandidaat-kaarten in de DOM
    print("\n-- kandidaat DOM-selectors (class/id bevat hint):")
    for hint in CARD_HINTS:
        try:
            n = page.eval_on_selector_all(
                f"[class*='{hint}'], [id*='{hint}']", "els => els.length"
            )
        except Exception:
            n = 0
        if n:
            print(f"   *{hint}*: {n} elementen")

    # Ankers die op detailpagina's lijken
    hrefs = page.eval_on_selector_all(
        "a[href]", "els => els.map(e => e.getAttribute('href'))"
    )
    patronen = {}
    for h in hrefs:
        if not h:
            continue
        for pat in ["/opdracht/", "/vacature/", "/vacatures/", "/vacancy/",
                    "/job/", "/jobs/", "/vac/"]:
            if pat in h:
                patronen.setdefault(pat, []).append(h)
    for pat, lst in patronen.items():
        print(f"\n-- ankers met '{pat}': {len(lst)} (eerste 8)")
        for h in lst[:8]:
            print(f"   {h}")

    # outerHTML van eerste kandidaat-kaart
    for hint in CARD_HINTS:
        try:
            el = page.query_selector(f"[class*='{hint}']")
            if el:
                outer = el.evaluate("e => e.outerHTML")
                if len(outer) > 200:  # sla lege wrappers over
                    print(f"\n-- eerste '*{hint}*' outerHTML (max 2500 chars):")
                    print(outer[:2500])
                    break
        except Exception:
            continue


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            locale="nl-NL",
        )
        for naam, url in SITES.items():
            page = ctx.new_page()
            try:
                verken(naam, url, page)
            except Exception as e:
                print(f"\n### {naam} MISLUKT: {e}")
            finally:
                page.close()
        browser.close()


if __name__ == "__main__":
    main()
