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

        base = "https://stedin-vms.my.site.com/vms/servlet/networks/switch?networkId=0DB2p00000002OA&startURL="
        paginas = {
            "Aanvragen (/a1J/l)": base + "/a1J/l?bid=stedin",
            "Opdrachten (/a0j/o)": base + "/a0j/o?bid=stedin",
            "DAS TenderDashboard": base + "/apex/c__TenderDashboard?bid=stedin",
        }
        for label, url in paginas.items():
            try:
                page.goto(url, timeout=60000, wait_until="domcontentloaded")
                page.wait_for_timeout(7000)
                print(f"\n  ===== {label} -> {page.url}")
                # dump zichtbare tekst (kort) + tabellen
                try:
                    txt = page.inner_text("body")
                    print(f"  body-tekst({len(txt)}): {txt[:800]}")
                except Exception:
                    pass
                dump_tabellen(page, label)
                for fr in page.frames:
                    if fr == page.main_frame:
                        continue
                    try:
                        if fr.query_selector_all("table"):
                            dump_tabellen(fr, f"{label}/iframe")
                    except Exception:
                        pass
            except Exception as e:
                print(f"  '{label}' fout: {e}")
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


def stedin_vms_check():
    print(f"\n{'='*70}\n### stedin_vms scraper (validatie)\n{'='*70}")
    try:
        from scrapers import stedin_vms
        rijen = stedin_vms.haal_op()
        print(f"  RESULTAAT: {len(rijen)} aanvragen")
        for r in rijen[:3]:
            print(f"    {r['nummer']} | {r['titel'][:40]} | {r['organisatie']} | {r['url']}")
    except Exception as e:
        import traceback
        print(f"  stedin_vms MISLUKT: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    freelance_check()
    stedin_vms_check()
