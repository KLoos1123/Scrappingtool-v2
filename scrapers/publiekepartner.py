"""De Publieke Partner - interim/ZZP/detacheringsopdrachten bij (semi-)overheden.

Publieke WordPress-site, geen login nodig. De opdrachten zijn gewone posts in
de WP REST API (/wp-json/wp/v2/posts) met een ACF-blok per opdracht: status
('active'/'archive'), valid_through, organisation, location, salary,
uren_per_week, identifier_value en post_content (kopje met o.a. de
sluitingsdatum + de omschrijving). De API bevat ook alle gearchiveerde
opdrachten (40.000+) en landingspagina's zonder status, en kan niet op ACF
filteren. Daarom:
  1. lichte ronde: alle posts van de laatste VENSTER_DAGEN, alleen id + status
     + valid_through (4 pagina's tegelijk), en houd de actieve over;
  2. volledige velden van die id's ophalen via ?include= (blokken van 100).
Er komen zo'n 100 opdrachten per dag bij; actieve opdrachten ouder dan een
paar maanden zijn zeldzaam (oudste bij het bouwen: ~3 maanden).
"""

import html
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

BRON = "publiekepartner"

APP = "https://depubliekepartner.nl"
API = f"{APP}/wp-json/wp/v2/posts"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

BLOK = 100           # max per_page van de REST API
VENSTER_DAGEN = 150  # hoe ver terug we naar nog actieve opdrachten zoeken
MAX_PAGINA = 300     # veiligheidsgrens (bij ~100 posts/dag ruim boven het venster)
PARALLEL = 4

LICHT = "id,acf.status,acf.valid_through"
VOLLEDIG = ("id,date,link,title,acf.status,acf.valid_through,acf.organisation,"
            "acf.hiring_organisation_name,acf.location,acf.regio,acf.salary,"
            "acf.uren_per_week,acf.identifier_value,acf.post_content,acf.beschrijving")


def _get(sessie, params):
    """GET op de posts-API met één herkansing; geeft de response terug."""
    for poging in range(2):
        try:
            r = sessie.get(API, params=params, timeout=60)
            r.raise_for_status()
            return r
        except Exception:
            if poging:
                raise
    return None


def _actieve_ids(sessie, vanaf, vandaag):
    """Id's van actieve opdrachten met valid_through vandaag of later."""
    basis = {"per_page": BLOK, "after": vanaf, "orderby": "date", "order": "desc",
             "_fields": LICHT}

    eerste = _get(sessie, dict(basis, page=1))
    paginas = min(int(eerste.headers.get("X-WP-TotalPages") or 1), MAX_PAGINA)
    print(f"  {eerste.headers.get('X-WP-Total')} posts in de laatste {VENSTER_DAGEN} dagen "
          f"({paginas} pagina's)")

    def pagina(nr):
        try:
            return _get(sessie, dict(basis, page=nr)).json()
        except Exception as e:
            print(f"  pagina {nr} mislukt: {e}")
            return []

    posts = list(eerste.json())
    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        for blok in pool.map(pagina, range(2, paginas + 1)):
            posts.extend(blok)

    ids = []
    for p in posts:
        acf = p.get("acf") or {}
        if acf.get("status") != "active":
            continue  # 'archive' = verlopen, '' = landingspagina
        if (acf.get("valid_through") or "9999") < vandaag:
            continue
        ids.append(str(p["id"]))
    return list(dict.fromkeys(ids))


def _iso(tekst):
    """'13-11-2026 17:00' -> '2026-11-13T17:00'."""
    m = re.search(r"(\d{1,2})-(\d{1,2})-(\d{4})(?:\s+(\d{1,2}):(\d{2}))?", tekst or "")
    if not m:
        return None
    dag, maand, jaar, uur, minuut = m.groups()
    datum = f"{jaar}-{int(maand):02d}-{int(dag):02d}"
    if uur:
        datum += f"T{int(uur):02d}:{minuut}"
    return datum


