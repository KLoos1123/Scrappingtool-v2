"""Haalt het uurtarief uit de omschrijving van een opdracht.

Alleen ter informatie in het dashboard: er wordt niet op gefilterd of
geprioriteerd. Bron is de omschrijvingentekst (beschrijvingen-tabel); als daar
niets in staat valt het terug op tarief_min/tarief_max uit de AI-verrijking.
"""

import html
import json
import re
import sqlite3

DB = "tenders.db"
MIN_UUR, MAX_UUR = 20, 400   # plausibel uurtarief in euro; daarbuiten is het iets anders
MIN_DAG, MAX_DAG = 200, 2000  # idem voor een dagtarief (Belgische opdrachten)

# Een bedrag: "95", "63,11", "1.250" (duizendtal wordt geweigerd via MAX_UUR).
_BEDRAG = r"(?<![\d.,])(\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?)(?!\d)(?:\s?,-{1,2})?"
_EURO = r"(?:€|eur\b|euro\b)"
_TOT = r"\s*(?:-|–|—|tot(?:\s+max(?:imaal)?)?|t/m|à|a)\s*"
# "€ 70 - € 75", "€70 - 75", "70 - 75 euro"
_BEREIK = re.compile(rf"{_EURO}\s?{_BEDRAG}{_TOT}(?:{_EURO}\s?)?{_BEDRAG}|{_BEDRAG}{_TOT}{_BEDRAG}\s?{_EURO}", re.I)
_ENKEL = re.compile(rf"{_EURO}\s?{_BEDRAG}|{_BEDRAG}\s?{_EURO}", re.I)
# een bedrag telt alleen mee als er een tarief- of uurwoord in de buurt staat
_CONTEXT = re.compile(r"tarief|uurloon|per\s+uur|p/u\b|p\.u\.|/\s?uur|\buur\b|hour|all[- ]in|excl", re.I)
_MAX = re.compile(r"max(?:imaal|imum)?\b|tot\s+max|plafond", re.I)
_PER_DAG = re.compile(r"dagtarief|per\s+dag|/\s?dag\b", re.I)
_MARKTCONFORM = re.compile(r"tarief[^.\n<]{0,25}marktconform|marktconform\w*\s+(?:uur)?tarief", re.I)


def _platte_tekst(tekst):
    t = re.sub(r"<[^>]+>", " ", tekst or "")
    return re.sub(r"\s+", " ", html.unescape(t))


def _getal(s):
    try:
        return float(s.replace(".", "").replace(",", "."))
    except (AttributeError, ValueError):
        return None


def _fmt(x):
    return f"{x:.2f}".replace(".", ",") if x % 1 else f"{int(x)}"


def _omschrijf(lo, hi, maximaal, eenheid="uur"):
    if lo is not None and hi is not None and lo != hi:
        return f"€ {_fmt(lo)} – {_fmt(hi)} /{eenheid}"
    waarde = hi if hi is not None else lo
    return f"{'max ' if maximaal else ''}€ {_fmt(waarde)} /{eenheid}"


def _eenheid(tekst, start, eind):
    """'dag' bij een dagtarief, anders 'uur'; met de bijbehorende grenzen."""
    if _PER_DAG.search(tekst[max(0, start - 40):eind + 25]):
        return "dag", MIN_DAG, MAX_DAG
    return "uur", MIN_UUR, MAX_UUR


def _in_context(tekst, start, eind):
    return bool(_CONTEXT.search(tekst[max(0, start - 90):eind + 40]))


def _resultaat(lo, hi, maximaal, eenheid):
    # min/max alleen voor uurtarieven, zodat de getallen overal hetzelfde betekenen
    per_uur = eenheid == "uur"
    return {"tarief": _omschrijf(lo, hi, maximaal, eenheid),
            "tarief_min": lo if per_uur else None, "tarief_max": hi if per_uur else None}


def haal_tarief(tekst):
    """Geeft {"tarief": "€ 70 – 75 /uur", "tarief_min": 70, "tarief_max": 75}
    of None. "marktconform" zonder bedrag geeft alleen een tekst."""
    t = _platte_tekst(tekst)
    if not t:
        return None

    for m in _BEREIK.finditer(t):
        a, b = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        lo, hi = _getal(a), _getal(b)
        if lo is None or hi is None or not _in_context(t, m.start(), m.end()):
            continue
        eenheid, ondergrens, bovengrens = _eenheid(t, m.start(), m.end())
        if ondergrens <= lo <= hi <= bovengrens:
            return _resultaat(lo, hi, False, eenheid)

    for m in _ENKEL.finditer(t):
        waarde = _getal(m.group(1) or m.group(2))
        if waarde is None or not _in_context(t, m.start(), m.end()):
            continue
        eenheid, ondergrens, bovengrens = _eenheid(t, m.start(), m.end())
        if not (ondergrens <= waarde <= bovengrens):
            continue
        maximaal = bool(_MAX.search(t[max(0, m.start() - 40):m.start()]))
        return _resultaat(None if maximaal else waarde, waarde, maximaal, eenheid)

    if _MARKTCONFORM.search(t):
        return {"tarief": "marktconform", "tarief_min": None, "tarief_max": None}
    return None


def uit_ai(data):
    """Tarief uit een AI-verrijking (dict met tarief_min/tarief_max), of None."""
    lo, hi = (data or {}).get("tarief_min"), (data or {}).get("tarief_max")
    lo = lo if isinstance(lo, (int, float)) and MIN_UUR <= lo <= MAX_UUR else None
    hi = hi if isinstance(hi, (int, float)) and MIN_UUR <= hi <= MAX_UUR else None
    if lo is None and hi is None:
        return None
    if lo is not None and hi is not None and lo > hi:
        lo, hi = hi, lo
    return {"tarief": _omschrijf(lo, hi, False), "tarief_min": lo, "tarief_max": hi}


def verzamel():
    """Tarieven voor alle opdrachten met een omschrijving of AI-verrijking in
    tenders.db. Geeft dicts met bron, tender_id, tarief, tarief_min, tarief_max,
    herkomst ('tekst' of 'ai')."""
    conn = sqlite3.connect(DB)
    uit = {}
    try:
        for bron, tid, data in conn.execute("SELECT bron, tender_id, data FROM verrijkingen"):
            try:
                gevonden = uit_ai(json.loads(data))
            except (TypeError, ValueError):
                gevonden = None
            if gevonden:
                uit[(bron, str(tid))] = {**gevonden, "herkomst": "ai"}
    except sqlite3.OperationalError:
        pass  # tabel bestaat nog niet
    try:
        for bron, tid, oms in conn.execute("SELECT bron, tender_id, omschrijving FROM beschrijvingen"):
            gevonden = haal_tarief(oms)
            # een bedrag uit de tekst wint; "marktconform" alleen als de AI niets vond
            if gevonden and (gevonden["tarief"] != "marktconform" or (bron, str(tid)) not in uit):
                uit[(bron, str(tid))] = {**gevonden, "herkomst": "tekst"}
    except sqlite3.OperationalError:
        pass
    conn.close()
    return [{"bron": b, "tender_id": t, **v} for (b, t), v in uit.items()]


if __name__ == "__main__":
    from collections import Counter
    rijen = verzamel()
    print(f"{len(rijen)} tarieven gevonden")
    print(Counter(r["bron"] for r in rijen).most_common())
