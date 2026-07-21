"""Validatie nieuwe scrapers (TIJDELIJK)."""

import traceback
from scrapers import ns, stedin


def test_scraper(mod):
    print(f"\n{'='*60}\n### {mod.BRON}\n{'='*60}")
    try:
        rijen = mod.haal_op()
        print(f"  TOTAAL: {len(rijen)}")
        for r in rijen[:3]:
            print("   ", r)
        for r in rijen[-2:]:
            print("   (laatste)", r)
    except Exception as e:
        print(f"  MISLUKT: {e}")
        traceback.print_exc()


def main():
    test_scraper(ns)
    test_scraper(stedin)


if __name__ == "__main__":
    main()
