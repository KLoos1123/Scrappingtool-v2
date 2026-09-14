"""Port of Rotterdam (HBR Inhuurdesk) - Nétive VMS op Salesforce.

Zelfde onderliggende platform als stedin_vms.py (Nétive VMS, Salesforce
Experience Cloud): login via input[name=username/password], daarna een
directe Lightning-lijstweergave op jRequest__c. We lezen die generiek uit
(kolomkoppen + celwaarden), net als bij Stedin.

Vereist secrets PORTOFROTTERDAM_EMAIL en PORTOFROTTERDAM_WACHTWOORD.

Let op: nog niet getest met een echt account (alleen de inlogpagina kon
zonder credentials geverifieerd worden). Als de aanvragen-lijst een ander
pad blijkt te hebben dan bij Stedin, meld dat dan zodat AANVRAGEN
aangepast kan worden.
"""

import os
from playwright.sync_api import sync_playwright

BRON = "portofrotterdam"

BASIS = "https://portofrotterdamsso.my.site.com"
LOGIN = f"{BASIS}/vms/s/login/?language=nl_NL"
AANVRAGEN = f"{BASIS}/vms/s/jrequest/jRequest__c/Default"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")


def _login(page, email, wachtwoord):
    page.goto(LOGIN, timeout=60000, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    page.fill("input[name='username']", email)
    page.fill("input[name='password']", wachtwoord)
    page.click("button:has-text('Inloggen')")
    page.wait_for_timeout(9000)
    if "login" in page.url.lower():
        raise RuntimeError("inloggen mislukt")


def _lees_datatable(page):
    """Leest de lightning-datatable generiek uit: koppen + rijen met recordlink."""
    rijen = []
    try:
        page.wait_for_selector("table[role='grid'] tbody tr, table.slds-table tbody tr",
                               timeout=15000)
    except Exception:
        return rijen  # geen rijen (leeg overzicht)

    tabel = (page.query_selector("table[role='grid']")
             or page.query_selector("table.slds-table"))
    if not tabel:
        return rijen

    koppen = []
    for th in tabel.query_selector_all("thead th"):
        t = (th.inner_text() or "").strip().replace("\n", " ")
        for ruis in ["Sorteren op:", "Gesorteerd: Geen", "kolomacties tonen"]:
            t = t.replace(ruis, " ")
        koppen.append(" ".join(t.split()))

    for tr in tabel.query_selector_all("tbody tr"):
        cellen = tr.query_selector_all("th,td")
        waarden = [(c.inner_text() or "").strip().replace("\n", " ") for c in cellen]
        if not any(waarden):
            continue
        link = tr.query_selector("a[href]")
        href = link.get_attribute("href") if link else None
        if href and href.startswith("/"):
            href = BASIS + href
        rij = {}
        for i, w in enumerate(waarden):
            kop = koppen[i] if i < len(koppen) else f"kol{i}"
            rij[kop] = w
        rij["_url"] = href
        rijen.append(rij)
    return rijen


def _norm(rij):
    def pak(*namen):
        for n in namen:
            for k, v in rij.items():
                if n.lower() in k.lower() and v:
                    return v
        return None

    nummer = pak("Aanvraag", "Nummer") or ""
    titel = pak("Functie", "Functietitel", "Onderwerp") or nummer
    return {
        "tender_id": nummer or (rij.get("_url") or titel),
        "nummer": nummer or None,
        "titel": titel,
        "organisatie": pak("Klant") or "Havenbedrijf Rotterdam",
        "status": pak("Status") or "Open",
        "deadline": pak("Sluitingsdatum", "Reactietermijn", "Einddatum"),
        "publicatiedatum": pak("Publicatiedatum", "Startdatum"),
        "locatie": pak("Werklocatie", "Afdeling"),
        "url": rij.get("_url") or AANVRAGEN,
    }


def haal_op():
    """Wordt aangeroepen door run.py. Geeft een lijst dicts terug."""
    email = os.environ.get("PORTOFROTTERDAM_EMAIL")
    wachtwoord = os.environ.get("PORTOFROTTERDAM_WACHTWOORD")
    if not email or not wachtwoord:
        print("  PORTOFROTTERDAM_EMAIL/WACHTWOORD ontbreekt; overslaan")
        return []

    rijen = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="nl-NL")
        page = ctx.new_page()
        try:
            ingelogd = False
            for poging in range(2):
                try:
                    _login(page, email, wachtwoord)
                    ingelogd = True
                    break
                except Exception as e:
                    print(f"  login-poging {poging + 1} mislukt ({type(e).__name__})")
                    page.wait_for_timeout(4000)
            if not ingelogd:
                print("  inloggen niet gelukt; bron overgeslagen (geen data)")
                return []

            page.goto(AANVRAGEN, timeout=60000, wait_until="domcontentloaded")
            page.wait_for_timeout(8000)
            ruw = _lees_datatable(page)
            print(f"  {len(ruw)} aanvragen in lijstweergave")
            rijen = [_norm(r) for r in ruw]
        finally:
            browser.close()

    if not rijen:
        print("  (geen open aanvragen voor dit account op dit moment)")
    return rijen
