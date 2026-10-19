import json
import os
import sqlite3
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import db
import verrijking

VOORBEELD = {
    "eindklant": "Stedin", "eindklant_zekerheid": "genoemd", "eindklant_omschrijving": None,
    "sector": "Energie", "rol": "SAP EWM consultant", "modules": ["SAP EWM", "SAP S/4HANA"],
    "vaardigheden": ["RF-scanning"], "senioriteit": "senior", "ervaring_jaren_min": 5,
    "uren_per_week_min": 32, "uren_per_week_max": 40, "tarief_min": 95, "tarief_max": 110,
    "startdatum": "2026-11-01", "looptijd_maanden": 6, "werkvorm": "hybride",
    "talen": ["Nederlands"], "samenvatting": "Inrichting van SAP EWM.",
}


def antwoord(data=None, stop="end_turn", model="claude-opus-5-5"):
    blokken = [SimpleNamespace(type="thinking", thinking="")]
    if data is not None:
        blokken.append(SimpleNamespace(type="text", text=json.dumps(data)))
    return SimpleNamespace(stop_reason=stop, content=blokken, model=model)


class NepClient:
    def __init__(self, maak_antwoord):
        self.verzoeken = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))
        self._maak = maak_antwoord

    def _create(self, **kwargs):
        self.verzoeken.append(kwargs)
        return self._maak(kwargs)


TENDER = {"bron": "freelance.nl", "tender_id": "1", "titel": "SAP EWM consultant",
          "organisatie": None, "locatie": "Utrecht", "oms_hash": "h",
          "omschrijving": "<p>Voor <b>Stedin</b> zoeken wij&nbsp;een consultant.</p>"}


class Verrijk(unittest.TestCase):
    def test_verzoek_en_antwoord(self):
        client = NepClient(lambda kw: antwoord(VOORBEELD))
        data, model = verrijking.verrijk(client, TENDER)
        self.assertEqual(data, VOORBEELD)
        self.assertEqual(model, "claude-opus-5-5")
        kw = client.verzoeken[0]
        self.assertEqual(kw["model"], "claude-opus-5-5")
        self.assertEqual(kw["output_config"]["effort"], "low")
        self.assertEqual(kw["output_config"]["format"]["schema"], verrijking.SCHEMA)
        self.assertEqual(kw["fallbacks"], "default")
        self.assertEqual(kw["betas"], ["server-side-fallback-2026-07-01"])
        inhoud = kw["messages"][0]["content"]
        self.assertIn("Voor Stedin zoeken wij een consultant.", inhoud)
        self.assertNotIn("<p>", inhoud)
        self.assertIn("<opdrachtgever_volgens_bron>onbekend</opdrachtgever_volgens_bron>", inhoud)

    def test_geen_fallback_voor_haiku(self):
        client = NepClient(lambda kw: antwoord(VOORBEELD, model="claude-haiku-5-5"))
        with mock.patch.object(verrijking, "MODEL", "claude-haiku-5-5"):
            verrijking.verrijk(client, TENDER)
        self.assertNotIn("fallbacks", client.verzoeken[0])

    def test_weigering_en_afgekapt(self):
        for stop in ("refusal", "max_tokens"):
            with self.subTest(stop=stop):
                client = NepClient(lambda kw, s=stop: antwoord(None, stop=s))
                self.assertEqual(verrijking.verrijk(client, TENDER), (None, None))

    def test_verrijk_alle_telt_mislukte(self):
        def maak(kw):
            if "kapot" in kw["messages"][0]["content"]:
                return antwoord(None, stop="refusal")
            return antwoord(VOORBEELD, model="claude-opus-5")
        tenders = [dict(TENDER, tender_id=str(i), titel="kapot" if i == 2 else "ok") for i in range(4)]
        resultaten, mislukt = verrijking.verrijk_alle(tenders, client=NepClient(maak))
        self.assertEqual(mislukt, 1)
        self.assertEqual(sorted(r["tender_id"] for r in resultaten), ["0", "1", "3"])
        self.assertEqual(resultaten[0]["model"], "claude-opus-5")  # model van de fallback

    def test_schema(self):
        self.assertEqual(set(verrijking.SCHEMA["required"]), set(VOORBEELD))
        self.assertFalse(verrijking.SCHEMA["additionalProperties"])


class Opslag(unittest.TestCase):
    def setUp(self):
        self.map = tempfile.mkdtemp()
        self.oud = db.DB
        db.DB = os.path.join(self.map, "t.db")
        conn = db.verbind()
        conn.execute("CREATE TABLE beschrijvingen (bron TEXT, tender_id TEXT, omschrijving TEXT, opgehaald_op TEXT)")
        tenders = [  # (tender_id, deadline, eerst_gezien, omschrijving)
            ("oud", "2020-01-01", "2026-10-01", "tekst"),           # verlopen
            ("open", "2099-01-01", "2026-10-02", "tekst"),
            ("zonder", None, "2026-10-03", "tekst"),
            ("leeg", None, "2026-10-04", ""),                       # geen omschrijving
            ("nieuwst", None, "2026-10-05", "tekst"),
        ]
        for tid, dl, eg, oms in tenders:
            conn.execute("INSERT INTO tenders (bron, tender_id, titel, deadline, eerst_gezien, laatst_gezien) "
                         "VALUES ('b', ?, ?, ?, ?, ?)", (tid, "titel " + tid, dl, eg, eg))
            conn.execute("INSERT INTO beschrijvingen VALUES ('b', ?, ?, '')", (tid, oms))
        conn.commit()
        conn.close()

    def tearDown(self):
        db.DB = self.oud

    def test_selectie_volgorde_en_hash(self):
        ids = [r["tender_id"] for r in db.te_verrijken(verrijking.maak_hash, 10)]
        self.assertEqual(ids, ["nieuwst", "zonder", "open"])
        self.assertEqual(len(db.te_verrijken(verrijking.maak_hash, 2)), 2)

        kandidaten = db.te_verrijken(verrijking.maak_hash, 10)
        db.verrijkingen_opslaan([{**k, "model": "m", "data": VOORBEELD} for k in kandidaten])
        self.assertEqual(db.te_verrijken(verrijking.maak_hash, 10), [])

        conn = db.verbind()
        conn.execute("UPDATE beschrijvingen SET omschrijving = 'nieuwe tekst' WHERE tender_id = 'open'")
        conn.commit()
        conn.close()
        self.assertEqual([r["tender_id"] for r in db.te_verrijken(verrijking.maak_hash, 10)], ["open"])

    def test_sync_vlag(self):
        kandidaten = db.te_verrijken(verrijking.maak_hash, 10)
        db.verrijkingen_opslaan([{**k, "model": "m", "data": VOORBEELD} for k in kandidaten])
        open_ = db.verrijkingen(alleen_ongesynct=True)
        self.assertEqual(len(open_), 3)
        self.assertEqual(open_[0]["data"], VOORBEELD)
        db.markeer_gesynct(open_[:2])
        self.assertEqual(len(db.verrijkingen(alleen_ongesynct=True)), 1)
        self.assertEqual(len(db.verrijkingen()), 3)


if __name__ == "__main__":
    unittest.main()
