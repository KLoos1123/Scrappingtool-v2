"""Flextender.

Geen login nodig: de opdrachtenlijst is publiek. De pagina bevat een
verborgen widget-token (kbs_flx_widget_config) dat je meestuurt naar
de zoek-endpoint van de website (wp-admin/admin-ajax.php). Die endpoint
geeft in één keer een HTML-blob terug met ALLE opdrachten (de "paginas"
in de UI zijn alleen CSS-hidden divs, geen aparte requests).

De kaart heeft een veld Regio (provincie): dat wordt ook de locatie; een
fijnere plaats staat nergens. De omschrijving staat niet in de lijst. De
detailpagina is traag (~2 s) en geeft bij een deel van de opdrachten vast een
serverfout, maar de PDF-export (app.flextender.nl/nologin/jobtopdf/<nr>) werkt
voor alles en kost ~0,2 s per opdracht met 4 werkers. Het standaardblok
"Uitvoeringsvoorwaarde" (Wet DBA) laten we weg: overal gelijk en het zou de
helft van de 4000 tekens opslag opeten.
"""

import io
import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

try:
    from pypdf import PdfReader
except ImportError:  # zonder pypdf geen omschrijving
    PdfReader = None

BRON = "flextender"

PAGE_URL = "https://www.flextender.nl/opdrachten/"
AJAX_URL = "https://www.flextender.nl/wp-admin/admin-ajax.php"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

PDF_URL = "https://app.flextender.nl/nologin/jobtopdf/{}"
WERKERS = 4


# ---------------------------------------------------------------- token

def _token(sessie):
    r = sessie.get(PAGE_URL, headers={"user-agent": UA}, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "lxml")
    veld = soup.find("input", {"name": "kbs_flx_widget_config"})
    if not veld or not veld.get("value"):
        raise RuntimeError("kbs_flx_widget_config niet gevonden op de pagina")
    return veld["value"]


# ---------------------------------------------------------------- ophalen

def _zoek(sessie, token, zoekterm=""):
    payload = {
        "kbs_flx_widget_config": token,
        "action": "kbs_flx_searchjobs",
        "kbs_flx_joblsrc_freetext": zoekterm,
        "StackOverflow1370021": "Fix autosubmit bug",
        "_charset_": "UTF-8",
    }
    r = sessie.post(AJAX_URL, data=payload, headers={"user-agent": UA}, timeout=60)
    r.raise_for_status()
    data = r.json()
    return data.get("resultHtml", "")


# ---------------------------------------------------------------- normaliseren

def _tekst(el):
    return el.get_text(strip=True) if el else None


def _samenvattingsveld(kaart, label):
    """Zoekt een css-summaryrow met de gegeven caption en geeft de waarde terug."""
    for rij in kaart.select(".css-summaryrow"):
        caption = rij.select_one(".css-caption")
        if caption and caption.get_text(strip=True) == label:
            return _tekst(rij.select_one(".css-value"))
    return None


def _uit_kaart(kaart):
    url = kaart.get("data-kbslinkurl")
    aanvraagnr = _samenvattingsveld(kaart, "Aanvraagnummer")
    tid = aanvraagnr or (re.search(r"aanvraagnr=(\d+)", url or "").group(1) if url else None)

    return {
        "tender_id": str(tid) if tid else None,
        "nummer": aanvraagnr,
        "titel": _tekst(kaart.select_one(".css-jobtitle")),
        "organisatie": _tekst(kaart.select_one(".css-customer")),
        "status": "Open",
        "deadline": _samenvattingsveld(kaart, "Einde inschrijfdatum"),
        "publicatiedatum": None,
        "start": _samenvattingsveld(kaart, "Start"),
        "duur": _samenvattingsveld(kaart, "Duur"),
        "uren_per_week": _samenvattingsveld(kaart, "Uren per week"),
        "regio": _samenvattingsveld(kaart, "Regio"),
        "locatie": _samenvattingsveld(kaart, "Regio"),
        "omschrijving": None,
        "opleidingsniveau": _samenvattingsveld(kaart, "Opleidingsniveau"),
        "url": url,
    }


# ---------------------------------------------------------------- detail

# het DBA-standaardblok; de slotzin staat soms met, soms zonder punt
_DBA = re.compile(r"Uitvoeringsvoorwaarde\b.{0,2500}?uit de\s+inschrijving\s+blijkt\.?", re.S)


def _omschrijving(tekst):
    """Omschrijving uit de PDF-tekst: kopregels (tot en met Eindtijd) en het
    DBA-standaardblok eruit, afgebroken regels weer aan elkaar."""
    regels = tekst.replace("\xa0", " ").splitlines()
    kop = next((i for i, r in enumerate(regels[:20]) if r.startswith("Eindtijd")), -1)
    regels = _DBA.sub("", "\n".join(regels[kop + 1:]), count=1).splitlines()
    uit = []
    for r in regels:
        r = re.sub(r"^\? ", "- ", r.strip())  # opsommingstekens komen als "?" uit de PDF
        if not r:
            continue
        if uit and len(uit[-1]) >= 80:  # PDF breekt rond 110 tekens af
            uit[-1] += " " + r
        else:
            uit.append(r)
    return "\n".join(uit) or None


def _vul_omschrijving(sessie, rij):
    """Haalt de PDF van de opdracht op; fouten negeren we (omschrijving blijft None)."""
    try:
        r = sessie.get(PDF_URL.format(rij["tender_id"]), headers={"user-agent": UA}, timeout=30)
        r.raise_for_status()
        tekst = "\n".join(pg.extract_text() or "" for pg in PdfReader(io.BytesIO(r.content)).pages)
        rij["omschrijving"] = _omschrijving(tekst)
    except Exception:
        pass


# ---------------------------------------------------------------- publiek

def haal_op():
    """Wordt aangeroepen door run.py. Geeft een lijst dicts terug."""
    sessie = requests.Session()

    token = _token(sessie)
    print("  token opgehaald")

    html = _zoek(sessie, token)
    soup = BeautifulSoup(html, "lxml")
    kaarten = soup.select(".css-foundjob")
    print(f"  {len(kaarten)} opdrachten gevonden")

    rijen = [_uit_kaart(k) for k in kaarten]
    rijen = [r for r in rijen if r["tender_id"]]

    if PdfReader is not None:
        with ThreadPoolExecutor(WERKERS) as pool:
            list(pool.map(lambda r: _vul_omschrijving(sessie, r), rijen))
    print(f"  {sum(1 for r in rijen if r['omschrijving'])} met omschrijving")

    return rijen

