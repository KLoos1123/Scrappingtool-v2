"""Stedin paginering achterhalen (TIJDELIJK)."""

import re
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
BASE = "https://werkenbij.stedin.net"


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(user_agent=UA, locale="nl-NL").new_page()

        results = []
        page.on("response", lambda r: results.append(r) if "search-jobs" in r.url else None)

        page.goto(f"{BASE}/vacatures-zoeken", timeout=60000, wait_until="networkidle")
        page.wait_for_timeout(3000)

        # aantal/telling
        for sel in ["[class*='count']", "[class*='total']", "[class*='result-header']",
                    ".job-count", "h1", "h2"]:
            el = page.query_selector(sel)
            if el:
                t = el.inner_text().strip()
                if t:
                    print(f"-- telling '{sel}': {t[:80]!r}")

        n0 = page.locator("a.job-list--link[data-job-id]").count()
        print(f"-- kaarten initieel: {n0}")

        # paginering-control zoeken en outer HTML tonen
        for sel in ["[class*='pagination']", "nav[class*='pag']", ".pager",
                    "[class*='paging']", "ul[class*='pag']"]:
            el = page.query_selector(sel)
            if el:
                print(f"\n-- '{sel}' outerHTML:\n{el.evaluate('e => e.outerHTML')[:1500]}")

        # alle knoppen/links met relevante tekst
        print("\n-- knoppen/links met meer/volgende/toon/laad/pagina:")
        for el in page.query_selector_all("button, a"):
            try:
                t = (el.inner_text() or "").strip().lower()
            except Exception:
                continue
            if any(w in t for w in ["meer", "volgende", "toon", "laad", "next", "pagina"]):
                print(f"     <{el.evaluate('e=>e.tagName')}> text={t[:30]!r} "
                      f"href={el.get_attribute('href')!r} class={el.get_attribute('class')!r}")

        # klik op pagina 2 als die er is, kijk of DOM verandert
        klik = None
        for sel in ["[class*='pagination'] a", "a[data-page='2']", "a[aria-label*='2']"]:
            els = page.query_selector_all(sel)
            for e in els:
                if (e.inner_text() or "").strip() == "2" or "page=2" in (e.get_attribute("href") or ""):
                    klik = e
                    break
            if klik:
                break
        if klik:
            print(f"\n-- klik op pagina 2: href={klik.get_attribute('href')!r}")
            results.clear()
            try:
                klik.click(timeout=3000)
                page.wait_for_timeout(3000)
            except Exception as e:
                print(f"   klik-fout: {e}")
            n1 = page.locator("a.job-list--link[data-job-id]").count()
            ids = page.eval_on_selector_all(
                "a.job-list--link[data-job-id]", "els=>els.map(e=>e.getAttribute('data-job-id'))")
            print(f"   kaarten na klik: {n1}, eerste ids: {ids[:5]}")
            for r in results:
                print(f"   search-jobs call: {r.request.method} {r.url[:200]}")
                try:
                    print(f"      body: {r.text()[:300]}")
                except Exception:
                    pass
        else:
            print("\n-- geen pagina-2 link gevonden")

        browser.close()


if __name__ == "__main__":
    main()
