"""Magnit-portaal: login-mechanisme verkennen (TIJDELIJK).

Navigeert naar het supplier-portaal (zonder in te loggen) en dumpt de
structuur van de login-pagina: invoervelden, knoppen, en of er een externe
identity provider (Okta / Azure AD / Auth0 / Ping) of MFA in het spel is.
Print GEEN wachtwoorden of tokens.
"""

import os
from playwright.sync_api import sync_playwright

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

START = "https://portal.magnitglobal.com/supplier/jobrequests/new"

IDP_HOSTS = ["okta", "microsoftonline", "auth0", "pingidentity", "pingone",
             "onelogin", "login.magnit", "sso", "identity"]


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(user_agent=UA, locale="nl-NL").new_page()

        try:
            page.goto(START, timeout=60000, wait_until="domcontentloaded")
        except Exception as e:
            print(f"goto fout: {e}")
        page.wait_for_timeout(6000)

        print(f"-- start-url : {START}")
        print(f"-- eind-url  : {page.url}")
        print(f"-- titel     : {page.title()!r}")

        host = page.url.lower()
        idp = [h for h in IDP_HOSTS if h in host]
        print(f"-- idp-hint (uit url): {idp or 'geen'}")

        # invoervelden
        velden = page.eval_on_selector_all(
            "input, button, a[role=button]",
            """els => els.slice(0, 40).map(e => ({
                tag: e.tagName,
                type: e.getAttribute('type'),
                name: e.getAttribute('name'),
                id: e.id,
                placeholder: e.getAttribute('placeholder'),
                autocomplete: e.getAttribute('autocomplete'),
                text: (e.innerText||'').trim().slice(0,40)
            }))"""
        )
        print("-- interactieve elementen:")
        for v in velden:
            print(f"   {v}")

        # SSO / MFA hints in de tekst
        tekst = page.inner_text("body").lower()
        for hint in ["okta", "microsoft", "azure", "single sign", "sso",
                     "verification code", "authenticator", "mfa",
                     "two-factor", "two factor", "wachtwoord", "password",
                     "e-mail", "email", "username", "gebruikersnaam"]:
            if hint in tekst:
                print(f"-- tekst-hint: '{hint}' aanwezig")

        # frames (login kan in een iframe zitten)
        for fr in page.frames:
            if fr.url and fr.url != page.url:
                print(f"-- frame: {fr.url[:120]}")

        try:
            page.screenshot(path="debug_magnit_login.png", full_page=True)
            print("-- screenshot: debug_magnit_login.png")
        except Exception:
            pass

        # laat weten of secrets al aanwezig zijn (zonder waarde te tonen)
        print(f"-- MAGNIT_EMAIL secret gezet: {bool(os.environ.get('MAGNIT_EMAIL'))}")
        print(f"-- MAGNIT_WACHTWOORD secret gezet: {bool(os.environ.get('MAGNIT_WACHTWOORD'))}")

        browser.close()


if __name__ == "__main__":
    main()
