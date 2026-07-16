"""Draait alle scrapers en schrijft het resultaat naar de gedeelde database.

Een scraper die crasht stopt de rest niet, maar de run eindigt wel in een fout
zodat je het in GitHub Actions ziet.
"""

import csv
import sys
import traceback
from datetime import datetime, timezone, timedelta

import db
from scrapers import mercell

# Nieuwe bron toevoegen? Importeer hem hierboven en zet hem in deze lijst.
SCRAPERS = [
    mercell,
]

CSV_ALLES = "tenders.csv"
CSV_NIEUW = "tenders_nieuw.csv"


def exporteer(rijen, bestand):
    if not rijen:
        print(f"  {bestand}: niets te schrijven")
        return
    kolommen = rijen[0].keys()
    with open(bestand, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=kolommen, delimiter=";")
        w.writeheader()
        w.writerows(dict(r) for r in rijen)
    print(f"  {bestand}: {len(rijen)} rijen")


def main():
    startmoment = datetime.now(timezone.utc) - timedelta(seconds=5)
    alles = []
    mislukt = []

    for scraper in SCRAPERS:
        naam = scraper.BRON
        print(f"\n=== {naam} ===")
        try:
            rijen = scraper.haal_op()
            for r in rijen:
                r["bron"] = naam
            print(f"  {len(rijen)} rijen opgehaald")
            alles.extend(rijen)
        except Exception as e:
            print(f"  MISLUKT: {e}")
            traceback.print_exc()
            mislukt.append(naam)

    if not alles:
        print("\nNiets opgehaald, database niet aangepast.")
        sys.exit(1)

    print(f"\n=== database ===")
    nieuw, totaal = db.opslaan(alles)
    print(f"  {nieuw} nieuw, {totaal} totaal")

    for r in db.per_bron():
        print(f"  {r['bron']}: {r['aantal']}")

    print(f"\n=== export ===")
    exporteer(db.alle_rijen(), CSV_ALLES)
    exporteer(db.nieuw_sinds(startmoment.isoformat(timespec="seconds")), CSV_NIEUW)

    if mislukt:
        print(f"\nMislukte bronnen: {', '.join(mislukt)}")
        sys.exit(1)

    print("\nKlaar.")


if __name__ == "__main__":
    main()
