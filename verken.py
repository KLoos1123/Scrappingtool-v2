"""Validatie TenderNed-scraper (TIJDELIJK)."""

import traceback
from scrapers import tenderned


def main():
    print("### tenderned")
    try:
        rijen = tenderned.haal_op()
        print(f"  TOTAAL: {len(rijen)}")
        for r in rijen[:3]:
            print("   ", r)
        # even kijken naar spreiding van publicatiedata
        datums = sorted({r["publicatiedatum"] for r in rijen if r["publicatiedatum"]})
        print(f"  datumbereik: {datums[:1]} .. {datums[-1:]}  ({len(datums)} unieke dagen)")
    except Exception as e:
        print(f"  MISLUKT: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
