"""Schrijft JSON-exports van de tenders-database naar web/.

Het dashboard (web/index.html) leest zelf uit Supabase. Deze exports zijn voor
GitHub Pages (tenders.json, beschrijvingen.json; niet in git) en voor agents die
via GitHub lezen (samenvatting.json, tenders_7d.json; wel in git, want klein).
"""

import os
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone, timedelta

DB = "tenders.db"
UITVOER_DIR = "web"
RECENT_DAGEN = 7

# Velden die het dashboard nodig heeft (zie loadData in web/index.html).
VELDEN = [
    "bron", "tender_id", "nummer", "titel", "organisatie", "status",
    "url", "locatie", "deadline", "publicatiedatum", "eerst_gezien",
]


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    rijen = conn.execute(
        "SELECT * FROM tenders ORDER BY publicatiedatum DESC"
    ).fetchall()
    laatst = conn.execute("SELECT max(laatst_gezien) FROM tenders").fetchone()[0]
    conn.close()

    data = {
        "fileName": "tenders",
        "lastUpdated": laatst or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count": len(rijen),
        "rows": [{k: r[k] for k in VELDEN} for r in rijen],
    }

    os.makedirs(UITVOER_DIR, exist_ok=True)
    pad = os.path.join(UITVOER_DIR, "tenders.json")
    with open(pad, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"{pad} geschreven ({len(rijen)} rijen)")

    # Omschrijvingen apart voor het dashboard: { "bron|tender_id": tekst }.
    # Losse file zodat tenders.json licht blijft en het dashboard 'm lazy laadt.
    conn2 = sqlite3.connect(DB)
    beschr = {}
    try:
        rows2 = conn2.execute(
            "SELECT bron, tender_id, omschrijving FROM beschrijvingen").fetchall()
        for bron, tid, oms in rows2:
            if oms:
                beschr[f"{bron}|{tid}"] = oms
    except sqlite3.OperationalError:
        pass  # tabel bestaat nog niet
    conn2.close()
    pad2 = os.path.join(UITVOER_DIR, "beschrijvingen.json")
    with open(pad2, "w", encoding="utf-8") as f:
        json.dump(beschr, f, ensure_ascii=False)
    print(f"{pad2} geschreven ({len(beschr)} omschrijvingen)")

    # Klein samenvattingsbestand voor API-analyse (leesbaar via GitHub API).
    alle_rijen = data["rows"]
    org_teller = Counter(r["organisatie"] for r in alle_rijen if r.get("organisatie"))
    bron_teller = Counter(r["bron"] for r in alle_rijen if r.get("bron"))
    actief = [r for r in alle_rijen if (r.get("status") or "").lower() in ("open", "actief", "gepubliceerd", "nieuw", "")]

    samenvatting = {
        "lastUpdated": data["lastUpdated"],
        "totaal": len(alle_rijen),
        "per_bron": dict(bron_teller.most_common()),
        "organisaties": dict(org_teller.most_common(200)),
        "nieuwste_100": alle_rijen[:100],
        "actief": actief[:200],
    }
    pad3 = os.path.join(UITVOER_DIR, "samenvatting.json")
    with open(pad3, "w", encoding="utf-8") as f:
        json.dump(samenvatting, f, ensure_ascii=False)
    print(f"{pad3} geschreven ({len(alle_rijen)} totaal, {len(actief)} actief)")

    grens = (datetime.now(timezone.utc) - timedelta(days=RECENT_DAGEN)).isoformat(timespec="seconds")
    conn3 = sqlite3.connect(DB)
    try:
        ai = {(b, t): json.loads(d) for b, t, d in conn3.execute(
            "SELECT bron, tender_id, data FROM verrijkingen")}
    except sqlite3.OperationalError:
        ai = {}  # tabel bestaat nog niet
    conn3.close()
    recent = [{**{k: r[k] for k in VELDEN}, "laatst_gezien": r["laatst_gezien"],
               "ai": ai.get((r["bron"], r["tender_id"]))}
              for r in rijen if (r["eerst_gezien"] or "") >= grens]
    recent_data = {
        "fileName": "tenders_7d",
        "lastUpdated": data["lastUpdated"],
        "vanaf": grens,
        "count": len(recent),
        "rows": recent,
    }
    pad4 = os.path.join(UITVOER_DIR, "tenders_7d.json")
    with open(pad4, "w", encoding="utf-8") as f:
        json.dump(recent_data, f, ensure_ascii=False)
    print(f"{pad4} geschreven ({len(recent)} rijen sinds {grens})")


if __name__ == "__main__":
    main()
