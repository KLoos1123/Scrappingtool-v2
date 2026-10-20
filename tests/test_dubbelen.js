// Draaien met: node tests/test_dubbelen.js
const assert = require('assert');
const { groepeer, normTekst } = require('../web/dubbelen.js');

const D = s => Date.parse(s);
const rij = (bron, tender_id, titel, organisatie, pub, deadline) =>
  ({ bron, tender_id, titel, organisatie, _pub: pub ? D(pub) : null, _deadline: deadline ? D(deadline) : null });
const groepVan = (groepen, r) => groepen.find(g => g.includes(r));

assert.strictEqual(normTekst('Adviseur (m/v) Kunstwerken – 16318 TK1'), 'adviseur kunstwerken tk1');
assert.strictEqual(normTekst('Gemeente Rotterdam'), normTekst('gemeente  ROTTERDAM'));

// zelfde opdracht op Mercell en TenderNed (TenderNed zonder deadline)
{
  const a = rij('mercell', '1', 'Realisatie zonnepanelen Limburgs Museum', 'Provincie Limburg', '2026-07-01', '2026-07-21');
  const b = rij('tenderned', '9', 'Realisatie zonnepanelen Limburgs Museum', 'Provincie Limburg', '2026-07-03', null);
  assert.strictEqual(groepVan(groepeer([a, b]), a).length, 2);
}

// Flextender en opdrachtoverheid: deadline een dag verschoven -> één groep
{
  const a = rij('flextender', '33050', 'Senior Test Engineer', 'Kadaster', '2026-10-13', '2026-10-27');
  const b = rij('opdrachtoverheid', 'flextender_33050', 'Senior Test Engineer', 'Kadaster', '2026-10-14', '2026-10-26T16:00:00');
  assert.strictEqual(groepVan(groepeer([a, b]), a).length, 2);
}

// Flextender-koppeling via tender_id werkt ook bij afwijkende titel
{
  const a = rij('flextender', '777', 'Adviseur Circulair Beleid', 'Provincie Overijssel', '2026-10-01', null);
  const b = rij('opdrachtoverheid', 'flextender_777', 'Adviseur circulair beleid kunstwerken', 'Prov. Overijssel', '2026-10-01', null);
  assert.strictEqual(groepVan(groepeer([a, b]), a).length, 2);
}

// dezelfde bron die een rol opnieuw uitzet blijft apart
{
  const a = rij('mercell', '1', 'Mendix Engineer - cluster BCO', 'Gemeente Rotterdam', '2026-07-01', '2026-07-15');
  const b = rij('mercell', '2', 'Mendix Engineer - cluster BCO', 'Gemeente Rotterdam', '2026-07-02', '2026-07-22');
  assert.strictEqual(groepeer([a, b]).length, 2);
}

// zelfde titel bij andere bron maar maanden later: nieuwe uitvraag, apart
{
  const a = rij('mercell', '1', 'Communicatieadviseur', 'Provincie Utrecht', '2026-05-01', '2026-05-20');
  const b = rij('opdrachtoverheid', 'x', 'Communicatieadviseur', 'Provincie Utrecht', '2026-09-01', '2026-09-20');
  assert.strictEqual(groepeer([a, b]).length, 2);
}

// deadlines te ver uit elkaar: apart, ook al verschenen ze tegelijk
{
  const a = rij('mercell', '1', 'Projectleider', 'Gemeente Delft', '2026-09-01', '2026-09-10');
  const b = rij('tenderned', '2', 'Projectleider', 'Gemeente Delft', '2026-09-02', '2026-10-30');
  assert.strictEqual(groepeer([a, b]).length, 2);
}

// zonder organisatie wordt niet op titel samengevoegd
{
  const a = rij('freelance.nl', '1', 'SAP EWM Consultant', null, '2026-10-01', null);
  const b = rij('striive', '2', 'SAP EWM Consultant', null, '2026-10-01', null);
  assert.strictEqual(groepeer([a, b]).length, 2);
}

// drie bronnen, een herhaalde Mercell-ronde komt in een eigen groep
{
  const a = rij('mercell', '1', 'Functioneel Beheerder Youforce', 'Gemeente Rotterdam', '2026-09-04', '2026-09-08');
  const b = rij('opdrachtoverheid', 'm1', 'Functioneel Beheerder Youforce', 'Gemeente Rotterdam', '2026-09-04', '2026-09-07T16:00:00');
  const c = rij('mercell', '2', 'Functioneel Beheerder Youforce', 'Gemeente Rotterdam', '2026-09-17', '2026-09-25');
  const g = groepeer([a, b, c]);
  assert.strictEqual(groepVan(g, a).length, 2);
  assert.ok(groepVan(g, a).includes(b));
  assert.strictEqual(groepVan(g, c).length, 1);
}

console.log('dubbelen: alle tests geslaagd');
