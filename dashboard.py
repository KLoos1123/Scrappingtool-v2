"""Genereert de databron voor het HTML-dashboard.

Schrijft web/tenders.json uit de tenders-database. Het dashboard (web/index.html)
laadt dat bestand via fetch() en doet zelf alle verrijking/scoring/filtering in de
browser. GitHub Pages host web/ zodat het dashboard op een vaste URL staat.
"""

import os
import json
import sqlite3
from datetime import datetime, timezone

DB = "tenders.db"
UITVOER_DIR = "web"

# Velden die het dashboard nodig heeft (zie loadData in web/index.html).
VELDEN = [
    "bron", "nummer", "titel", "organisatie", "status",
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


if __name__ == "__main__":
    main()
