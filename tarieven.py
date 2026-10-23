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


def uit_bron(rij):
    """Tarief dat de scraper als veld aanlevert (tarief_min/tarief_max per uur), of None."""
    return uit_ai(rij)


# ---------------------------------------------------------------- uren per week

_U = r"(\d{1,2})"
_UTOT = r"\s*(?:-|–|/|tot|à)\s*"
_PER_WEEK = r"\s*(?:uur|uren|u)\b\.?\s*(?:per\s*(?:week|wk)\b|p/w|p\.w\.|/\s*(?:week|wk)\b|in\s+de\s+week\b)"
_UREN_BEREIK = re.compile(_U + _UTOT + _U + _PER_WEEK, re.I)
_UREN_ENKEL = re.compile(r"(?<![\d/-])" + _U + _PER_WEEK, re.I)
# "Uren per week: 32 / 40", "Aantal uur per week: 16", "Uren: 36", "Inzet: 24-32"
_UREN_LABEL = re.compile(r"(?:uren\s+per\s+week|uur\s+per\s+week|aantal\s+uren|uren|inzet|omvang)\s*:\s*"
                         + _U + r"(?:" + _UTOT + _U + r")?(?!\s*(?:maanden|weken|jaar|%|-\d))", re.I)
MIN_UREN, MAX_UREN = 4, 40


def _uren_tekst(lo, hi):
    return f"{lo}–{hi} u/w" if lo != hi else f"{lo} u/w"


def _uren_resultaat(lo, hi):
    lo, hi = int(lo), int(hi if hi is not None else lo)
    if lo > hi:
        lo, hi = hi, lo
    if not (MIN_UREN <= lo <= hi <= MAX_UREN):
        return None
    return {"uren": _uren_tekst(lo, hi), "uren_min": lo, "uren_max": hi}


def haal_uren(tekst):
    """Uren per week uit de omschrijving: {"uren": "32–40 u/w", "uren_min": 32,
    "uren_max": 40} of None."""
    t = _platte_tekst(tekst)
    if not t:
        return None
    for patroon, bereik in ((_UREN_BEREIK, True), (_UREN_ENKEL, False), (_UREN_LABEL, None)):
        for m in patroon.finditer(t):
            if bereik is True:
                uit = _uren_resultaat(m.group(1), m.group(2))
            elif bereik is False:
                uit = _uren_resultaat(m.group(1), None)
            else:
                uit = _uren_resultaat(m.group(1), m.group(2))
            if uit:
                return uit
    return None


def uren_uit_bron(rij):
    """Uren die de scraper als veld meegeeft (freelance.nl: uren_per_week "32-40")."""
    tekst = str(rij.get("uren_per_week") or "")
    if re.match(r"\s*\d{1,2}\s*$", tekst):            # één getal: "36"
        return _uren_resultaat(int(tekst), None)
    m = re.match(r"\s*(\d{1,2}|\?)\s*-\s*(\d{1,2}|\?)\s*$", tekst)
    if not m:
        return None
    lo, hi = (None if x == "?" else x for x in m.groups())
    if lo is None and hi is None:
        return None
    return _uren_resultaat(lo or hi, hi or lo)


def uren_uit_ai(data):
    lo, hi = (data or {}).get("uren_per_week_min"), (data or {}).get("uren_per_week_max")
    lo = lo if isinstance(lo, (int, float)) else None
    hi = hi if isinstance(hi, (int, float)) else None
    if lo is None and hi is None:
        return None
    return _uren_resultaat(lo if lo is not None else hi, hi if hi is not None else lo)


# ---------------------------------------------------------------- kenmerken
# Contractvorm (ZZP/detachering), startdatum, duur en verlenging. Uit velden die
# de scraper meegeeft (bv. De Publieke Partner) of uit een gelabelde regel in de
# omschrijving ("Startdatum: 01-11-2026", "Duur van de opdracht: 12 maand(en)").
# Bewust behoudend: alleen met een duidelijk label of een vaste zinsnede.

_MAANDEN = ["januari", "februari", "maart", "april", "mei", "juni", "juli",
            "augustus", "september", "oktober", "november", "december"]
_DATUM = (r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})"
          r"|(\d{1,2})\s+(" + "|".join(_MAANDEN) + r")\s+(\d{4})"
          r"|(z\.?\s?s\.?\s?m\.?|zo\s+spoedig\s+mogelijk|per\s+direct|direct|asap)")
