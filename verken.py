"""Finale validatie nieuwe scrapers (TIJDELIJK)."""

import traceback
from scrapers import freelancenl, ns, stedin


def test(mod):
    print(f"\n### {mod.BRON}")
    try:
        rijen = mod.haal_op()
        print(f"  TOTAAL: {len(rijen)}")
        if rijen:
            print("   voorbeeld:", rijen[0])
    except Exception as e:
        print(f"  MISLUKT: {e}")
        traceback.print_exc()


def main():
    for mod in (freelancenl, ns, stedin):
        test(mod)


if __name__ == "__main__":
    main()
