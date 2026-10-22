"""Quest4 - IT/ICT-opdrachten (vooral rijksoverheid) via bemiddelaar Quest4.

Publieke WordPress-site, geen login nodig. De lijst op /it-en-ict-opdrachten/
komt uit de 'blokkenmodule' (admin-ajax.php?action=getblocks) en bevat alleen
de openstaande opdrachten. De WP REST API (/wp-json/wp/v2/opdracht) bevat ook
alle verlopen opdrachten (ruim 11.000), dus die gebruiken we alleen om de
volledige tekst op te halen van de id's uit de lijst (?include=...).
Per opdracht staat een <dl> met standplaats, aanvraagnummer, uren, tarief en
sluitingsdatum in de content.
"""

import html
import json
import re

import requests
from bs4 import BeautifulSoup

BRON = "quest4"

APP = "https://quest4.nl"
LIJST = f"{APP}/it-en-ict-opdrachten/"
AJAX = f"{APP}/wp-admin/admin-ajax.php"
API = f"{APP}/wp-json/wp/v2/opdracht"
# SiteGround weigert (403) python-requests en verouderde Chrome-UA's zoals de
# Chrome/120-string van de andere scrapers; een eerlijke eigen UA mag wel.
UA = "ProfourceDashboard/1.0 (+https://profource.com)"

BLOK = 100       # max per_page van de REST API
MAX_PAGINA = 20  # veiligheidsgrens voor de lijst (24 per pagina)

# fallback als de ajaxdata niet (meer) in de pagina staat
AJAXDATA = {
    "id": "opdrachten", "action": "getblocks", "load_from": "opdracht",
    "orderby": "date", "order": "DESC", "pagesize": 24, "headertag": "h3",
    "layout": "blog_custom", "excerptlength": 45,
}


def _ids(html_tekst):
    return re.findall(r'id="post-(\d+)"', html_tekst or "")


def _lijst_ids(sessie):
    """Id's van de openstaande opdrachten, in de volgorde van de site."""
    r = sessie.get(LIJST, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")

    ul = soup.select_one("#blocks_opdrachten ul[data-ajaxdata]")
    ajaxdata = dict(AJAXDATA)
    paginas = 1
    if ul:
        try:
            ajaxdata = json.loads(ul["data-ajaxdata"])
        except Exception:
            pass
        try:
            paginas = int(ul.get("data-pages") or 1)
        except ValueError:
            pass
        ids = _ids(str(ul))
    else:
        ids = _ids(r.text)

    # volgende pagina's zoals de 'Load more'-knop ze ophaalt
    for pagina in range(2, min(paginas, MAX_PAGINA) + 1):
        params = dict(ajaxdata, paged=pagina, tax="", text="")
        try:
            r = sessie.get(AJAX, params=params, timeout=30)
            r.raise_for_status()
            ids.extend(_ids(r.json().get("html")))
        except Exception as e:
            print(f"  pagina {pagina} van de lijst mislukt: {e}")
            break

    return list(dict.fromkeys(ids))  # dedup, volgorde behouden


def _velden(soup):
    """De <dl> met 'Standplaats:', 'Aanvraagnummer:', ... als dict."""
    velden = {}
    for dt in soup.select("dt"):
        dd = dt.find_next_sibling("dd")
        if dd:
            sleutel = dt.get_text(strip=True).rstrip(":").lower()
            velden[sleutel] = dd.get_text(" ", strip=True)
    return velden


def _iso(tekst):
    """'27-10-2026 09:00' -> '2026-10-27T09:00'."""
    m = re.search(r"(\d{1,2})-(\d{1,2})-(\d{4})(?:\s+(\d{1,2}):(\d{2}))?", tekst or "")
    if not m:
        return tekst or None
    dag, maand, jaar, uur, minuut = m.groups()
    datum = f"{jaar}-{int(maand):02d}-{int(dag):02d}"
    if uur:
        datum += f"T{int(uur):02d}:{minuut}"
    return datum


def _uren(tekst):
    """'36' / '32 - 36 uur' -> '36' / '32-36'."""
    getallen = re.findall(r"\d+", tekst or "")
    return "-".join(getallen[:2]) if getallen else None


def _tarief(tekst):
    """'€ 95 - € 110' -> (95, 110); 'n.o.t.k.' -> (None, None)."""
    getallen = [int(g) for g in re.findall(r"\b\d{2,3}\b", (tekst or "").replace(".", ""))]
    getallen = [g for g in getallen if 20 <= g <= 400]
    if not getallen:
        return None, None
    return min(getallen), max(getallen)


def _uit_post(post):
    soup = BeautifulSoup((post.get("content") or {}).get("rendered") or "", "lxml")
    velden = _velden(soup)

    titel = html.unescape((post.get("title") or {}).get("rendered") or "")
    locatie = velden.get("standplaats")
    if not locatie and " | " in titel:
        locatie = titel.rsplit(" | ", 1)[1]

    # sluitingsdatum uit de <dl>, anders uit de excerpt-lijst
    deadline = velden.get("sluitingsdatum aanvraag")
    if not deadline:
        m = re.search(r"Sluitingsdatum:\s*([^<]+)", (post.get("excerpt") or {}).get("rendered") or "")
        deadline = m.group(1) if m else None

    rij = {
        "tender_id": str(post["id"]),
        "nummer": velden.get("aanvraagnummer"),
        "titel": titel,
        # Quest4 noemt zichzelf als opdrachtgever; de eindklant staat hooguit in de tekst
        "organisatie": velden.get("opdrachtgever") or "Quest4",
        "status": "Open",
        "deadline": _iso(deadline),
        "publicatiedatum": post.get("date"),
        "locatie": locatie,
        "omschrijving": soup.get_text(" ", strip=True) or None,
        "url": post.get("link"),
    }

    # extra's: mogen de rij nooit breken
    try:
        rij["uren_per_week"] = _uren(velden.get("aantal uur per week"))
        tmin, tmax = _tarief(velden.get("indicatie uurtarief"))
        if tmin:
            rij["tarief_min"], rij["tarief_max"] = tmin, tmax
    except Exception:
        pass
    return rij


def haal_op():
    """Wordt aangeroepen door run.py. Geeft een lijst dicts terug."""
    sessie = requests.Session()
    sessie.headers.update({"user-agent": UA})

    ids = _lijst_ids(sessie)
    print(f"  {len(ids)} openstaande opdrachten in de lijst")

    # volledige tekst via de REST API, in blokken van 100 id's
    posts = {}
    for i in range(0, len(ids), BLOK):
        deel = ids[i:i + BLOK]
        r = sessie.get(API, params={
            "include": ",".join(deel),
            "per_page": BLOK,
            "_fields": "id,date,link,title,content,excerpt",
        }, timeout=30)
        r.raise_for_status()
        for post in r.json():
            posts[str(post.get("id"))] = post

    rijen = [_uit_post(posts[i]) for i in ids if i in posts]
    print(f"  {len(rijen)} opdrachten opgehaald")
    return rijen
