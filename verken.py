"""Magnit: retrievejobrequests-payload + response + token-locatie (TIJDELIJK).

Logt in, opent Aanvragen, en legt bij binnenkomst de payload en de body van
de data-calls vast. Zoekt ook waar de OIDC-access-token is opgeslagen
(alleen sleutelnamen, niet de tokenwaarde).
"""

import os
import json
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

BASE = "https://portal.magnitglobal.com"
START = f"{BASE}/supplier/jobrequests/new"

DATA_HINT = ("jobrequest", "retrievejob", "assignment", "expertise",
             "categorycount", "dashboard")
SKIP = (".js", ".css", ".png", ".jpg", ".svg", ".woff", "google", "segment",
        "analytics", "sentry", "negotiate", "openid")


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
    if not email or not wachtwoord:
        print("!! secrets ontbreken")
        return

    captured = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="nl-NL")
        page = ctx.new_page()

        def on_resp(resp):
            try:
                ct = resp.headers.get("content-type", "")
                if not _interessant(resp.url, ct):
                    return
                entry = {"method": resp.request.method,
                         "url": resp.url.split("?")[0]}
                try:
                    entry["postdata"] = (resp.request.post_data or "")[:1000]
                except Exception:
                    entry["postdata"] = None
                try:
                    entry["body"] = resp.text()[:2500]
                except Exception as e:
                    entry["body"] = f"<geen body: {e}>"
                captured.append(entry)
            except Exception:
                pass

        page.on("response", on_resp)

        # login
        page.goto(START, timeout=60000, wait_until="domcontentloaded")
        page.wait_for_selector("input[type='password']", timeout=30000)
        page.query_selector(
            "input[type='email'], input[placeholder*='mail']").fill(email)
        page.query_selector("input[type='password']").fill(wachtwoord)
        page.query_selector(
            "button:has-text('Inloggen'), button[type='submit']").click()
        page.wait_for_timeout(8000)

        # naar Aanvragen
        for sel in ["a:has-text('Aanvragen')", "text=AANVRAGEN",
                    "a:has-text('Naar alle aanvragen')"]:
            el = page.query_selector(sel)
            if el:
                el.click()
                break
        page.wait_for_timeout(8000)

        # token-locatie zoeken (alleen sleutelnamen + shape, geen waarde)
        try:
            info = page.evaluate("""() => {
                const out = {local: [], session: [], oidc: null};
                for (let i=0;i<localStorage.length;i++){
                    const k = localStorage.key(i); out.local.push(k);
                    if (k.toLowerCase().includes('oidc') || k.toLowerCase().includes('user')) {
                        try { const v = JSON.parse(localStorage.getItem(k));
                            out.oidc = {key: k, fields: Object.keys(v),
                                        hasAccess: !!v.access_token,
                                        tokenType: v.token_type,
                                        profileKeys: v.profile? Object.keys(v.profile): null};
                        } catch(e){}
                    }
                }
                for (let i=0;i<sessionStorage.length;i++) out.session.push(sessionStorage.key(i));
                return out;
            }""")
            print("-- localStorage keys:", info["local"])
            print("-- sessionStorage keys:", info["session"])
            print("-- oidc-user:", info["oidc"])
        except Exception as e:
            print(f"-- storage-scan fout: {e}")

        print(f"\n-- {len(captured)} data-calls vastgelegd:")
        for e in captured:
            print(f"\n>>> {e['method']} {e['url']}")
            if e.get("postdata"):
                print(f"    PAYLOAD: {e['postdata']}")
            body = e.get("body", "")
            # probeer nette structuur te tonen
            try:
                d = json.loads(body) if body.startswith(("{", "[")) else None
            except Exception:
                d = None
            if isinstance(d, dict):
                print(f"    keys: {list(d.keys())[:20]}")
                for veld in ("content", "items", "results", "data", "records",
                             "jobRequests", "aanvragen", "value"):
                    lst = d.get(veld)
                    if isinstance(lst, list) and lst and isinstance(lst[0], dict):
                        print(f"    '{veld}': {len(lst)} items; item-keys: {list(lst[0].keys())}")
                        print(f"    item0: {json.dumps(lst[0], ensure_ascii=False)[:1500]}")
                        break
            else:
                print(f"    body: {body[:1500]}")

        browser.close()


if __name__ == "__main__":
    main()
