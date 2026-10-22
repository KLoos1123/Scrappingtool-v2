"""Haalt een deadline uit de omschrijving van een opdracht.

Terugval voor bronnen die de deadline niet als veld aanleveren maar wel in de
tekst zetten ("Deadline: 13-08-2026", "Sluitingsdatum: woensdag 5 augustus
2026 om 12.00 uur", "Deadline voor het voorstellen van kandidaten: 26-7 16 uur").
run.py vult hiermee alleen een lege deadline; een deadline uit de bron wint altijd.
"""

import html
import re
from datetime import date, datetime, timedelta

from datums import MAANDEN

# Woorden waarna een deadline volgt. "deadline" alleen als kopje: "harde deadline
# rond de jaarwisseling" telt niet, "Deadline:", "Deadline 8 aug." en "Deadline
# inschrijven:" wel.
_SLEUTEL = re.compile(
    r"\bdeadline\b(?=\s*(?:[:\-–]|\d|voor\b|inschrijv|indien|aanbied|reacties?\b|cv))"
    r"|\bsluitings?(?:datum|termijn)\b"
    r"|\breageren\s+(?:kan\s+)?(?:tot(?:\s+en\s+met)?|t/m|vóór|voor|uiterlijk)"
    r"|\buiterlijk\s+(?:reageren|aanbieden|inschrijven|indienen)\b"
    r"|\breactietermijn\b"
    r"|\b(?:aanbieden|inschrijven|indienen)\s+(?:tot(?:\s+en\s+met)?|t/m|vóór|voor|uiterlijk)",
    re.I)
VENSTER = 70  # zoveel tekens na het sleutelwoord zoeken we naar een datum

_MAAND = "|".join(sorted(MAANDEN, key=len, reverse=True))
_VOLLEDIG = re.compile(r"(?<!\d)(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})(?!\d)")
_TEKST = re.compile(rf"(?<!\d)(\d{{1,2}})\s+({_MAAND})\.?(?:\s+(\d{{4}}))?\b", re.I)
# "10-08", "26-7", "05-08" zonder jaar; geen tijd ("16:00") of urenbereik ("32-40")
_KORT = re.compile(r"(?<![\d:.])(\d{1,2})[-/](\d{1,2})(?![\d:/-])")


def _platte_tekst(tekst):
    t = re.sub(r"<[^>]+>", " ", tekst or "")
    return re.sub(r"\s+", " ", html.unescape(t))


def _met_jaar(dag, maand, referentie):
    """Zonder jaartal: het eerstvolgende moment na de referentiedatum (met een
    week speling, want een deadline ligt nooit ver voor de publicatie)."""
    for jaar in (referentie.year, referentie.year + 1):
        try:
            d = date(jaar, maand, dag)
        except ValueError:
            return None
        if d >= referentie - timedelta(days=7):
            return d
    return None


def _datum_in(stuk, referentie):
    m = _VOLLEDIG.search(stuk)
    if m:
        try:
            return date(int(m[3]), int(m[2]), int(m[1]))
        except ValueError:
            return None
    m = _TEKST.search(stuk)
    if m:
        dag, maand = int(m[1]), MAANDEN[m[2].lower()]
        if m[3]:
            try:
                return date(int(m[3]), maand, dag)
            except ValueError:
                return None
        return _met_jaar(dag, maand, referentie)
    m = _KORT.search(stuk)
    if m and 1 <= int(m[2]) <= 12:
        return _met_jaar(int(m[1]), int(m[2]), referentie)
    return None


def _referentie(waarde):
    if isinstance(waarde, date):
        return waarde if not isinstance(waarde, datetime) else waarde.date()
    if isinstance(waarde, str) and re.match(r"\d{4}-\d{2}-\d{2}", waarde):
        return date.fromisoformat(waarde[:10])
    return date.today()


def haal_deadline(tekst, referentie=None):
    """Geeft de deadline als ISO-datum ("2026-08-13") of None.

    referentie: publicatiedatum (ISO-string of date) om een datum zonder
    jaartal in het juiste jaar te plaatsen; standaard vandaag.
    """
    t = _platte_tekst(tekst)
    if not t:
        return None
    ref = _referentie(referentie)
    for m in _SLEUTEL.finditer(t):
        d = _datum_in(t[m.end():m.end() + VENSTER], ref)
        # een "deadline" jaren voor of na de publicatie is iets anders (projecteinde, wetgeving)
        if d and ref - timedelta(days=60) <= d <= ref + timedelta(days=400):
            return d.isoformat()
    return None


def vul_aan(rijen):
    """Vult in place de deadline van rijen zonder deadline maar met een
    omschrijving. Geeft het aantal aangevulde rijen terug."""
    n = 0
    for r in rijen:
        if r.get("deadline") or not r.get("omschrijving"):
            continue
        d = haal_deadline(r["omschrijving"], r.get("publicatiedatum"))
        if d:
            r["deadline"] = d
            n += 1
    return n
