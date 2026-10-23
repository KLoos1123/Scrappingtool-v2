"""Dezelfde opdracht bij meerdere bronnen herkennen.

Zelfde logica als groepeerDubbel in web/marktlogica.js (titel zonder ruis,
organisatie, deadlines hooguit 7 dagen uit elkaar). Er wordt niets weggehaald:
elke bron houdt zijn eigen regel. Per regel komt erbij op welke andere bronnen
dezelfde opdracht staat (ook_op), zodat je dat bij iedere bron ziet. Gaat met
de tarieven en kenmerken naar de tabel tarieven (zie tarieven.py).
"""

import hashlib
import json
import re
import sqlite3
from datetime import datetime, timedelta, timezone

DB = "tenders.db"
ACTIEF_DAGEN = 2     # alleen opdrachten die de laatste dagen nog gezien zijn
DEADLINE_MARGE = timedelta(days=7)

# gelijk aan BUREAUS in web/marktlogica.js
BUREAUS = ['striive', 'magnit', 'flextender', 'harvey nash', 'yacht', 'brunel', 'hays', 'headfirst', 'myler',
           'between', 'sthree', 'experis', 'modis', 'randstad', 'usg', 'tempo team', 'olympia', 'manpower',
           'adecco', 'start people', 'young capital', 'circle8', 'bergler', 'ordina', 'conclusion', 'centric',
           'cgi', 'capgemini', 'sopra steria', 'atos', 'accenture', 'deloitte', 'kpmg', 'pwc', 'info support',
           'ilionx', 'valid', 'quintor', 'devoteam', 'profource', 'freelance', 'detach', 'consultancy',
           'consultants', 'interim', 'recruit', 'payroll', 'staffing', 'uitzend', 'flexkracht', 'sourcing']
_RUIS = re.compile(r"\b(tk\d?|m/v(/x)?|v/m|h/v|zzp|zzp'er|freelance|freelancer|interim|inhuur|opdracht|vacature|gezocht)\b")


def titel_sleutel(titel):
    t = str(titel or "").lower()
    t = re.sub(r"\(.*?\)", " ", t)
    t = re.sub(r"\b[a-z]{0,4}\d[\w./-]*\b", " ", t)
    t = _RUIS.sub(" ", t)
    t = re.sub(r"[^a-zà-ÿ ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _is_bureau(org_l):
    if not org_l or org_l == "-" or re.search(r"unknown|onbekend", org_l):
        return True
    return any(b in org_l for b in BUREAUS)


def org_sleutel(rij):
    o = str(rij.get("organisatie") or "").lower().strip()
    if not o or o == "-" or _is_bureau(o) or re.match(r"client team|onbekend|unknown", o):
        return ""
    o = re.sub(r"\b(gemeente|provincie|b\.?v\.?|n\.?v\.?)\b", " ", o)
    return re.sub(r"[^a-z0-9à-ÿ]+", " ", o).strip()


def _deadline(rij):
    try:
        d = datetime.fromisoformat(str(rij.get("deadline") or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _passen(a, b):
    da, db_ = a["_dl"], b["_dl"]
    return da is None or db_ is None or abs(da - db_) <= DEADLINE_MARGE


def groepeer(rijen):
    """Lijst groepen (lijsten rijen); een opdracht die maar één keer voorkomt is
    een groep van één."""
    for r in rijen:
        r["_dl"], r["_org"] = _deadline(r), org_sleutel(r)
    per_titel = {}
    # eerst regels met een bekende organisatie, dan pas de rest aan een groep koppelen
    for i, r in sorted(enumerate(rijen), key=lambda x: 0 if x[1]["_org"] else 1):
        t = titel_sleutel(r.get("titel"))
        if len(t) < 8:                       # te kort om op te vertrouwen
            per_titel[f"#{i}"] = [[r]]
            continue
        groepen = per_titel.setdefault(t, [])
        doel = None
        if r["_org"]:
            doel = next((g for g in groepen if any(x["_org"] == r["_org"] for x in g)
                         and all(_passen(x, r) for x in g)), None)
        else:
            # zonder organisatie alleen bij precies één passende groep mét bekende organisatie
            passend = [g for g in groepen if any(x["_org"] for x in g) and all(_passen(x, r) for x in g)]
            if len(passend) == 1:
                doel = passend[0]
        if doel is not None:
            doel.append(r)
        else:
            groepen.append([r])
    return [g for groepen in per_titel.values() for g in groepen]


def bereken(db=None):
    """Voor elke actieve opdracht: {"groep": id of None, "ook_op": JSON-lijst van
    de andere bronnen of None}. Sleutel (bron, tender_id). Ook enkelvoudige
    opdrachten staan erin (met None), zodat een oude koppeling verdwijnt."""
    conn = sqlite3.connect(db or DB)
    conn.row_factory = sqlite3.Row
    grens = (datetime.now(timezone.utc) - timedelta(days=ACTIEF_DAGEN)).isoformat(timespec="seconds")
    rijen = [dict(r) for r in conn.execute(
        "SELECT bron, tender_id, titel, organisatie, deadline, url FROM tenders WHERE laatst_gezien >= ?", (grens,))]
    conn.close()
    uit = {}
    for g in groepeer(rijen):
        bronnen = {r["bron"] for r in g}
        if len(bronnen) < 2:                 # alleen dubbel als het echt verschillende bronnen zijn
            for r in g:
                uit[(r["bron"], str(r["tender_id"]))] = {"groep": None, "ook_op": None}
            continue
        sleutels = sorted(f"{r['bron']}|{r['tender_id']}" for r in g)
        groep = hashlib.sha1(sleutels[0].encode()).hexdigest()[:12]
        for r in g:
            anderen = [{"bron": x["bron"], "tender_id": str(x["tender_id"]), "url": x.get("url")}
                       for x in g if x["bron"] != r["bron"]]
            uit[(r["bron"], str(r["tender_id"]))] = {"groep": groep, "ook_op": json.dumps(anderen, ensure_ascii=False)}
    return uit


if __name__ == "__main__":
    from collections import Counter
    d = bereken()
    dubbel = {k: v for k, v in d.items() if v["groep"]}
    print(f"{len(d)} actieve opdrachten, {len(dubbel)} ook bij een andere bron, "
          f"{len({v['groep'] for v in dubbel.values()})} groepen")
    print(Counter(k[0] for k in dubbel).most_common())
