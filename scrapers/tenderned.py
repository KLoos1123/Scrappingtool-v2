"""TenderNed - aanbestedingen via de open publicatie-API (papi).

Publieke JSON-API, geen login nodig. De API is gesorteerd op nieuwste eerst;
we halen de publicaties van de laatste weken op (gepagineerd) zodat de focus
op nieuwe leads ligt. Dedup op (bron, tender_id) bouwt vanzelf historie op
over runs heen.

De lijst geeft `sluitingsDatum` (inschrijven) en voor marktconsultaties soms
`sluitingsDatumMarktconsultatie`. Vooraankondigingen die als oproep tot
mededinging dienen (eForms 10-14) en marktconsultaties zonder lijstdatum hebben
hun termijn alleen in de eForms-notitie; de JSON-detail heeft hem niet en de
XML is niet openbaar (403), dus voor die paar rijen lezen we de PDF.
Gegund, wijziging, beëindiging en informatieve vooraankondigingen hebben
geen termijn.

De lijst geeft ook `opdrachtBeschrijving` (de omschrijving). De plaats van
uitvoering staat alleen als NUTS-code in de detail-JSON; ~1800 detailcalls per
run is te traag, maar de lijst-API filtert op `nutsCodes` (hiërarchisch, NL35
geeft ook NL350). We vragen dus per provincie de id's op (12 kleine queries)
en zetten de provincienaam als locatie. Ruim de helft heeft alleen code "NL"
(heel Nederland); die houden locatie None.
"""

import io
import re
import requests
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

try:
    from pypdf import PdfReader
except ImportError:  # zonder pypdf alleen de lijstdatums
    PdfReader = None

BRON = "tenderned"

API = "https://www.tenderned.nl/papi/tenderned-rs-tns/v2/publicaties"
DETAIL = "https://www.tenderned.nl/aankondigingen/overzicht"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

DAGEN_TERUG = 21
BLOK = 100
MAX_PAGINA = 300  # veiligheidsgrens

NL = ZoneInfo("Europe/Amsterdam")
PDF = API + "/{}/pdf"
PDF_WERKERS = 4
# eForms-codes waarvan de termijn alleen in de PDF staat (ook bij rectificaties
# met die code): oproep via vooraankondiging, marktconsultatie, lichte regeling
PDF_CODES = {"EF10", "EF11", "EF12", "EF13", "EF14", "EFE1",
             "EF16", "EF17", "EF18", "EF19", "EF20", "EF21", "EF22", "EF23", "EF24"}
# NUTS-2 (indeling 2024: Utrecht en Zuid-Holland zijn NL35/NL36, niet NL31/NL33)
PROVINCIES = {
    "NL11": "Groningen", "NL12": "Friesland", "NL13": "Drenthe",
    "NL21": "Overijssel", "NL22": "Gelderland", "NL23": "Flevoland",
    "NL32": "Noord-Holland", "NL34": "Zeeland", "NL35": "Utrecht",
    "NL36": "Zuid-Holland", "NL41": "Noord-Brabant", "NL42": "Limburg",
}
_TERMIJN = re.compile(
    r"(?:Uiterste datum voor (?:de )?ontvangst[^:]{0,80}|Termijn (?:voor )?(?:de )?ontvangst[^:]{0,60}):"
    r"\s*(\d{2})/(\d{2})/(\d{4})\s+(\d{2}):(\d{2})\s*([+-]\d{2}):(\d{2})")


def _oms(v):
    return (v or {}).get("omschrijving")


def _beschrijving(tekst):
    """opdrachtBeschrijving, maar None voor lege of nietszeggende waarden ("-")."""
    tekst = (tekst or "").strip()
    return tekst if re.search(r"[^\W\d_]{3}", tekst) else None


def _uit_publicatie(p):
    pid = p.get("publicatieId")
    return {
        "tender_id": str(pid),
        "nummer": str(p.get("kenmerk")) if p.get("kenmerk") else None,
        "titel": p.get("aanbestedingNaam"),
        "organisatie": p.get("opdrachtgeverNaam"),
        "status": _oms(p.get("publicatiestatus")),
        "deadline": p.get("sluitingsDatum") or p.get("sluitingsDatumMarktconsultatie"),
        "publicatiedatum": p.get("publicatieDatum"),
        "locatie": None,
        "omschrijving": _beschrijving(p.get("opdrachtBeschrijving")),
        "type_opdracht": _oms(p.get("typeOpdracht")),
        "procedure": _oms(p.get("procedure")),
        "type_publicatie": _oms(p.get("typePublicatie")),
        "url": f"{DETAIL}/{pid}",
    }


