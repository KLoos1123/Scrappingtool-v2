"""Eenmalige backfill: zet de bestaande tenders.db (en beschrijvingen) over
naar Supabase.

Draai dit ÉÉN keer, lokaal, nadat je supabase_migration.sql hebt uitgevoerd
in de Supabase SQL Editor en de env vars hieronder hebt gezet. Daarna houdt
de normale scraper-run (run.py, via supabase_sync.py) Supabase automatisch
bij; dit script hoeft nooit meer te draaien tenzij je een keer helemaal
opnieuw wil synchroniseren.

Gebruik:
    export SUPABASE_URL="https://xxxx.supabase.co"
    export SUPABASE_SERVICE_ROLE_KEY="xxxxx"
    python migreer_naar_supabase.py
"""

import db
import beschrijvingen
import supabase_sync


def main():
    print("=== bestaande tenders ophalen uit tenders.db ===")
    rijen = [dict(r) for r in db.alle_rijen()]
    print(f"  {len(rijen)} rijen gevonden")

    print("\n=== naar Supabase sturen (tenders) ===")
    n = supabase_sync.sync_tenders(rijen)
    print(f"  {n} tenders gesynct")

    print("\n=== bestaande omschrijvingen ophalen ===")
    conn = beschrijvingen._verbind()
    oms_rijen = [
        {"bron": b, "tender_id": t, "omschrijving": o}
        for b, t, o in conn.execute(
            "SELECT bron, tender_id, omschrijving FROM beschrijvingen"
        ).fetchall()
    ]
    conn.close()
    print(f"  {len(oms_rijen)} omschrijvingen gevonden")

    print("\n=== naar Supabase sturen (beschrijvingen) ===")
    n2 = supabase_sync.sync_beschrijvingen(oms_rijen)
    print(f"  {n2} omschrijvingen gesynct")

    print("\nKlaar. Check in de Supabase Table Editor of 'tenders' en "
          "'beschrijvingen' gevuld zijn, en open daarna het dashboard.")


if __name__ == "__main__":
    main()
