"""Validatie Magnit-scraper (TIJDELIJK)."""

import json
import traceback
from scrapers import magnit


def main():
    print("### magnit")
    try:
        rijen = magnit.haal_op()
        print(f"  TOTAAL: {len(rijen)}")
        for r in rijen[:5]:
            print("   ", json.dumps(r, ensure_ascii=False))
    except Exception as e:
        print(f"  MISLUKT: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    main()
