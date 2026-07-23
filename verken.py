"""Recon (TIJDELIJK): TenderNed detail-API -> welk veld bevat de omschrijving?

Alleen requests, geen browser, geen login-scrapers. Print de structuur van een
publicatie-detail zodat we de omschrijving-ophaler kunnen bouwen.
"""

import json
import requests

UA = {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "accept": "application/json"}
BASE = "https://www.tenderned.nl/papi/tenderned-rs-tns/v2/publicaties"


def _zoek_velden(obj, prefix=""):
    """Loop door de JSON en print velden die op een omschrijving lijken."""
    woorden = ["omschrijving", "beschrijving", "samenvatting", "toelichting",
               "korte", "aanleiding", "doel", "scope", "opdracht"]
    if isinstance(obj, dict):
        for k, v in obj.items():
            pad = f"{prefix}.{k}" if prefix else k
            if isinstance(v, str) and any(w in k.lower() for w in woorden) and v.strip():
                print(f"   [{pad}] ({len(v)} tekens): {v[:220]}")
            _zoek_velden(v, pad)
    elif isinstance(obj, list) and obj:
        _zoek_velden(obj[0], prefix + "[0]")


def main():
    r = requests.get(BASE, params={"page": 0, "size": 3}, headers=UA, timeout=30)
    print("lijst status:", r.status_code)
    content = r.json().get("content") or []
    for p in content[:3]:
        pid = p.get("publicatieId")
        naam = p.get("aanbestedingNaam")
        print(f"\n{'='*70}\npublicatieId={pid}  |  {naam}")
        try:
            r2 = requests.get(f"{BASE}/{pid}", headers=UA, timeout=30)
            print("detail status:", r2.status_code)
            det = r2.json()
            print("top-level keys:", sorted(det.keys()))
            print("omschrijving-achtige velden:")
            _zoek_velden(det)
        except Exception as e:
            print("detail FOUT:", type(e).__name__, str(e)[:200])


if __name__ == "__main__":
    main()
