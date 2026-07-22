"""Exporteert de tenders-database naar data/tenders.json voor de statische dashboard."""

import json
import sqlite3
from datetime import datetime, timezone

DB = "tenders.db"
OUT = "data/tenders.json"


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    rijen = c.execute("SELECT * FROM tenders ORDER BY publicatiedatum DESC").fetchall()
    conn.close()

    rows = [dict(r) for r in rijen]

    payload = {
        "fileName": "tenders.db",
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "rows": rows,
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)

    print(f"{OUT} geschreven ({len(rows)} rijen)")


if __name__ == "__main__":
    main()