_START = re.compile(r"(?<![\w-])(?:beoogde\s+)?(?:start(?:datum|moment)?|aanvang(?:sdatum)?|ingangsdatum|begindatum)"
                    r"(?:\s+(?:van\s+de\s+)?opdracht)?\s*[:\-]?\s*(?:" + _DATUM + r")", re.I)
_DUUR = re.compile(r"(?<![\w-])(?:duur(?:\s+van\s+de\s+opdracht)?|looptijd|opdrachtduur|contractduur|periode)"
                   r"\s*(?::|-|van)?\s*(?:circa\s+|ca\.?\s+|minimaal\s+)?(\d{1,2})\s*"
                   r"(maand(?:en|\(en\))?|mnd\.?|weken|week|jaar)\b", re.I)
_VERLENG_LABEL = re.compile(r"(?:optie\s+tot\s+verlenging|verlengingsopties?|verlenging(?:smogelijkheden?)?)"
                            r"\s*:\s*([^\n.;|<]{2,60})", re.I)
_VERLENG_ZIN = re.compile(r"(?:met\s+)?(?:de\s+)?optie\s+(?:tot|op)\s+verlenging", re.I)
_ALLEEN_DETA = re.compile(r"niet\s+open\s+voor\s+zzp|geen\s+zzp|uitsluitend\s+(?:via\s+|op\s+basis\s+van\s+)?detachering"
                          r"|alleen\s+(?:via\s+|op\s+basis\s+van\s+)?detachering|niet\s+(?:geschikt|mogelijk)\s+voor\s+zzp", re.I)
_ZZP_OK = re.compile(r"(?:ook\s+)?(?:open|mogelijk)\s+voor\s+zzp|zzp['’]?ers?\s+(?:zijn\s+)?(?:van\s+harte\s+)?welkom"
                     r"|zzp\s*(?:of|/|en)\s*detachering|detachering\s*(?:of|/|en)\s*zzp", re.I)


def _start(m):
    if m.group(1):
        dag, maand, jaar = int(m.group(1)), int(m.group(2)), int(m.group(3))
        jaar += 2000 if jaar < 100 else 0
    elif m.group(4):
        dag, maand, jaar = int(m.group(4)), _MAANDEN.index(m.group(5).lower()) + 1, int(m.group(6))
    else:
        return "z.s.m."
    if not (1 <= dag <= 31 and 1 <= maand <= 12 and 2020 <= jaar <= 2035):
        return None
    return f"{jaar}-{maand:02d}-{dag:02d}"


def _duur(n, eenheid):
    n, e = int(n), eenheid.lower()
    if n <= 0:
        return None
    if e.startswith("w"):
        return f"{n} {'week' if n == 1 else 'weken'}"
    if e.startswith("j"):
        return f"{n} jaar"
    return f"{n} {'maand' if n == 1 else 'maanden'}"


def contractvorm(tekst):
    """'Alleen detachering', 'ZZP mogelijk' of None, uit een veld of zin."""
    t = _platte_tekst(tekst)
    if not t:
        return None
    if _ALLEEN_DETA.search(t):
        return "Alleen detachering"
    m = re.search(r"zzp\s+mogelijk\s*:\s*(ja|nee)\b", t, re.I)
    if m:
        return "ZZP mogelijk" if m.group(1).lower() == "ja" else "Alleen detachering"
    # "Contractvorm: Detachering ZZP" (meerdere labels achter elkaar)
    m = re.search(r"contractvorm\s*:\s*((?:(?:zzp|detachering|loondienst|inhuur|freelance|interim)[\s,/&]*(?:of|en)?\s*)+)", t, re.I)
    if m:
        v = m.group(1).lower()
        if "zzp" in v or "freelance" in v or "interim" in v:
            return "ZZP mogelijk"
        if "detachering" in v:
            return "Alleen detachering"
        if "loondienst" in v:
            return "Loondienst"
    if _ZZP_OK.search(t):
        return "ZZP mogelijk"
    return None


