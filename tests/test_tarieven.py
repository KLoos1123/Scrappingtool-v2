import unittest

from tarieven import haal_tarief, haal_uren, uit_ai, uit_bron, uren_uit_bron


class HaalTarief(unittest.TestCase):
    def test_bedragen(self):
        gevallen = {
            "Tarief: €80 - €85 per uur excl. btw": "€ 80 – 85 /uur",            # freelance.nl
            "Richttarief: € 63,11 per uur all-in, excl. btw": "€ 63,11 /uur",   # harveynash
            "Max tarief: 71,90 EUR all-in ex BTW": "max € 71,90 /uur",
            "Richttarief: Middenschaal € 110 tot € 120": "€ 110 – 120 /uur",
            "maximaal uurtarief van € 150. Takenpakket": "max € 150 /uur",      # opdrachtoverheid
            "<li><p>Tarief: €95</p></li>": "€ 95 /uur",
            "Dagtarief: € 450 – € 550, afhankelijk van ervaring": "€ 450 – 550 /dag",
            "Tarief: marktconform": "marktconform",
        }
        for tekst, verwacht in gevallen.items():
            with self.subTest(tekst=tekst):
                self.assertEqual(haal_tarief(tekst)["tarief"], verwacht)

    def test_geen_tarief(self):
        for tekst in [None, "", "Salarisrange: €3200 - €3600 per maand, 40 uur",
                      "Tarief / salaris: €4.500 tot €6.500 bruto per maand",
                      "Uurtarief is exclusief reiskosten à €0,23/km.",
                      "Op een project van € 30.000 is dat € 3.000.",
                      "Inzet: 32-40 uur per week"]:
            with self.subTest(tekst=tekst):
                self.assertIsNone(haal_tarief(tekst))

    def test_min_max(self):
        self.assertEqual(haal_tarief("Tarief: €80 - €85 per uur"),
                         {"tarief": "€ 80 – 85 /uur", "tarief_min": 80, "tarief_max": 85})
        self.assertEqual(haal_tarief("Max tarief: 90 EUR per uur")["tarief_min"], None)

    def test_uit_ai(self):
        self.assertEqual(uit_ai({"tarief_min": 85, "tarief_max": 95})["tarief"], "€ 85 – 95 /uur")
        self.assertEqual(uit_ai({"tarief_min": None, "tarief_max": 100})["tarief"], "€ 100 /uur")
        self.assertIsNone(uit_ai({"tarief_min": None, "tarief_max": None}))
        self.assertIsNone(uit_ai({"tarief_min": 5000, "tarief_max": 6000}))  # maandsalaris


    def test_uit_bron(self):
        # freelance.nl levert rateFrom/rateTo als tarief_min/tarief_max
        self.assertEqual(uit_bron({"tarief_min": 80, "tarief_max": 100})["tarief"], "€ 80 – 100 /uur")
        self.assertIsNone(uit_bron({"tarief_min": None, "tarief_max": None}))
        self.assertIsNone(uit_bron({}))


class HaalUren(unittest.TestCase):
    def test_uren(self):
        gevallen = {   # letterlijk uit omschrijvingen
            "Inzet: bij voorkeur 36–40 uur per week": "36–40 u/w",
            "24 / 36 uur per week €50 / €70": "24–36 u/w",
            "Uren: 16 tot 32 uur per week - Tarief": "16–32 u/w",
            "Start: 16 nov 2026, 36 uur/week.": "36 u/w",
            "Uren per week: 32 / 40 Startdatum": "32–40 u/w",
            "Aantal uur per week: 16 Functie-omschrijving": "16 u/w",
            "Amersfoort | 40 uur p/w | Start": "40 u/w",
        }
        for tekst, verwacht in gevallen.items():
            with self.subTest(tekst=tekst):
                self.assertEqual(haal_uren(tekst)["uren"], verwacht)

    def test_geen_uren(self):
        for tekst in [None, "", "Opdrachtduur: 6 maanden", "8 uur per dag", "Inzet: 1 FTE",
                      "Beschikbaarheid in uren per week", "Reacties voor 12 uur 's middags"]:
            with self.subTest(tekst=tekst):
                self.assertIsNone(haal_uren(tekst))

    def test_uit_bron(self):
        self.assertEqual(uren_uit_bron({"uren_per_week": "32-40"})["uren"], "32–40 u/w")
        self.assertEqual(uren_uit_bron({"uren_per_week": "?-36"})["uren"], "36 u/w")
        self.assertIsNone(uren_uit_bron({"uren_per_week": "?-?"}))


if __name__ == "__main__":
    unittest.main()
