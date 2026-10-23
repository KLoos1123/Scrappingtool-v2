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

Het kopje van post_content heeft vaste labels (Contractvorm, Duur van de
opdracht, Startdatum, Optie tot verlenging, Sluitingsdatum); die gaan als
kenmerken mee (zie tarieven.py) en het kopje zelf gaat uit de omschrijving.
Een opdracht waarvan de sluitingstijd voorbij is (of die het kopje "gesloten"
noemt) krijgt status Gesloten.
"""

import html
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

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
            "acf.uren_per_week,acf.identifier_value,acf.post_content,acf.beschrijving,"
            "acf.alleen_detachering,acf.zzp_value,acf.detachering")
NL = ZoneInfo("Europe/Amsterdam")


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
    datum = (_iso(m.group(1)) if m else None) or acf.get("valid_through") or ""
    # '01-01-2900' is hun plaatshouder voor 'doorlopend'
    return datum if datum and datum < "2100" else None


def _label(acf, naam):
    """Waarde achter '<b>Naam: </b>' in het kopje van post_content, als platte tekst."""
    m = re.search(r"<b>\s*" + re.escape(naam) + r"\s*:\s*</b>(.*?)(?:<br\s*/?>|</p>)",
                  acf.get("post_content") or "", re.I | re.S)
    if not m:
        return ""
    return re.sub(r"\s+", " ", BeautifulSoup(m.group(1), "lxml").get_text(" ", strip=True)).strip()


def _oms(acf):
    tekst = acf.get("post_content") or acf.get("beschrijving")
    if not tekst:
        return None
    tekst = re.sub(r"\[elementor-template[^\]]*\]", "", tekst)
    # het kopje met labels (en "LET OP! ...") staat tussen de eerste twee <hr>'s en zit al in
    # de velden; alleen de omschrijving erna houden
    delen = re.split(r"<hr\s*/?>", tekst)
    if len(delen) >= 3 and "Aanvraagnummer" in delen[1]:
        tekst = "<hr>".join(delen[2:])
    return BeautifulSoup(tekst, "lxml").get_text(" ", strip=True) or None


def _contractvorm(acf):
    if (acf.get("alleen_detachering") or "").strip().upper() == "JA":
        return "Alleen detachering"
    kop = _label(acf, "Contractvorm").lower()
    if acf.get("zzp_value") or "zzp" in kop:
        return "ZZP mogelijk"
    if acf.get("detachering") or "detachering" in kop:
        return "Alleen detachering"
    return None


def _duur(tekst):
    """'12 maand(en)' -> '12 maanden'; '2 week/weken' -> '2 weken'."""
    m = re.search(r"(\d{1,3})\s*(maand|week|jaar)", tekst or "", re.I)
    if not m:
        return None
    n, e = int(m.group(1)), m.group(2).lower()
    if e == "jaar":
        return f"{n} jaar"
    if e == "week":
        return f"{n} {'week' if n == 1 else 'weken'}"
    return f"{n} {'maand' if n == 1 else 'maanden'}"


def _startdatum(tekst):
    if re.search(r"z\.?\s?s\.?\s?m|zo\s+(?:snel|spoedig)|per\s+direct|asap", tekst or "", re.I):
        return "z.s.m."
    datum = _iso(tekst)
    return datum[:10] if datum else None


def _gesloten(acf, deadline):
    if re.search(r"deze opdracht is gesloten", acf.get("post_content") or "", re.I):
        return True
    if not deadline:
        return False
    nu = datetime.now(NL).strftime("%Y-%m-%dT%H:%M")
    return deadline < nu[:len(deadline)] if "T" not in deadline else deadline <= nu


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
    deadline = _deadline(acf)
    rij = {
        "tender_id": str(post["id"]),
        "nummer": str(acf["identifier_value"]) if acf.get("identifier_value") else None,
        "titel": html.unescape((post.get("title") or {}).get("rendered") or ""),
        "organisatie": acf.get("organisation") or acf.get("hiring_organisation_name"),
        "status": "Gesloten" if _gesloten(acf, deadline) else "Open",
        "deadline": deadline,
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
    try:
        rij["contractvorm"] = _contractvorm(acf)
        rij["duur"] = _duur(_label(acf, "Duur van de opdracht"))
        rij["startdatum"] = _startdatum(_label(acf, "Startdatum"))
        rij["verlenging"] = _label(acf, "Optie tot verlenging") or None
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