def haal_kenmerken(tekst):
    """Kenmerken uit de omschrijving: dict met contractvorm, startdatum, duur,
    verlenging (alleen de gevonden sleutels)."""
    t = _platte_tekst(tekst)
    if not t:
        return {}
    uit = {}
    for m in _START.finditer(t):
        start = _start(m)
        if start:
            uit["startdatum"] = start
            break
    m = _DUUR.search(t)
    if m:
        duur = _duur(m.group(1), m.group(2))
        if duur:
            uit["duur"] = duur
    m = _VERLENG_LABEL.search(t)
    if m:
        # tekst is platgeslagen: stop bij het volgende label ("Sluitingsdatum: ...")
        waarde = re.split(r"\s+(?=[A-Z][A-Za-zé ]{2,30}\s*:)|\s+LET OP", m.group(1))[0].strip(" ,:-")
        if re.match(r"[A-Z][A-Za-zé ]{2,30}\s*:", waarde):
            waarde = ""   # label zonder waarde, meteen gevolgd door het volgende label
        if re.match(r"(?:nee|geen)\b", waarde, re.I):
            uit["verlenging"] = "Nee"
        elif re.match(r"ja\b", waarde, re.I):
            uit["verlenging"] = "Ja"
        elif waarde:
            uit["verlenging"] = waarde[0].upper() + waarde[1:]
    elif _VERLENG_ZIN.search(t):
        uit["verlenging"] = "Mogelijk"
    vorm = contractvorm(t)
    if vorm:
        uit["contractvorm"] = vorm
    return uit


KENMERKEN = ("contractvorm", "startdatum", "duur", "verlenging")


def kenmerken_uit_bron(rij):
    """Kenmerken die de scraper als veld meegeeft (zelfde sleutels)."""
    return {k: rij[k] for k in KENMERKEN if rij.get(k)}


def verzamel(rijen=()):
    """Tarief en uren per week voor alle opdrachten met een omschrijving of
    AI-verrijking in tenders.db, plus de rijen van deze run die het zelf als veld
    meegeven (zoals freelance.nl). Geeft dicts met bron, tender_id, tarief,
    tarief_min, tarief_max, herkomst ('bron', 'tekst' of 'ai'; van het tarief) en
    uren, uren_min, uren_max. Tarief of uren kan ontbreken (None)."""
    conn = sqlite3.connect(DB)
    tarief, uren, kenm = {}, {}, {}
    try:
        for bron, tid, data in conn.execute("SELECT bron, tender_id, data FROM verrijkingen"):
            try:
                d = json.loads(data)
            except (TypeError, ValueError):
                continue
            if uit_ai(d):
                tarief[(bron, str(tid))] = {**uit_ai(d), "herkomst": "ai"}
            if uren_uit_ai(d):
                uren[(bron, str(tid))] = uren_uit_ai(d)
    except sqlite3.OperationalError:
        pass  # tabel bestaat nog niet
    try:
        for bron, tid, oms in conn.execute("SELECT bron, tender_id, omschrijving FROM beschrijvingen"):
            k = (bron, str(tid))
            gevonden = haal_tarief(oms)
            # een bedrag uit de tekst wint; "marktconform" alleen als de AI niets vond
            if gevonden and (gevonden["tarief"] != "marktconform" or k not in tarief):
                tarief[k] = {**gevonden, "herkomst": "tekst"}
            u = haal_uren(oms)
            if u:
                uren[k] = u
            gevonden_k = haal_kenmerken(oms)
            if gevonden_k:
                kenm[k] = gevonden_k
    except sqlite3.OperationalError:
        pass
    conn.close()
    # velden van de bron zelf zijn het betrouwbaarst en winnen altijd
    for r in rijen:
        if not r.get("bron") or r.get("tender_id") is None:
            continue
        k = (r["bron"], str(r["tender_id"]))
        if uit_bron(r):
            tarief[k] = {**uit_bron(r), "herkomst": "bron"}
        if uren_uit_bron(r):
            uren[k] = uren_uit_bron(r)
        if kenmerken_uit_bron(r):
            kenm[k] = {**kenm.get(k, {}), **kenmerken_uit_bron(r)}
    leeg_t = {"tarief": None, "tarief_min": None, "tarief_max": None, "herkomst": None}
    leeg_u = {"uren": None, "uren_min": None, "uren_max": None}
    leeg_k = {k: None for k in KENMERKEN}
    return [{"bron": b, "tender_id": t, **tarief.get((b, t), leeg_t), **uren.get((b, t), leeg_u),
             **leeg_k, **kenm.get((b, t), {})}
            for (b, t) in sorted(set(tarief) | set(uren) | set(kenm))]


if __name__ == "__main__":
    from collections import Counter
    rijen = verzamel()
    print(f"{sum(1 for r in rijen if r['tarief'])} tarieven, {sum(1 for r in rijen if r['uren'])} met uren")
    for k in KENMERKEN:
        print(f"  {k}: {sum(1 for r in rijen if r[k])}")
    print(Counter(r["bron"] for r in rijen).most_common())