def _deadline(acf):
    """Sluitingsdatum uit het kopje van post_content, anders valid_through."""
    m = re.search(r"Sluitingsdatum:\s*</b>\s*([^<\n]+)", acf.get("post_content") or "")
    if m and _iso(m.group(1)):
        return _iso(m.group(1))
    vt = acf.get("valid_through") or ""
    # '2900-01-01' is hun plaatshouder voor 'doorlopend'
    return vt if vt and vt < "2100" else None


def _oms(acf):
    tekst = acf.get("post_content") or acf.get("beschrijving")
    if not tekst:
        return None
    tekst = re.sub(r"\[elementor-template[^\]]*\]", "", tekst)
    return BeautifulSoup(tekst, "lxml").get_text(" ", strip=True) or None


def _locatie(acf):
    plaats = (acf.get("location") or "").strip()
    regio = (acf.get("regio") or "").strip()
    if plaats and regio and regio.lower() not in plaats.lower():
        return f"{plaats} - {regio}"
    return plaats or regio or None


def _uren(tekst):
    """'32 - 36 per week' -> '32-36'."""
    getallen = re.findall(r"\d+", tekst or "")
    return "-".join(getallen[:2]) if getallen else None


def _tarief(tekst):
    """'83 - 93 per uur' -> (83, 93); 'Geen maximum' -> (None, None)."""
    if "uur" not in (tekst or "").lower():
        return None, None
    getallen = [int(g) for g in re.findall(r"\d+", tekst.replace(".", ""))]
    getallen = [g for g in getallen if 20 <= g <= 400]
    if not getallen:
        return None, None
    return min(getallen), max(getallen)


def _uit_post(post):
    acf = post.get("acf") or {}
    rij = {
        "tender_id": str(post["id"]),
        "nummer": str(acf["identifier_value"]) if acf.get("identifier_value") else None,
        "titel": html.unescape((post.get("title") or {}).get("rendered") or ""),
        "organisatie": acf.get("organisation") or acf.get("hiring_organisation_name"),
        "status": "Open",
        "deadline": _deadline(acf),
        "publicatiedatum": post.get("date"),
        "locatie": _locatie(acf),
        "omschrijving": _oms(acf),
        "url": post.get("link"),
    }

    # extra's: mogen de rij nooit breken
    try:
        rij["uren_per_week"] = _uren(acf.get("uren_per_week"))
        tmin, tmax = _tarief(acf.get("salary"))
        if tmin:
            rij["tarief_min"], rij["tarief_max"] = tmin, tmax
    except Exception:
        pass
    return rij


def haal_op():
    """Wordt aangeroepen door run.py. Geeft een lijst dicts terug."""
    sessie = requests.Session()
    sessie.headers.update({"user-agent": UA, "accept": "application/json"})

    nu = datetime.now(timezone.utc)
    vanaf = (nu - timedelta(days=VENSTER_DAGEN)).strftime("%Y-%m-%dT00:00:00")
    vandaag = nu.strftime("%Y-%m-%d")

    ids = _actieve_ids(sessie, vanaf, vandaag)
    print(f"  {len(ids)} actieve opdrachten gevonden")

    # volledige velden, blokken van 100 id's, een paar tegelijk
    def details(deel):
        try:
            return _get(sessie, {"include": ",".join(deel), "per_page": BLOK,
                                 "_fields": VOLLEDIG}).json()
        except Exception as e:
            print(f"  details mislukt ({len(deel)} id's): {e}")
            return []

    blokken = [ids[i:i + BLOK] for i in range(0, len(ids), BLOK)]
    posts = {}
    with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
        for blok in pool.map(details, blokken):
            for post in blok:
                posts[str(post.get("id"))] = post

    rijen = [_uit_post(posts[i]) for i in ids if i in posts]
    print(f"  {len(rijen)} opdrachten opgehaald, "
          f"{sum(1 for r in rijen if r['deadline'])} met deadline")
    return rijen
