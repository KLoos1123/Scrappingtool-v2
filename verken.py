"""Validatie Stedin-paginering (TIJDELIJK)."""

import traceback
from scrapers import stedin


def main():
    print("### stedin")
    try:
        rijen = stedin.haal_op()
        print(f"  TOTAAL: {len(rijen)}")
        for r in rijen[:2]:
            print("   ", r)
        for r in rijen[-2:]:
            print("   (laatste)", r)
    except Exception as e:
        print(f"  MISLUKT: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
