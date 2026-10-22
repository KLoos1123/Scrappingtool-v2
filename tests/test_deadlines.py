import unittest

from deadlines import haal_deadline, vul_aan


class HaalDeadline(unittest.TestCase):
    REF = "2026-07-20"

    def test_formaten(self):
        gevallen = {   # allemaal letterlijk uit freelance.nl-omschrijvingen
            "Deadline: 13-08-2026 om 13:00": "2026-08-13",
            "Locatie regio Den Helder Deadline 8 aug. 2026 (ma.), Opdrachtomschrijving": "2026-08-08",
            "Sluitingsdatum: woensdag 5 augustus 2026 om 12.00 uur.": "2026-08-05",
            "Deadline inschrijven: 28 juli om 14:00": "2026-07-28",
            "Deadline voor het voorstellen van kandidaten: 26-7 16 uur": "2026-07-26",
            "Deadline voor het voorstellen van kandidaten: 12:00, 05-08": "2026-08-05",
            "Reageren kan tot en met 11 augustus 2026.": "2026-08-11",
            "Aanbieden tot 03/09/2026 Maximum uurtarief": "2026-09-03",
            "Deadline indienen van cv en motivatie : maandag 10 augustus": "2026-08-10",
            "Deadline aanleveren cv's: donderdag 22 oktober": "2026-10-22",
        }
        for tekst, verwacht in gevallen.items():
            with self.subTest(tekst=tekst):
                self.assertEqual(haal_deadline(tekst, self.REF), verwacht)

    def test_jaarwisseling(self):
        # gepubliceerd in december, deadline "8 januari" valt in het volgende jaar
        self.assertEqual(haal_deadline("Deadline: 8 januari om 12:00", "2026-12-15"), "2027-01-08")

    def test_geen_deadline(self):
        for tekst in [None, "", "de kar trekken om de harde deadline rond de jaarwisseling te halen",
                      "Inzet: 32-40 uur per week, start 1 september",
                      "Deadline voor het voorstellen van kandidaten: Dit is een spoedaanvraag",
                      "Deadline: 1 oktober 2019"]:          # ver voor de publicatie
            with self.subTest(tekst=tekst):
                self.assertIsNone(haal_deadline(tekst, self.REF))

    def test_vul_aan(self):
        rijen = [{"omschrijving": "Deadline: 13-08-2026", "publicatiedatum": self.REF},
                 {"omschrijving": "Deadline: 13-08-2026", "deadline": "2026-09-01"},   # bron wint
                 {"omschrijving": None}]
        self.assertEqual(vul_aan(rijen), 1)
        self.assertEqual([r.get("deadline") for r in rijen], ["2026-08-13", "2026-09-01", None])


if __name__ == "__main__":
    unittest.main()
