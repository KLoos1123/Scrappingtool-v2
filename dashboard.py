"""Genereert de databron voor het HTML-dashboard.

Schrijft web/tenders.json uit de tenders-database. Het dashboard (web/index.html)
laadt dat bestand via fetch() en doet zelf alle verrijking/scoring/filtering in de
browser. GitHub Pages host web/ zodat het dashboard op een vaste URL staat.
"""

import os
import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone

DB = "tenders.db"
UITVOER_DIR = "web"

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


if __name__ == "__main__":
    main()
