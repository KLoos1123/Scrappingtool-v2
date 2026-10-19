"""Zet datums die bronnen als tekst aanleveren om naar ISO 8601.

Sommige scrapers leveren datums zoals de website ze toont ("28 juli 2026agenda",
"21 okt 2026 07:00 uur", "16-09-2026"). Die kunnen het dashboard en Postgres
niet als datum lezen, waardoor zo'n opdracht als "geen deadline" telde.
"""

import re
from datetime import datetime, date
from zoneinfo import ZoneInfo

NL = ZoneInfo("Europe/Amsterdam")

MAANDEN = {
    "januari": 1, "jan": 1, "februari": 2, "feb": 2, "maart": 3, "mrt": 3, "mar": 3,
    "april": 4, "apr": 4, "mei": 5, "juni": 6, "jun": 6, "juli": 7, "jul": 7,
    "augustus": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "oktober": 10, "okt": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}")
_DMJ = re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{4})(?:\s+(\d{1,2})[:.](\d{2}))?")
_TEKST = re.compile(r"^(\d{1,2})\s+([a-z]+)\.?\s+(\d{4})(?:\s+(\d{1,2})[:.](\d{2}))?")

DATUM_VELDEN = ("deadline", "publicatiedatum")


def normaliseer_datum(waarde):
    """Geeft een ISO-datum terug ("2026-07-28", of met tijd en NL-tijdzone).

    Waarden die al ISO zijn, leeg zijn of niet herkend worden, komen ongewijzigd
    terug, zodat er nooit informatie verloren gaat.
    """
    if not isinstance(waarde, str) or not waarde.strip() or _ISO.match(waarde.strip()):
        return waarde
    tekst = waarde.strip().lower()

    m = _DMJ.match(tekst)
    if m:
        dag, maand, jaar = int(m[1]), int(m[2]), int(m[3])
        uur, minuut = m[4], m[5]
    else:
        m = _TEKST.match(tekst)
        if not m or m[2] not in MAANDEN:
            return waarde
        dag, maand, jaar = int(m[1]), MAANDEN[m[2]], int(m[3])
        uur, minuut = m[4], m[5]

    try:
        if uur is None:
            return date(jaar, maand, dag).isoformat()
        return datetime(jaar, maand, dag, int(uur), int(minuut), tzinfo=NL).isoformat()
    except ValueError:
        return waarde


def normaliseer_rij(rij):
    """Normaliseert de datumvelden van een tender-dict in place."""
    for veld in DATUM_VELDEN:
        if veld in rij:
            rij[veld] = normaliseer_datum(rij[veld])
    return rij
