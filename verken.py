"""Validatie regionale inhuurdesk-scrapers (TIJDELIJK)."""

import traceback
from scrapers import inhuurdesk_regio, gelderland, flexwestbrabant


def test(mod):
    print(f"\n{'='*60}\n### {mod.BRON}\n{'='*60}")
    try:
        rijen = mod.haal_op()
        print(f"  TOTAAL: {len(rijen)}")
        for r in rijen[:3]:
            print("   ", r)
        for r in rijen[-1:]:
            print("   (laatste)", r)
    except Exception as e:
        print(f"  MISLUKT: {e}")
        traceback.print_exc()


def main():
    for mod in (inhuurdesk_regio, gelderland, flexwestbrabant):
        test(mod)


if __name__ == "__main__":
    main()
