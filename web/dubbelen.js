/* Herkent dezelfde opdracht die via meerdere bronnen binnenkomt (bv. Mercell en
   TenderNed, of Flextender en opdrachtoverheid). Werkt op de verrijkte rijen van
   het dashboard: bron, tender_id, titel, organisatie, _pub en _deadline (ms). */
(function (root) {
  const DAG = 86400000;
  const MAX_VERSCHIJNEN = 14 * DAG;  // publicatie of eerste keer gezien
  const MAX_DEADLINE = 3 * DAG;      // bronnen noteren de sluitingstijd soms een dag anders

  function normTekst(s) {
    return String(s || '').toLowerCase().normalize('NFKD').replace(/[̀-ͯ]/g, '')
      .replace(/\(.*?\)|\[.*?\]/g, ' ').replace(/\b\d+\b/g, ' ')
      .replace(/[^a-z0-9]+/g, ' ').trim().replace(/\s+/g, ' ');
  }

  // Een bron zet dezelfde rol soms meerdere keren uit (andere ronde, andere
  // deadline); die blijven apart. Samenvoegen gebeurt alleen tussen bronnen.
  function pastBij(groep, r) {
    return groep.every(g => g.bron !== r.bron
      && !(g._pub != null && r._pub != null && Math.abs(g._pub - r._pub) > MAX_VERSCHIJNEN)
      && !(g._deadline != null && r._deadline != null && Math.abs(g._deadline - r._deadline) > MAX_DEADLINE));
  }

  // Geeft groepen (arrays van rijen) terug; elke rij zit in precies één groep.
  function groepeer(rows) {
    const ouder = rows.map((_, i) => i);
    const vind = i => { while (ouder[i] !== i) { ouder[i] = ouder[ouder[i]]; i = ouder[i]; } return i; };
    const verenig = (a, b) => { ouder[vind(b)] = vind(a); };

    // opdrachtoverheid plaatst Flextender-opdrachten door als "flextender_<id>"
    const flex = new Map();
    rows.forEach((r, i) => { if (r.bron === 'flextender') flex.set(String(r.tender_id), i); });
    rows.forEach((r, i) => {
      const m = r.bron === 'opdrachtoverheid' && /^flextender_(.+)$/.exec(String(r.tender_id));
      if (m && flex.has(m[1])) verenig(flex.get(m[1]), i);
    });

    const emmers = new Map();
    rows.forEach((r, i) => {
      const t = normTekst(r.titel), o = normTekst(r.organisatie);
      if (!t || !o) return;
      const k = t + '|' + o;
      if (!emmers.has(k)) emmers.set(k, []);
      emmers.get(k).push(i);
    });
    for (const idx of emmers.values()) {
      if (idx.length < 2) continue;
      idx.sort((a, b) => (rows[a]._pub ?? 0) - (rows[b]._pub ?? 0));
      const clusters = [];
      for (const i of idx) {
        const c = clusters.find(c => pastBij(c.map(j => rows[j]), rows[i]));
        if (c) { c.push(i); verenig(c[0], i); } else clusters.push([i]);
      }
    }

    const groepen = new Map();
    rows.forEach((r, i) => {
      const w = vind(i);
      if (!groepen.has(w)) groepen.set(w, []);
      groepen.get(w).push(r);
    });
    return [...groepen.values()];
  }

  const Dubbelen = { groepeer, normTekst };
  root.Dubbelen = Dubbelen;
  if (typeof module !== 'undefined') module.exports = Dubbelen;
})(typeof window !== 'undefined' ? window : globalThis);
