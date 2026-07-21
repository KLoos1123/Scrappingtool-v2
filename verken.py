"""Magnit-portaal: inloggen + aanvragen-API onderscheppen (TIJDELIJK).

Logt in met MAGNIT_EMAIL/MAGNIT_WACHTWOORD (uit secrets), opent de
Aanvragen-lijst en dumpt de JSON-API die die lijst vult. Print GEEN
wachtwoorden, cookies of auth-headers.
"""

import os
import json
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

BASE = "https://portal.magnitglobal.com"
START = f"{BASE}/supplier/jobrequests/new"

# API-achtige, data-dragende calls (geen assets/telemetrie)
DATA_HINT = ("jobrequest", "aanvra", "request", "assignment", "opdracht",
             "search", "list", "supplier")
SKIP = (".js", ".css", ".png", ".jpg", ".svg", ".woff", "google", "segment",
        "analytics", "sentry", "datadog", "telemetry")


def _interessant(url, ct):
    u = url.lower()
    if any(s in u for s in SKIP):
        return False
    if "json" not in ct:
        return False
    return any(h in u for h in DATA_HINT)


def main():
    email = os.environ.get("MAGNIT_EMAIL")
    wachtwoord = os.environ.get("MAGNIT_WACHTWOORD")
    print(f"-- MAGNIT_EMAIL gezet: {bool(email)} | MAGNIT_WACHTWOORD gezet: {bool(wachtwoord)}")
    if not email or not wachtwoord:
        print("!! secrets ontbreken, stoppen (voeg MAGNIT_EMAIL en MAGNIT_WACHTWOORD toe)")
        return

    calls = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="nl-NL")
        page = ctx.new_page()

        def on_resp(resp):
            ct = resp.headers.get("content-type", "")
            if _interessant(resp.url, ct):
                calls.append(resp)

        page.on("response", on_resp)

        # ---- inloggen ----
        page.goto(START, timeout=60000, wait_until="domcontentloaded")
        try:
            page.wait_for_selector(
                "input[type='email'], input[placeholder*='mail'], input[placeholder*='mail']",
                timeout=30000)
        except Exception:
            pass
        try:
            email_veld = page.query_selector(
                "input[type='email'], input[placeholder*='mail'], input[placeholder*='mail']")
            pw_veld = page.query_selector("input[type='password']")
            email_veld.fill(email)
            pw_veld.fill(wachtwoord)
            knop = page.query_selector(
                "button:has-text('Inloggen'), button[type='submit'], input[type='submit']")
            knop.click()
        except Exception as e:
            print(f"!! login-invoer mislukt: {e}")
            page.screenshot(path="debug_magnit_login.png", full_page=True)
            browser.close()
            return

        page.wait_for_timeout(8000)
        print(f"-- na login url: {page.url}")
        try:
            print(f"-- kop op pagina: {page.inner_text('body')[:120]!r}")
        except Exception:
            pass

        # ---- naar Aanvragen ----
        for sel in ["a:has-text('Aanvragen')", "text=AANVRAGEN",
                    "a:has-text('Naar alle aanvragen')"]:
            try:
                el = page.query_selector(sel)
                if el:
                    el.click()
                    page.wait_for_timeout(6000)
                    break
            except Exception:
                continue

        page.wait_for_timeout(3000)
        page.mouse.wheel(0, 4000)
        page.wait_for_timeout(3000)
        print(f"-- aanvragen url: {page.url}")

        # ---- API-calls dumpen ----
        print(f"\n-- {len(calls)} data-achtige JSON-calls:")
        gezien = set()
        for resp in calls:
            key = resp.url.split("?")[0]
            if key in gezien:
                continue
            gezien.add(key)
            print(f"\n>>> {resp.request.method} {resp.url.split('?')[0]}")
            try:
                data = resp.json()
            except Exception:
                continue
            if isinstance(data, dict):
                print(f"    keys: {list(data.keys())[:20]}")
                for veld in ("content", "items", "results", "data", "records",
                             "jobRequests", "aanvragen"):
                    lijst = data.get(veld)
                    if isinstance(lijst, list) and lijst:
                        print(f"    '{veld}': {len(lijst)} items; eerste item keys: "
                              f"{list(lijst[0].keys()) if isinstance(lijst[0], dict) else type(lijst[0])}")
                        print(f"    eerste item: {json.dumps(lijst[0], ensure_ascii=False)[:1400]}")
                        break
            elif isinstance(data, list) and data:
                print(f"    lijst: {len(data)} items; eerste keys: "
                      f"{list(data[0].keys()) if isinstance(data[0], dict) else type(data[0])}")
                print(f"    eerste item: {json.dumps(data[0], ensure_ascii=False)[:1400]}")

        try:
            page.screenshot(path="debug_magnit_aanvragen.png", full_page=True)
        except Exception:
            pass
        browser.close()


if __name__ == "__main__":
    main()
