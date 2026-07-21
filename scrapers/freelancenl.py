"""freelance.nl - freelance opdrachten.

De site blokkeert kale requests (WAF geeft dan 403), daarom laden we eerst
de opdrachtenpagina in een echte browser en bevragen we daarna de publieke
GraphQL-endpoint (/public-api) via diezelfde browsercontext. Die endpoint
geeft alle opdrachten gepagineerd terug (query publicSearch met offset/limit).
"""

import re
import json
from playwright.sync_api import sync_playwright

BRON = "freelance.nl"

APP = "https://www.freelance.nl"
API = f"{APP}/public-api"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

QUERY = """
query PublicSearch($query: SearchQueryInput!, $sortMethod: String!, $limit: Int!, $offset: Int!) {
  publicSearch(query: $query, sortMethod: $sortMethod, limit: $limit, offset: $offset) {
    count
    results {
      assignment {
        title
        place
        hoursFrom
        hoursTo
        id
        status
        publishAt
      }
    }
  }
}
"""


def _slug(titel):
    s = (titel or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def _uit_assignment(a):
    aid = a.get("id")
    titel = a.get("title") or ""
    slug = _slug(titel)
    url = f"{APP}/opdracht/{aid}-{slug}" if slug else f"{APP}/opdracht/{aid}"

    uren = None
    if a.get("hoursFrom") or a.get("hoursTo"):
        uren = f"{a.get('hoursFrom') or '?'}-{a.get('hoursTo') or '?'}"

    return {
        "tender_id": str(aid),
        "nummer": str(aid),
        "titel": titel,
        "organisatie": None,           # niet aanwezig in de publieke API
        "status": a.get("status"),
        "deadline": None,
        "publicatiedatum": a.get("publishAt"),
        "locatie": a.get("place") or None,
        "uren_per_week": uren,
        "url": url,
    }


def _zoek(ctx, offset, limit):
    payload = {
        "query": QUERY,
        "variables": {
            "query": {"onLocation": False},
            "sortMethod": "newest",
            "limit": limit,
            "offset": offset,
        },
    }
    resp = ctx.request.post(
        API,
        data=json.dumps(payload),
        headers={
            "content-type": "application/json",
            "accept": "application/json",
            "referer": f"{APP}/opdrachten",
        },
        timeout=30000,
    )
    if not resp.ok:
        raise RuntimeError(f"public-api gaf {resp.status}")
    return resp.json()


def haal_op():
    """Wordt aangeroepen door run.py. Geeft een lijst dicts terug."""
    rijen = []
    limit = 100

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="nl-NL")
        page = ctx.new_page()

        # Pagina laden om een geldige sessie/cookies op te bouwen.
        page.goto(f"{APP}/opdrachten", timeout=60000, wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        offset = 0
        totaal = None
        while True:
            data = _zoek(ctx, offset, limit)
            zoek = (data.get("data") or {}).get("publicSearch") or {}
            if totaal is None:
                totaal = zoek.get("count") or 0
                print(f"  {totaal} opdrachten beschikbaar")

            blok = zoek.get("results") or []
            if not blok:
                break

            for r in blok:
                a = r.get("assignment") or {}
                if a.get("id"):
                    rijen.append(_uit_assignment(a))

            offset += limit
            if offset >= (totaal or 0):
                break

        browser.close()

    print(f"  {len(rijen)} opdrachten opgehaald")
    return rijen
