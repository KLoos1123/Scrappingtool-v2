"""Regionale inhuurdesks op het gedeelde "Marktplaats"-platform.

Drie desks draaien op identieke software (server-side gerenderd):
  - inhuur.werkeninnoordhollandnoord.nl
  - inhuurdesk.werkeninnoordoostbrabant.nl
  - inhuur.werkeninzuidoostbrabant.nl

Opdracht-links hebben de vorm /Opdracht/{Organisatie-slug}/{Titel-slug}/{id}.
We lezen de /opdrachten-lijstpagina (en de homepage als vangnet) en proberen
eenvoudige ?page=N-paginering tot er geen nieuwe id's meer bijkomen.

Op /opdrachten zijn de items geen <a>, maar li.searchresult-item met een
data-view-url; daar staat ook de deadline ("Reageren voor: 02-11-2026 17:00").
De detailpagina toont die deadline niet, de homepage-ankers ook niet.
"""

import re
from urllib.parse import unquote
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup

BRON = "inhuurdesk-regio"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

DESKS = [
    ("nhn", "Noord-Holland Noord", "https://inhuur.werkeninnoordhollandnoord.nl"),
    ("nob", "Noordoost-Brabant", "https://inhuurdesk.werkeninnoordoostbrabant.nl"),
    ("zob", "Zuidoost-Brabant", "https://inhuur.werkeninzuidoostbrabant.nl"),
]

OPDRACHT_RE = re.compile(r"^/Opdracht/([^/]+)/([^/]+)/(\d+)$")
DEADLINE_RE = re.compile(r"(\d{1,2})-(\d{1,2})-(\d{4})(?:\s+(\d{1,2}):(\d{2}))?")
MAX_PAGINA = 30


def _ontslug(s):
    """'Gemeente-Schagen' -> 'Gemeente Schagen' (lossy maar leesbaar)."""
    return re.sub(r"\s+", " ", unquote(s).replace("-", " ")).strip()


def _iso(tekst):
    """'02-11-2026 17:00' -> '2026-11-02T17:00'."""
    m = DEADLINE_RE.search(tekst or "")
    if not m:
        return None
    dag, maand, jaar, uur, minuut = m.groups()
    datum = f"{jaar}-{int(maand):02d}-{int(dag):02d}"
    if uur:
        datum += f"T{int(uur):02d}:{minuut}"
    return datum


def _uit_item(li, base, prefix, regio):
    """Item van de /opdrachten-lijst: titel, labels/waarden en de deadline."""
    kop = li.select_one(".searchresult-item-header > div")
    rij = _maak_rij(li.get("data-view-url"), kop.get_text(strip=True) if kop else None,
                    base, prefix, regio)
    if not rij:
        return None
    labels = [l.get_text(strip=True).lower() for l in li.select(".searchresult-item-label")]
    waarden = [w.get_text(" ", strip=True) for w in li.select(".searchresult-item-value")]
    for label, waarde in zip(labels, waarden):
        if label.startswith("reageren voor"):
            rij["deadline"] = _iso(waarde)
    return rij


def _uit_anker(a, base, prefix, regio):
    return _maak_rij(a.get("href"), a.get_text(strip=True), base, prefix, regio)


def _maak_rij(href, tekst, base, prefix, regio):
    m = OPDRACHT_RE.match(href or "")
    if not m:
        return None
    org_slug, titel_slug, oid = m.groups()

    # De h3 op de homepage kapt lange titels af ("...piek..."); de URL-slug
    # bevat de volledige titel, dus die heeft dan de voorkeur.
    titel = tekst or None
    if (not titel or titel.lower() in ("delen", "bekijk")
            or titel.endswith("...") or titel.endswith("…")):
        titel = _ontslug(titel_slug)

    return {
        "tender_id": f"{prefix}-{oid}",
        "nummer": oid,
        "titel": titel,
        "organisatie": _ontslug(org_slug),
        "status": "Open",
        "deadline": None,
        "publicatiedatum": None,
        "locatie": regio,
        "url": base + href,
    }


def _desk(ctx, prefix, regio, base):
    rijen = {}

    def verwerk(html):
        nieuw = 0
        soup = BeautifulSoup(html, "lxml")
        kandidaten = [_uit_item(li, base, prefix, regio)
                      for li in soup.select("li.searchresult-item[data-view-url]")]
        kandidaten += [_uit_anker(a, base, prefix, regio)
                       for a in soup.select("a[href^='/Opdracht/']")]
        for rij in kandidaten:
            if rij and rij["tender_id"] not in rijen:
                # kies het anker met de beste titel (h3 boven lege ankers)
                rijen[rij["tender_id"]] = rij
                nieuw += 1
            elif rij:
                oud = rijen[rij["tender_id"]]
                if (not oud["titel"] or len(rij["titel"] or "") > len(oud["titel"])):
                    rij["deadline"] = rij["deadline"] or oud["deadline"]
                    rijen[rij["tender_id"]] = rij
        return nieuw

    # lijstpagina met simpele paginering, homepage als vangnet
    for pagina in range(1, MAX_PAGINA + 1):
        url = f"{base}/opdrachten" if pagina == 1 else f"{base}/opdrachten?page={pagina}"
        try:
            r = ctx.request.get(url, timeout=30000)
        except Exception as e:
            print(f"    {prefix} pagina {pagina}: {e}")
            break
        if not r.ok:
            break
        if verwerk(r.text()) == 0:
            break

    try:
        r = ctx.request.get(base + "/", timeout=30000)
        if r.ok:
            verwerk(r.text())
    except Exception:
        pass

    print(f"    {regio}: {len(rijen)}")
    return list(rijen.values())


def haal_op():
    """Wordt aangeroepen door run.py. Geeft een lijst dicts terug."""
    rijen = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="nl-NL")
        for prefix, regio, base in DESKS:
            try:
                rijen.extend(_desk(ctx, prefix, regio, base))
            except Exception as e:
                print(f"    {regio} MISLUKT: {e}")
        browser.close()

    print(f"  {len(rijen)} opdrachten gevonden, "
          f"{sum(1 for r in rijen if r['deadline'])} met deadline")
    return rijen
