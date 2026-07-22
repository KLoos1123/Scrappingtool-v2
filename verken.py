"""Recon (TIJDELIJK): Stedin-VMS opdrachten-pagina's + validatie freelance ingelogd."""

import os
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def dump_tabellen(page, label):
    print(f"\n  --- {label}: {page.url}")
    try:
        # klassieke Visualforce/Salesforce list views renderen <table>
        tabellen = page.query_selector_all("table")
        print(f"  {len(tabellen)} tabellen")
        for ti, t in enumerate(tabellen):
            rijen = t.query_selector_all("tr")
            if len(rijen) < 2:
                continue
            teksten = []
            for r in rijen[:12]:
                cellen = r.query_selector_all("th,td")
                vals = [(c.inner_text() or "").strip().replace("\n", " ") for c in cellen]
                vals = [v for v in vals if v]
                if vals:
                    teksten.append(" | ".join(vals)[:220])
            if len(teksten) >= 2:
                print(f"\n  [tabel {ti}] {len(rijen)} rijen:")
                for line in teksten:
                    print(f"    {line}")
    except Exception as e:
        print(f"  tabel-dump fout: {e}")


def stedinvms():
    print(f"\n{'='*70}\n### Stedin-VMS opdrachten\n{'='*70}")
    email = os.environ.get("STEDINVMS_EMAIL")
    pw = os.environ.get("STEDINVMS_WACHTWOORD")
    if not email or not pw:
        print("  secrets ontbreken"); return
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="nl-NL")
        page = ctx.new_page()
        page.goto("https://stedin-vms.my.site.com/vms/s/login", timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)
        try:
            page.fill("input[name='username']", email)
            page.fill("input[name='password']", pw)
            page.click("button:has-text('Login')")
        except Exception as e:
            print(f"  login fout: {e}")
        page.wait_for_timeout(9000)
        print(f"  na login: {page.url}")

        # klik door naar de relevante pagina's en dump tabellen
        for tekst in ["Dynamisch aankoopsystemen", "Aanvragen", "Opdrachten"]:
            try:
                el = page.query_selector(f"a:has-text('{tekst}')")
                if not el:
                    print(f"\n  link '{tekst}' niet gevonden")
                    continue
                el.click()
                page.wait_for_timeout(8000)
                # soms opent een iframe (Visualforce)
                dump_tabellen(page, tekst)
                for fr in page.frames:
                    if fr == page.main_frame:
                        continue
                    try:
                        tb = fr.query_selector_all("table")
                        if tb:
                            print(f"  [iframe {fr.url[:80]}] {len(tb)} tabellen")
                            dump_tabellen(fr, f"{tekst}/iframe")
                    except Exception:
                        pass
            except Exception as e:
                print(f"  '{tekst}' fout: {e}")
        browser.close()


def freelance_check():
    print(f"\n{'='*70}\n### freelance.nl ingelogd (validatie scraper)\n{'='*70}")
    try:
        from scrapers import freelancenl
        rijen = freelancenl.haal_op()
        print(f"  RESULTAAT: {len(rijen)} opdrachten")
        for r in rijen[:3]:
            print(f"    {r['nummer']} | {r['titel'][:40]} | deadline={r['deadline']} "
                  f"| org={r['organisatie']} | uren={r['uren_per_week']}")
    except Exception as e:
        print(f"  freelance MISLUKT: {e}")


if __name__ == "__main__":
    freelance_check()
    stedinvms()
