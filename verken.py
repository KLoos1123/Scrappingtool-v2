"""TenderNed open-API verkenning (TIJDELIJK)."""

import json
import requests

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

BASES = [
    "https://www.tenderned.nl/papi/tenderned-rs-tns/v2/publicaties",
    "https://www.tenderned.nl/papi/tenderned-rs-tns/publicaties",
]


def probe(url, params):
    try:
        r = requests.get(url, params=params,
                         headers={"user-agent": UA, "accept": "application/json"},
                         timeout=30)
        print(f"\n>>> {r.url}\n    status={r.status_code} ct={r.headers.get('content-type','')}")
        if r.status_code == 200 and "json" in r.headers.get("content-type", ""):
            data = r.json()
            if isinstance(data, dict):
                print(f"    top-keys: {list(data.keys())}")
                content = data.get("content") or data.get("publicaties") or data.get("_embedded")
                if isinstance(content, list) and content:
                    print(f"    aantal in pagina: {len(content)}")
                    print(f"    eerste item keys: {list(content[0].keys())}")
                    print(f"    eerste item: {json.dumps(content[0], ensure_ascii=False)[:1500]}")
                else:
                    print(f"    body sample: {json.dumps(data, ensure_ascii=False)[:1200]}")
            elif isinstance(data, list):
                print(f"    lijst, lengte {len(data)}")
                if data:
                    print(f"    eerste: {json.dumps(data[0], ensure_ascii=False)[:1200]}")
        else:
            print(f"    body: {r.text[:400]}")
    except Exception as e:
        print(f"    fout: {e}")


def main():
    for base in BASES:
        for params in [
            {"page": 0, "size": 5},
            {"page": 0, "size": 5, "publicatieDatumVanaf": "2026-07-14"},
        ]:
            probe(base, params)


if __name__ == "__main__":
    main()
