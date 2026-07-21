"""Stedin: juiste paginering-URL bepalen (TIJDELIJK)."""

import re
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
BASE = "https://werkenbij.stedin.net"


def ids(html):
    return list(dict.fromkeys(re.findall(r'data-job-id="(\d+)"', html)))


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="nl-NL")
        # eerst de pagina laden voor sessie/cookies
        page = ctx.new_page()
        page.goto(f"{BASE}/vacatures-zoeken", timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        for url in [
            f"{BASE}/vacatures-zoeken?p=1",
            f"{BASE}/vacatures-zoeken?p=2",
            f"{BASE}/vacatures-zoeken?p=3",
            f"{BASE}/vacatures-zoeken&p=2",
            f"{BASE}/vacatures-zoeken?CurrentPage=2",
            f"{BASE}/vacatures-zoeken?pg=2",
        ]:
            r = ctx.request.get(url, timeout=30000)
            got = ids(r.text())
            print(f"{url}\n   status={r.status} kaarten={len(got)} eerste3={got[:3]}")

        browser.close()


if __name__ == "__main__":
    main()
