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
# (mercell, striive, magnit, stedin-vms, portofrotterdam, staffingms, heart)
# zijn af en toe flakey; pas bij brede uitval is er echt iets structureel mis.
MAX_MISLUKT = 3
 
import db
import datums
import deadlines
import verrijking
import beschrijvingen
import tarieven
import sheets_writer
import supabase_sync
from scrapers import (mercell, flextender, hero, striive, freelancenl, ns,
                      stedin, tenderned, inhuurdesk_regio, gelderland,
                      flexwestbrabant, magnit, stedin_vms, opdrachtoverheid,
                      harveynash, portofrotterdam, staffingms, heart,
                      mipublic, freep, quest4, publiekepartner,
                      inhuurdesk_alliander, ns_vms, alliander_vms)
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
    opdrachtoverheid,
    harveynash,
    portofrotterdam,
    staffingms,
    heart,
    mipublic,
    freep,
    quest4,
    publiekepartner,
    inhuurdesk_alliander,
    ns_vms,
    alliander_vms,
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
                datums.normaliseer_rij(r)
            print(f"  {len(rijen)} rijen opgehaald")
            alles.extend(rijen)
        except Exception as e:
            print(f"  MISLUKT: {e}")
            traceback.print_exc()
            mislukt.append(naam)
    
    if not alles:
        print("\nNiets opgehaald, database niet aangepast.")
        sys.exit(1)

    # Bronnen zonder deadlineveld zetten 'm vaak wel in de omschrijving.
    aangevuld = deadlines.vul_aan(alles)
    if aangevuld:
        print(f"\n  {aangevuld} deadlines aangevuld uit de omschrijving")
 
    print(f"\n=== database ===")
    nieuw, totaal = db.opslaan(alles)
    print(f"  {nieuw} nieuw, {totaal} totaal")
    gecorrigeerd = db.normaliseer_bestaande_datums()
    if gecorrigeerd:
        print(f"  {len(gecorrigeerd)} oudere tekstdatums omgezet naar ISO")
    uit_tekst = db.deadlines_uit_omschrijving(deadlines.haal_deadline)
    if uit_tekst:
        print(f"  {len(uit_tekst)} oudere deadlines aangevuld uit de omschrijving")
    gecorrigeerd += uit_tekst
    for r in db.per_bron():
        print(f"  {r['bron']}: {r['aantal']}")
 
    # Omschrijvingen apart bewaren (hoofdtabel blijft licht). Scrapers die een
    # 'omschrijving' meegeven voeden zo de latere AI-inschatting van de eindklant.
    print(f"\n=== omschrijvingen ===")
    met_oms = []
    try:
        met_oms = [r for r in alles if r.get("omschrijving")]
        opgeslagen = beschrijvingen.opslaan(met_oms)
        print(f"  {opgeslagen} omschrijvingen bewaard")
        for r in beschrijvingen.per_bron():
            print(f"  {r[0]}: {r[1]}")
    except Exception as e:
        print(f"  omschrijvingen MISLUKT: {e}")

    print(f"\n=== AI-verrijking ===")
    if not verrijking.beschikbaar():
        print("  ANTHROPIC_API_KEY ontbreekt; overgeslagen")
    else:
        try:
            kandidaten = db.te_verrijken(verrijking.maak_hash, verrijking.MAX_PER_RUN)
            resultaten, fouten = verrijking.verrijk_alle(kandidaten)
            db.verrijkingen_opslaan(resultaten)
            print(f"  {len(resultaten)} verrijkt, {fouten} mislukt "
                  f"(max {verrijking.MAX_PER_RUN} per run, model {verrijking.MODEL})")
            if kandidaten and not resultaten:
                mislukt.append("AI-verrijking")
        except Exception as e:
            print(f"  AI-verrijking MISLUKT: {type(e).__name__}: {e}")
            mislukt.append("AI-verrijking")
 
    # Supabase is de databron voor het live dashboard (real-time, met een
    # per-tender status die gebruikers zelf zetten). Raakt nooit de
    # status/status_gewijzigd_door/status_gewijzigd_op kolommen aan.
    print(f"\n=== supabase ===")
    try:
        al_in_run = {(r["bron"], str(r.get("tender_id"))) for r in alles}
        extra = [r for r in gecorrigeerd if (r["bron"], str(r["tender_id"])) not in al_in_run]
        n_tenders = supabase_sync.sync_tenders(alles + extra)
        print(f"  {n_tenders} tenders gesynct")
        n_oms = supabase_sync.sync_beschrijvingen(met_oms)
        print(f"  {n_oms} omschrijvingen gesynct")
        nog_te_syncen = db.verrijkingen(alleen_ongesynct=True)
        if nog_te_syncen:
            n_ai = supabase_sync.sync_verrijkingen(nog_te_syncen)
            db.markeer_gesynct(nog_te_syncen)
            print(f"  {n_ai} verrijkingen gesynct")
    except Exception as e:
        print(f"  Supabase-sync MISLUKT: {e}")
        traceback.print_exc()
        mislukt.append("Supabase")

    # Tarieven uit de omschrijvingen (en anders de AI-verrijking), alleen ter
    # info in het dashboard. Telt niet mee als mislukte bron: de tabel bestaat
    # pas na supabase/notities_tarieven.sql.
    print(f"\n=== tarieven ===")
    try:
        gevonden = tarieven.verzamel(alles)
        print(f"  {sum(1 for r in gevonden if r['tarief'])} tarieven en "
              f"{sum(1 for r in gevonden if r['uren'])} keer uren gevonden")
        if supabase_sync._configured():
            print(f"  {supabase_sync.sync_tarieven(gevonden)} rijen gesynct")
    except Exception as e:
        print(f"  tarieven MISLUKT: {e}")
 
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
