"""Recon ronde 2: inhuur-subdomeinen + kaartstructuren (TIJDELIJK)."""

import re
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

SITES = {
    "inhuur-nhn": "https://inhuur.werkeninnoordhollandnoord.nl/",
    "inhuurdesk-nob": "https://inhuurdesk.werkeninnoordoostbrabant.nl/",
    "inhuur-zob": "https://inhuur.werkeninzuidoostbrabant.nl/",
    "gelderland": "https://www.werkeningelderland.nl/inhuur/",
    "flexwestbrabant-opdrachten": "https://flexwestbrabant.nl/opdrachten/",
    "flexwestbrabant-home": "https://flexwestbrabant.nl/",
}

API_HINT = re.compile(r"(/api/|/wp-json|graphql|\.json|search|opdracht|vacature|aanvraag|request)", re.I)
STATIC = re.compile(r"\.(png|jpe?g|gif|svg|webp|woff2?|ttf|css|ico|mp4)(\?|$)", re.I)

CARD_HINTS = ["opdracht", "aanvraag", "vacature", "job", "card", "result",
              "listing", "item", "post", "tender"]


def verken(naam, url, ctx):
    print(f"\n{'='*70}\n### {naam}  ->  {url}\n{'='*70}")
    page = ctx.new_page()
    api_calls = []

    def on_response(resp):
        u = resp.url
        if STATIC.search(u) or "maps.googleapis" in u or "google" in u:
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

    hrefs = page.eval_on_selector_all(
        "a[href]", "els => els.map(e => e.getAttribute('href'))")
    for pat in ["opdracht", "aanvraag", "vacature", "detail", "request"]:
        matches = list(dict.fromkeys(
            h for h in hrefs if h and pat in h.lower() and "linkedin" not in h))
        if matches:
            print(f"-- ankers met '{pat}': {len(matches)} (eerste 6)")
            for h in matches[:6]:
                print(f"     {h}")

    # eerste inhoudelijke "kaart" dumpen
    for hint in CARD_HINTS:
        try:
            els = page.query_selector_all(f"[class*='{hint}']")
        except Exception:
            continue
        for el in els[:3]:
            try:
                outer = el.evaluate("e => e.outerHTML")
            except Exception:
                continue
            if len(outer) > 300 and ("<a" in outer or "href" in outer):
                print(f"\n-- '*{hint}*' outerHTML (max 2200):\n{outer[:2200]}")
                break
        else:
            continue
        break

    gezien = set()
    print(f"\n-- {len(api_calls)} interessante netwerk-calls:")
    for method, status, ct, u in api_calls:
        key = u.split("?")[0]
        if key in gezien:
            continue
        gezien.add(key)
        print(f"   [{method} {status} {ct}] {u[:170]}")

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
