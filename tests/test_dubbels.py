import unittest

from dubbels import groepeer, titel_sleutel


def rij(bron, titel, org, deadline=None):
    return {"bron": bron, "tender_id": f"{bron}-{titel}", "titel": titel, "organisatie": org, "deadline": deadline}


class Dubbels(unittest.TestCase):
    def groepen(self, rijen):
        return sorted(sorted(r["bron"] for r in g) for g in groepeer(rijen))

    def test_zelfde_opdracht_bij_twee_bronnen(self):
        g = self.groepen([rij("mipublic", "Business Analist (ZZP)", "UWV", "2026-11-01T12:00"),
                          rij("freep", "Business analist", "UWV", "2026-11-03")])
        self.assertEqual(g, [["freep", "mipublic"]])

    def test_andere_klant_of_deadline_is_iets_anders(self):
        self.assertEqual(len(groepeer([rij("a", "Business Analist", "UWV"), rij("b", "Business Analist", "SVB")])), 2)
        self.assertEqual(len(groepeer([rij("a", "Business Analist", "UWV", "2026-11-01"),
                                       rij("b", "Business Analist", "UWV", "2026-12-01")])), 2)

    def test_zonder_organisatie_alleen_bij_een_passende_groep(self):
        self.assertEqual(self.groepen([rij("a", "Senior Java ontwikkelaar", "Rijkswaterstaat"),
                                       rij("b", "Senior Java ontwikkelaar", "")]), [["a", "b"]])
        self.assertEqual(len(groepeer([rij("a", "Senior Java ontwikkelaar", ""),
                                       rij("b", "Senior Java ontwikkelaar", "")])), 2)

    def test_titel_sleutel(self):
        self.assertEqual(titel_sleutel("A0723819 - Junior Medewerker (2 FTE) | ZZP"), "junior medewerker")


if __name__ == "__main__":
    unittest.main()
