import unittest

from datums import normaliseer_datum, normaliseer_rij


class NormaliseerDatum(unittest.TestCase):
    def test_bronformaten(self):
        gevallen = {
            "28 juli 2026agenda": "2026-07-28",          # flextender
            "3 augustus 2026agenda": "2026-08-03",
            "11 september 2026": "2026-09-11",
            "21 okt 2026 07:00 uur": "2026-10-21T07:00:00+02:00",  # magnit, zomertijd
            "2 dec 2026 18:30 uur": "2026-12-02T18:30:00+01:00",   # wintertijd
            "16-09-2026": "2026-09-16",                  # heart
            "30-9-2027": "2027-09-30",                   # portofrotterdam
            "1-11-2026": "2026-11-01",
        }
        for invoer, verwacht in gevallen.items():
            with self.subTest(invoer=invoer):
                self.assertEqual(normaliseer_datum(invoer), verwacht)

    def test_ongewijzigd(self):
        for waarde in [None, "", "2026-08-03T00:00:00.000Z", "2026-08-03 10:00:00",
                       "2026-07-29", "binnenkort", "31-02-2026", "12 foo 2026"]:
            with self.subTest(waarde=waarde):
                self.assertEqual(normaliseer_datum(waarde), waarde)

    def test_rij(self):
        rij = {"titel": "x", "deadline": "28 juli 2026agenda", "publicatiedatum": "15-10-2026"}
        normaliseer_rij(rij)
        self.assertEqual(rij, {"titel": "x", "deadline": "2026-07-28", "publicatiedatum": "2026-10-15"})


if __name__ == "__main__":
    unittest.main()
