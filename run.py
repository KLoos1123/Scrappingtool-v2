"""Draait alle scrapers en schrijft het resultaat naar de gedeelde database.
Een scraper die crasht stopt de rest niet, maar de run eindigt wel in een fout
zodat je het in GitHub Actions ziet.
"""
import os
import csv
import sys
import subprocess
import traceback
from datetime import datetime, timezone, timedelta

# Zoveel bronnen mogen falen zonder de hele run rood te maken. Login-scrapers
# (mercell, striive, magnit, stedin-vms) zijn af en toe flakey; pas bij brede
# uitval is er echt iets structureel mis.
MAX_MISLUKT = 3

import db
import beschrijvingen
import sheets_writer
from scrapers import (mercell, flextender, hero, striive, freelancenl, ns,
                      stedin, tenderned, inhuurdesk_regio, gelderland,
                      flexwestbrabant, magnit, stedin_vms)
# import sharepoint_writer


SCRAPERS = [
    mercell,
    flextender,
    hero,
    striive,
    freelancenl,
    ns,
    stedin,
    tenderned,
    inhuurdesk_regio,
    gelderland,
    flexwestbrabant,
    magnit,
    stedin_vms,
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

    # Omschrijvingen apart bewaren (hoofdtabel blijft licht). Scrapers die een
    # 'omschrijving' meegeven voeden zo de latere AI-inschatting van de eindklant.
    print(f"\n=== omschrijvingen ===")
    try:
        met_oms = [r for r in alles if r.get("omschrijving")]
        opgeslagen = beschrijvingen.opslaan(met_oms)
        print(f"  {opgeslagen} omschrijvingen bewaard")
        for r in beschrijvingen.per_bron():
            print(f"  {r[0]}: {r[1]}")
    except Exception as e:
        print(f"  omschrijvingen MISLUKT: {e}")

    print(f"\n=== export ===")
    alle = db.alle_rijen()
    exporteer(alle, CSV_ALLES)
    exporteer(db.nieuw_sinds(startmoment.isoformat(timespec="seconds")), CSV_NIEUW)

    print(f"\n=== sharepoint ===")
    try:
        sheets_writer.sync(alle)
    except Exception as e:
        print(f"  SharePoint-sync MISLUKT: {e}")
        traceback.print_exc()
        mislukt.append("SharePoint")

    print(f"\n=== dashboard ===")
    subprocess.run(["python", "dashboard.py"], check=True)

    if mislukt:
        melding = f"Mislukte bronnen ({len(mislukt)}): {', '.join(mislukt)}"
        print(f"\n{melding}")
        # zichtbaar maken in de GitHub-samenvatting, ook als de run groen blijft
        samenvatting = os.environ.get("GITHUB_STEP_SUMMARY")
        if samenvatting:
            try:
                with open(samenvatting, "a", encoding="utf-8") as f:
                    f.write(f"\n⚠️ {melding}\n")
            except Exception:
                pass
        # een paar flakey (login-)bronnen tolereren; alleen bij brede uitval falen
        if len(mislukt) > MAX_MISLUKT:
            print(f"  meer dan {MAX_MISLUKT} bronnen mislukt -> run faalt")
            sys.exit(1)
        print(f"  binnen tolerantie ({len(mislukt)}/{MAX_MISLUKT}); run blijft groen")

    print("\nKlaar.")


if __name__ == "__main__":
    main()