def _termijn_uit_pdf(sessie, pid):
    """Eerste termijn (blijken van belangstelling / antwoorden) uit de PDF, in NL-tijd."""
    try:
        r = sessie.get(PDF.format(pid), headers={"user-agent": UA}, timeout=30)
        r.raise_for_status()
        tekst = " ".join(pg.extract_text() or "" for pg in PdfReader(io.BytesIO(r.content)).pages)
    except Exception:
        return None
    m = _TERMIJN.search(re.sub(r"\s+", " ", tekst))
    if not m:
        return None
    d, mnd, j, u, mi, tz_u, tz_m = (int(x) for x in m.groups())
    tz = timezone(timedelta(hours=tz_u, minutes=tz_m if tz_u >= 0 else -tz_m))
    return datetime(j, mnd, d, u, mi, tzinfo=tz).astimezone(NL).isoformat()


def _vul_termijnen(sessie, rijen, codes):
    """Haalt voor rijen zonder deadline met een PDF_CODES-code de termijn uit de PDF."""
    open_ = [r for r in rijen if not r["deadline"] and codes.get(r["tender_id"]) in PDF_CODES]
    if not open_ or PdfReader is None:
        return
    with ThreadPoolExecutor(PDF_WERKERS) as pool:
        termijnen = list(pool.map(lambda r: _termijn_uit_pdf(sessie, r["tender_id"]), open_))
    gevonden = 0
    for rij, t in zip(open_, termijnen):
        if t:
            rij["deadline"] = t
            gevonden += 1
    print(f"  termijn uit PDF: {gevonden} van {len(open_)}")


def _ids_per_provincie(sessie, headers, cutoff, code):
    """Publicatie-id's in het venster met (een deel van) deze NUTS-regio."""
    ids, pagina = set(), 0
    while pagina < MAX_PAGINA:
        r = sessie.get(
            API,
            params={"page": pagina, "size": BLOK, "publicatieDatumVanaf": cutoff, "nutsCodes": code},
            headers=headers,
            timeout=45,
        )
        r.raise_for_status()
        data = r.json()
        content = data.get("content") or []
        ids |= {str(p["publicatieId"]) for p in content if p.get("publicatieId")}
        if data.get("last") or not content:
            break
        pagina += 1
    return ids


def _vul_locaties(sessie, headers, cutoff, rijen):
    """Zet de provincie(s) van uitvoering als locatie; fouten negeren we."""
    def per_code(code):
        try:
            return _ids_per_provincie(sessie, headers, cutoff, code)
        except Exception:
            return set()
    with ThreadPoolExecutor(PDF_WERKERS) as pool:
        ids = dict(zip(PROVINCIES, pool.map(per_code, PROVINCIES)))
    for rij in rijen:
        namen = [naam for code, naam in PROVINCIES.items() if rij["tender_id"] in ids[code]]
        rij["locatie"] = ", ".join(namen) or None
    print(f"  locatie (provincie): {sum(1 for r in rijen if r['locatie'])} van {len(rijen)}")


def haal_op():
    """Wordt aangeroepen door run.py. Geeft een lijst dicts terug."""
    sessie = requests.Session()
    headers = {"user-agent": UA, "accept": "application/json"}
    cutoff = (datetime.now(timezone.utc) - timedelta(days=DAGEN_TERUG)).strftime("%Y-%m-%d")

    rijen = []
    codes = {}  # tender_id -> eForms-code, voor de PDF-aanvulling
    pagina = 0
    totaal = None

    while pagina < MAX_PAGINA:
        r = sessie.get(
            API,
            params={"page": pagina, "size": BLOK, "publicatieDatumVanaf": cutoff},
            headers=headers,
            timeout=45,
        )
        r.raise_for_status()
        data = r.json()

        if totaal is None:
            totaal = data.get("totalElements")
            print(f"  venster vanaf {cutoff}, {totaal} publicaties gemeld")

        content = data.get("content") or []
        if not content:
            break

        # nieuwste-eerst: stop zodra we voorbij het venster zijn
        te_oud = False
        for p in content:
            pd = p.get("publicatieDatum") or ""
            if pd and pd < cutoff:
                te_oud = True
                continue
            if p.get("publicatieId"):
                rijen.append(_uit_publicatie(p))
                codes[str(p["publicatieId"])] = (p.get("publicatiecode") or {}).get("code")

        if data.get("last") or te_oud:
            break
        pagina += 1

    _vul_termijnen(sessie, rijen, codes)
    _vul_locaties(sessie, headers, cutoff, rijen)
    oms = sum(1 for r in rijen if r["omschrijving"])
    print(f"  {len(rijen)} publicaties opgehaald, {oms} met omschrijving")
    return rijen
