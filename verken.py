"""Tweede verkenningsronde (TIJDELIJK).

Legt per site de JSON-API's vast (request + response body) en onderzoekt
paginering. Voor MiPublic: probeer WAF te omzeilen met realistische headers
en alternatieve bronnen (wp-json / feed / sitemap).
"""

import json
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

HDRS = {
    "Accept-Language": "nl-NL,nl;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,"
              "image/webp,*/*;q=0.8",
    "sec-ch-ua": '"Chromium";v="120", "Not:A-Brand";v="99"',
    "sec-ch-ua-platform": '"Windows"',
    "Upgrade-Insecure-Requests": "1",
}

API_WORDS = ("search", "results", "/api/", "opdracht", "vacature", "banen",
             "public-api", "jobs", "graphql")


def dump_apis(naam, url, page, extra=None):
    print(f"\n{'='*70}\n### {naam}  ->  {url}\n{'='*70}")
    boeiend = []

    def on_resp(resp):
        u = resp.url.lower()
        ct = resp.headers.get("content-type", "")
        if ("json" in ct) and any(w in u for w in API_WORDS):
            boeiend.append(resp)

    page.on("response", on_resp)
    try:
        page.goto(url, timeout=60000, wait_until="networkidle")
    except Exception as e:
        print(f"  goto: {e}")
    page.wait_for_timeout(3000)
    # probeer meer te laden
    for _ in range(3):
        try:
            page.mouse.wheel(0, 6000)
            page.wait_for_timeout(1500)
        except Exception:
            pass
    if extra:
        extra(page)

    print(f"-- {len(boeiend)} interessante JSON-calls")
    gezien = set()
    for resp in boeiend:
        key = (resp.request.method, resp.url.split("?")[0])
        if key in gezien:
            continue
        gezien.add(key)
        print(f"\n>>> {resp.request.method} {resp.url[:200]}")
        pd = resp.request.post_data
        if pd:
            print(f"    POSTDATA: {pd[:600]}")
        try:
            body = resp.text()
            print(f"    RESP ({len(body)} chars): {body[:1800]}")
        except Exception as e:
            print(f"    body-fout: {e}")


def freelance_extra(page):
    # paginering onderzoeken
    for sel in ["a[rel='next']", ".pagination a", "a.projectlist-nav__next",
                "[class*='pagination'] a", "[class*='next']"]:
        els = page.query_selector_all(sel)
        if els:
            print(f"-- freelance paginatie-selector '{sel}': {len(els)}")
            for e in els[:5]:
                print(f"     href={e.get_attribute('href')} text={e.inner_text()[:30]!r}")


def ns_extra(page):
    # zoek naar totaal + probeer een vacatures-api
    for sel in ["[class*='count']", "[class*='total']", "[class*='result']"]:
        el = page.query_selector(sel)
        if el:
            print(f"-- ns '{sel}': {el.inner_text()[:80]!r}")
    for path in ["/api/2/vacancies", "/api/2/jobs", "/api/2/search",
                 "/api/vacancies", "/api/2/vacancy"]:
        try:
            r = page.request.get("https://www.werkenbijns.nl" + path, timeout=15000)
            print(f"-- ns probe {path}: {r.status} {r.headers.get('content-type','')} "
                  f"{r.text()[:300] if r.status==200 else ''}")
        except Exception as e:
            print(f"-- ns probe {path}: {e}")


def stedin_extra(page):
    for path in ["/search-jobs/results?CurrentPage=1",
                 "/search-jobs/results",
                 "/vacatures-zoeken?page=2"]:
        try:
            r = page.request.get("https://werkenbij.stedin.net" + path, timeout=15000)
            print(f"-- stedin probe {path}: {r.status} {r.headers.get('content-type','')} "
                  f"len={len(r.text())} {r.text()[:400] if r.status==200 else ''}")
        except Exception as e:
            print(f"-- stedin probe {path}: {e}")


def mipublic(ctx):
    print(f"\n{'='*70}\n### mipublic (WAF-omzeiling)\n{'='*70}")
    page = ctx.new_page()
    for url in ["https://mipublic.nl/zzp-opdrachten-overheid/",
                "https://mipublic.nl/wp-json/wp/v2/types",
                "https://mipublic.nl/wp-json/wp/v2/vacature?per_page=5",
                "https://mipublic.nl/vacature/feed/",
                "https://mipublic.nl/sitemap.xml",
                "https://mipublic.nl/sitemap_index.xml",
                "https://mipublic.nl/wp-sitemap.xml"]:
        try:
            r = page.request.get(url, headers=HDRS, timeout=20000)
            body = r.text()
            print(f"\n>>> {url}\n    status={r.status} ct={r.headers.get('content-type','')} "
                  f"len={len(body)}")
            print(f"    {body[:700]}")
        except Exception as e:
            print(f"\n>>> {url}\n    fout: {e}")
    page.close()


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(user_agent=UA, locale="nl-NL",
                                  extra_http_headers=HDRS)
        for naam, url, extra in [
            ("freelancenl", "https://www.freelance.nl/opdrachten", freelance_extra),
            ("ns", "https://www.werkenbijns.nl/vacatures", ns_extra),
            ("stedin", "https://werkenbij.stedin.net/vacatures-zoeken", stedin_extra),
        ]:
            page = ctx.new_page()
            try:
                dump_apis(naam, url, page, extra)
            except Exception as e:
                print(f"### {naam} MISLUKT: {e}")
            finally:
                page.close()
        mipublic(ctx)
        browser.close()


if __name__ == "__main__":
    main()
