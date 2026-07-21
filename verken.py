"""Validatie + NS-structuur (TIJDELIJK).

- draait de freelance.nl- en stedin-scraper en print aantallen + voorbeelden
- dumpt de NS-vacaturekaart-structuur en paginering zodat we ns.py precies
  kunnen schrijven
"""

import re
import traceback
from playwright.sync_api import sync_playwright
from scrapers import freelancenl, stedin

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def test_scraper(mod):
    print(f"\n{'='*60}\n### {mod.BRON}\n{'='*60}")
    try:
        rijen = mod.haal_op()
        print(f"  TOTAAL: {len(rijen)}")
        for r in rijen[:3]:
            print("   ", r)
    except Exception as e:
        print(f"  MISLUKT: {e}")
        traceback.print_exc()


def dump_ns():
    print(f"\n{'='*60}\n### NS structuur-dump\n{'='*60}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(user_agent=UA, locale="nl-NL").new_page()
        page.goto("https://www.werkenbijns.nl/vacatures", timeout=60000,
                  wait_until="networkidle")
        page.wait_for_timeout(3000)

        # vacature-ankers
        hrefs = page.eval_on_selector_all(
            "a[href*='/vacatures/']", "els => els.map(e => e.getAttribute('href'))")
        vac = [h for h in hrefs if h and re.search(r"-\d+$", h)]
        print(f"-- {len(vac)} vacature-ankers (met -id), eerste 5: {vac[:5]}")

        # eerste vacaturekaart: ga vanaf een anker omhoog naar de li/article
        el = page.query_selector("a[href*='/vacatures/'][href$='0'], a[href*='/vacatures/']")
        for sel in ["li[class*='vacancy']", "article", "div[class*='vacancy']",
                    "li[class*='result']", "div[class*='result']"]:
            kaart = page.query_selector(sel)
            if kaart:
                outer = kaart.evaluate("e => e.outerHTML")
                if len(outer) > 200 and "vacatures/" in outer:
                    print(f"\n-- kaart '{sel}' outerHTML (max 2500):\n{outer[:2500]}")
                    break

        # paginering
        for sel in ["a[rel='next']", "[class*='pagination'] a", "[class*='pager'] a",
                    "a[class*='next']", "nav a"]:
            els = page.query_selector_all(sel)
            if els:
                print(f"\n-- paginatie '{sel}': {len(els)}")
                for e in els[:8]:
                    print(f"     href={e.get_attribute('href')!r} "
                          f"text={e.inner_text()[:25]!r} "
                          f"aria={e.get_attribute('aria-label')!r}")
        # url met ?page=2 proberen
        r2 = page.request.get("https://www.werkenbijns.nl/vacatures?page=2", timeout=20000)
        h2 = re.findall(r'/vacatures/[a-z0-9-]+-(\d+)', r2.text())
        print(f"\n-- ?page=2 status={r2.status} unieke ids in html: {len(set(h2))} "
              f"eerste: {list(dict.fromkeys(h2))[:5]}")
        browser.close()


def main():
    test_scraper(freelancenl)
    test_scraper(stedin)
    dump_ns()


if __name__ == "__main__":
    main()
