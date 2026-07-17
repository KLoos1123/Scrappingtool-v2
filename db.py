"""Gedeelde database voor alle scrapers.

Elke scraper levert rijen aan met de velden uit VELDEN.
Deduplicatie gebeurt op (bron, tender_id).
"""

import sqlite3
from datetime import datetime, timezone

DB = "tenders.db"

# Het contract: dit zijn de velden die elke scraper moet aanleveren.
VELDEN = [
    "bron",
    "tender_id",
    "nummer",
    "titel",
    "organisatie",
    "status",
    "deadline",
    "publicatiedatum",
    "locatie",
    "url",
]

SCHEMA = """
CREATE TABLE IF NOT EXISTS tenders (
    bron             TEXT NOT NULL,
    tender_id        TEXT NOT NULL,
    nummer           TEXT,
    titel            TEXT,
    organisatie      TEXT,
    status           TEXT,
    deadline         TEXT,
    publicatiedatum  TEXT,
    locatie          TEXT,
    url              TEXT,
    eerst_gezien     TEXT NOT NULL,
    laatst_gezien    TEXT NOT NULL,
    PRIMARY KEY (bron, tender_id)
);

CREATE INDEX IF NOT EXISTS idx_publicatie ON tenders(publicatiedatum DESC);
CREATE INDEX IF NOT EXISTS idx_bron       ON tenders(bron);
CREATE INDEX IF NOT EXISTS idx_deadline   ON tenders(deadline);
"""


def verbind():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)

    # Migratie: bestaande databases hadden nog geen locatie-kolom.
    kolommen = {r["name"] for r in conn.execute("PRAGMA table_info(tenders)")}
    if "locatie" not in kolommen:
        conn.execute("ALTER TABLE tenders ADD COLUMN locatie TEXT")

    return conn


def opslaan(rijen):
    """Slaat rijen op. Bestaande tenders worden bijgewerkt, niet gedupliceerd.

    Geeft terug: (aantal_nieuw, totaal_in_database)
    """
    conn = verbind()
    nu = datetime.now(timezone.utc).isoformat(timespec="seconds")

    voor = conn.execute("SELECT count(*) FROM tenders").fetchone()[0]

    for r in rijen:
        waarden = [r.get(v) for v in VELDEN]
        conn.execute(
            """
            INSERT INTO tenders
                (bron, tender_id, nummer, titel, organisatie,
                 status, deadline, publicatiedatum, locatie, url,
                 eerst_gezien, laatst_gezien)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT (bron, tender_id) DO UPDATE SET
                titel         = excluded.titel,
                organisatie   = excluded.organisatie,
                status        = excluded.status,
                deadline      = excluded.deadline,
                locatie       = excluded.locatie,
                url           = excluded.url,
                laatst_gezien = excluded.laatst_gezien
            """,
            waarden + [nu, nu],
        )

    conn.commit()
    na = conn.execute("SELECT count(*) FROM tenders").fetchone()[0]
    conn.close()

    return na - voor, na


def alle_rijen():
    conn = verbind()
    rijen = conn.execute(
        "SELECT * FROM tenders ORDER BY publicatiedatum DESC"
    ).fetchall()
    conn.close()
    return rijen


def nieuw_sinds(tijdstip):
    """Tenders die voor het eerst gezien zijn na het opgegeven tijdstip (ISO-string)."""
    conn = verbind()
    rijen = conn.execute(
        "SELECT * FROM tenders WHERE eerst_gezien > ? ORDER BY publicatiedatum DESC",
        (tijdstip,),
    ).fetchall()
    conn.close()
    return rijen


def per_bron():
    conn = verbind()
    rijen = conn.execute(
        "SELECT bron, count(*) AS aantal FROM tenders GROUP BY bron ORDER BY aantal DESC"
    ).fetchall()
    conn.close()
    return rijen
