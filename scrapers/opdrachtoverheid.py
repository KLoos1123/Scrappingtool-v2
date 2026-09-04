"""Opdracht Overheid - verzamelplatform voor interim/freelance opdrachten bij de overheid.

Publieke JSON-API, geen login nodig. De site (Nuxt/Vue) haalt de opdrachten op
via een POST naar de kbenp-match-api (Azure Functions) met een filter- en
paginatie-payload; wij bootsen dat verzoek na. De API bundelt opdrachten uit
allerlei achterliggende bronnen (circle8, magnitglobal, ...) onder één
tender_id per opdracht, dus dedup op (bron, tender_id) werkt hier ook prima.
"""

import re
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

BRON = "opdrachtoverheid"

APP = "https://opdrachtoverheid.nl"
API = "https://kbenp-match-api.azurewebsites.net/v7/vacancies/search"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

BLOK = 100
MAX_PAGINA = 40  # veiligheidsgrens (bij 100/pagina ruim boven het huidige aanbod)


def _slug(tekst):
    s = (tekst or "").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def _url(t):
    web_key = t.get("web_key")
    if not web_key:
        return t.get("tender_url")
    org = _slug(t.get("tender_buying_organization"))
    titel = _slug(t.get("tender_name"))
    pad = "/".join(deel for deel in (org, titel) if deel)
    return f"{APP}/inhuuropdracht/{pad}/{web_key}" if pad else f"{APP}/inhuuropdracht/{web_key}"


def _oms(t):
    html = t.get("tender_overview") or t.get("tender_description_html")
    if html:
        tekst = BeautifulSoup(html, "lxml").get_text(" ", strip=True)
        if tekst:
            return tekst
    return t.get("vacancy_metadescription") or None


def _locatie(t):
    return (t.get("vacancies_location") or {}).get("province") or t.get("tender_job_location")


def _payload(offset, vanaf):
    return {
        "single": False,
        "userInput": None,
        "limit": BLOK,
        "offset": offset,
        "disjunction": 0,
        "user_coordinates": {},
        "filters": {
            "and_filters": [
                {
                    "filters": [
                        {"field_name": "tender_offline_date", "value": [vanaf], "operator": ">="},
                        {"field_name": "publish", "value": ["0"], "operator": "neq"},
                        {"field_name": "oim_vacancy", "value": ["true"], "operator": "neq"},
                        {"field_name": "direct_recruitment_vacancy", "value": ["true"], "operator": "neq"},
                    ]
                }
            ],
            "or_filters": [],
            "or_disjunction": 0,
        },
        "order_by": [{"field": "tender_first_seen", "direction": "desc"}],
    }


def _uit_tender(t):
    tid = t.get("tender_id")
    return {
        "tender_id": str(tid),
        "nummer": None,
        "titel": t.get("tender_name"),
        "organisatie": t.get("tender_buying_organization"),
        "status": t.get("tender_status"),
        "deadline": t.get("tender_offline_date"),
        "publicatiedatum": t.get("tender_first_seen"),
        "locatie": _locatie(t),
        "omschrijving": _oms(t),
        "url": _url(t),
    }


def haal_op():
    """Wordt aangeroepen door run.py. Geeft een lijst dicts terug."""
    sessie = requests.Session()
    headers = {"user-agent": UA, "content-type": "application/json", "accept": "application/json"}

    # UTC in plaats van Europe/Amsterdam (geen tzdata-afhankelijkheid nodig): dat
    # ligt altijd vóór de lokale NL-tijd, dus het filter blijft even streng of
    # iets ruimer - nooit een nog openstaande opdracht per ongeluk uitsluiten.
    vanaf = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    rijen = []
    offset = 0

    for _ in range(MAX_PAGINA):
        r = sessie.post(API, json=_payload(offset, vanaf), headers=headers, timeout=30)
        r.raise_for_status()
        blok = r.json().get("negometrix_tenders") or []
        if not blok:
            break

        rijen.extend(_uit_tender(t) for t in blok if t.get("tender_id"))

        if len(blok) < BLOK:
            break
        offset += BLOK

    print(f"  {len(rijen)} opdrachten opgehaald")
    return rijen
