"""MiPublic (Masters in Public) - zzp-, interim- en detacheringsopdrachten bij de overheid.

Publieke site, geen login nodig. De homepage (Next.js) wordt server-side
gerenderd en bevat in de RSC-payload (self.__next_f.push) de volledige
opdrachtenlijst als JSON ("opdrachten":[...]): titel, opdrachtgever, uren,
tarief, regio en link. Een aparte JSON-API is er niet publiek.

De lijst geeft de sluitingsdatum alleen relatief ("Sluit over 4 dagen"). De
exacte datum (validThrough), publicatiedatum, plaats en omschrijving staan in
de JSON-LD (JobPosting) van de detailpagina; die halen we per opdracht op. Lukt
dat niet, dan rekenen we de deadline terug uit de relatieve tekst.
"""

import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

BRON = "mipublic"

APP = "https://mipublic.nl"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

WERKERS = 4  # parallelle detailpagina's

RSC_RE = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)', re.S)
LD_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)
SLUIT_RE = re.compile(r"sluit\s+over\s+(\d+)\s+dag", re.I)


def _opdrachten(html):
    """Haalt de array "opdrachten" uit de RSC-payload van de homepage."""
    stukken = RSC_RE.findall(html)
    # De stukken zijn JS-stringliterals; samen als JSON-string decoderen.
    payload = json.loads('"' + "".join(stukken) + '"')
    sleutel = '"opdrachten":'
    i = payload.find(sleutel + "[")
    if i < 0:
        raise RuntimeError("MiPublic: opdrachtenlijst niet gevonden in de homepage")
    lijst, _ = json.JSONDecoder().raw_decode(payload, i + len(sleutel))
    return lijst


def _uren(o):
    laag, hoog = o.get("hoursMin"), o.get("hoursMax")
    if not hoog:
        return None
    if laag and laag != hoog:
        return f"{laag}-{hoog}"
    return str(hoog)


def _deadline_relatief(tekst):
    """"Sluit over 4 dagen" -> datum; "Sluit vandaag" -> vandaag."""
    tekst = (tekst or "").lower()
    m = SLUIT_RE.search(tekst)
    if m:
        return (date.today() + timedelta(days=int(m[1]))).isoformat()
    if "vandaag" in tekst:
        return date.today().isoformat()
    return None


def _uit_opdracht(o):
    href = o.get("href") or ""
    slug = href.rstrip("/").rsplit("/", 1)[-1]
    rij = {
        "tender_id": slug,
        "nummer": None,
        "titel": o.get("title"),
        # Anonieme opdrachten: "Een overheidsorganisatie in Zuid-Holland" (en
        # "confidential" in de JSON-LD) is geen echte opdrachtgever.
        "organisatie": None if o.get("isAnonymous") else o.get("company"),
        "status": "Open",
        "deadline": _deadline_relatief(o.get("closing")),
        "publicatiedatum": None,
        "locatie": o.get("location"),
        "uren_per_week": _uren(o),
        "url": APP + href,
    }
    if o.get("tariefMin"):
        rij["tarief_min"] = o["tariefMin"]
    if o.get("tariefMax"):
        rij["tarief_max"] = o["tariefMax"]
    return rij


def _jobposting(html):
    for blok in LD_RE.findall(html):
        try:
            ld = json.loads(blok, strict=False)
        except ValueError:
            continue
        if isinstance(ld, dict) and ld.get("@type") == "JobPosting":
            return ld
    return None


def _vul_detail(sessie, rij):
    """Vult exacte deadline, publicatiedatum, plaats en omschrijving aan uit de
    JSON-LD van de detailpagina. Fouten negeren we."""
    try:
        r = sessie.get(rij["url"], timeout=20)
        if not r.ok:
            return
        ld = _jobposting(r.text)
    except requests.RequestException:
        return
    if not ld:
        return

    rij["deadline"] = ld.get("validThrough") or rij["deadline"]
    rij["publicatiedatum"] = ld.get("datePosted")
    adres = (ld.get("jobLocation") or {}).get("address") or {}
    # Alleen de werkplaats: addressRegion is de regio uit de lijst en past niet
    # altijd bij de plaats ("Groningen" met regio "Utrecht").
    if adres.get("addressLocality"):
        rij["locatie"] = adres["addressLocality"]
    oms = ld.get("description")
    if oms:
        rij["omschrijving"] = BeautifulSoup(oms, "lxml").get_text(" ", strip=True) or None


def haal_op():
    """Wordt aangeroepen door run.py. Geeft een lijst dicts terug."""
    sessie = requests.Session()
    sessie.headers.update({"user-agent": UA, "accept-language": "nl-NL,nl;q=0.9"})

    r = sessie.get(APP + "/", timeout=30)
    r.raise_for_status()

    rijen, gezien = [], set()
    for o in _opdrachten(r.text):
        if not o.get("href"):
            continue
        rij = _uit_opdracht(o)
        if rij["tender_id"] not in gezien:
            gezien.add(rij["tender_id"])
            rijen.append(rij)
    print(f"  {len(rijen)} opdrachten in de lijst")

    with ThreadPoolExecutor(WERKERS) as pool:
        list(pool.map(lambda rij: _vul_detail(sessie, rij), rijen))

    met = sum(1 for r in rijen if r.get("omschrijving"))
    print(f"  {len(rijen)} opdrachten opgehaald, {met} met omschrijving")
    return rijen
