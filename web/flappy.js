/* Easter egg: klik 10 keer snel achter elkaar op het Profource-logo en je speelt
   Flappy Mat. Los bestand, geen afhankelijkheden; koppelen met
   flappyMat.koppel(element). Tik, klik, spatie of pijl omhoog om te vliegen,
   Esc of × om te sluiten. Elk punt levert een credit op; met credits koop je
   in de winkel onder het speelveld andere personages. Ingelogd worden beste
   score, credits en gekochte personages per gebruiker in Supabase bewaard
   (tabel flappy_scores, zie supabase/flappy_scores.sql) en staat er een
   ranglijst naast het speelveld; zonder die tabel valt alles terug op
   localStorage. */
(function(){
  const KLIKKEN = 10, KLIK_PAUZE = 1500;   // 10 klikken, hooguit 1,5 s ertussen
  const B = 400, H = 600, GROND = 70;      // logische afmetingen van het speelveld
  const ZWAARTE = 1500, FLAP = -430;       // px/s² en px/s
  const SNELHEID = 150, GAT = 165, BREEDTE = 66, AFSTAND = 230;
  const HOOFD_B = 44, HOOFD_H = 63;
  const MUNT_WAARDE = 3, MUNT_R = 13;      // gouden P-munten tussen de pijpen
  const MEDAILLES = [ [100,'Platina medaille','#9fd8e6'], [50,'Gouden medaille','#e3b23c'], [25,'Zilveren medaille','#b9c0c9'], [10,'Bronzen medaille','#c58a4f'] ];

  // Personages in de winkel. Een personage verschijnt pas als zijn foto laadt,
  // dus een nieuw gezicht toevoegen = foto in web/ zetten + regel hieronder.
  const PERSONAGES = [
    { id:'mat',     naam:'Mat',      src:'mat.png',     prijs:0 },
    { id:'p4',      naam:'Overloper', src:'persoon4.png', euro:5 },   // grap: niet te koop met credits
    { id:'p3',      naam:'Luckyluuk', src:'persoon3.png', prijs:50, bonus:2 },   // geluksvogel: dubbele credits
    { id:'p2',      naam:'Markkie',   src:'persoon2.png', prijs:200 },
  ];
  const BEELDEN = {};
  PERSONAGES.forEach(p => {
    const img = new Image();
    img.onload = () => { p.beschikbaar = true; if(overlay && !overlay.hidden) renderWinkel(); };
    img.src = p.src;
    BEELDEN[p.id] = img;
  });

  let overlay, canvas, ctx, frame = null, vorige = 0, spel;
  let beste = lees('flappyMatBest', 0), credits = lees('flappyMatCredits', 0);
  let gekocht = lees('flappyMatGekocht', ['mat']), keuze = lees('flappyMatKeuze', 'mat');
  let gespeeld = lees('flappyMatGespeeld', 0), melding = '';
  // online: { id, naam } zodra de gebruiker bekend is; fout: tabel ontbreekt of geen toegang
  const online = { id:null, naam:'', klaar:false, fout:false, lijst:[], plek:null };

  function lees(sleutel, standaard){
    try{ const v = localStorage.getItem(sleutel); return v == null ? standaard : JSON.parse(v); }catch(e){ return standaard; }
  }
  function bewaar(sleutel, waarde){ try{ localStorage.setItem(sleutel, JSON.stringify(waarde)); }catch(e){} }
  function huidigBeeld(){ const img = BEELDEN[keuze]; return img && img.naturalWidth ? img : BEELDEN.mat; }

  function nieuwSpel(){
    spel = { fase:'start', y:H/2 - 40, v:0, pijpen:[], munten:[], score:0, gepakt:0, afstand:0, wiebel:0, flits:0 };
  }

  function bouwOverlay(){
    const stijl = document.createElement('style');
    stijl.textContent = `
      .fm-overlay{ position:fixed; inset:0; z-index:1000; background:rgba(20,26,38,.72); display:flex; align-items:center; justify-content:center;
        padding:env(safe-area-inset-top,0px) env(safe-area-inset-right,0px) env(safe-area-inset-bottom,0px) env(safe-area-inset-left,0px); }
      .fm-overlay{ overflow-y:auto; }
      .fm-overlay[hidden]{ display:none; }
      .fm-doos{ margin:auto; padding:8px 0; display:flex; flex-direction:column; gap:10px; align-items:center; }
      .fm-doos canvas{ display:block; width:min(400px, 92vw, calc((92vh - 290px) * 2 / 3)); height:auto; aspect-ratio:2/3; border-radius:14px;
        box-shadow:0 20px 60px rgba(0,0,0,.45); touch-action:none; cursor:pointer; }
      .fm-veld{ position:relative; }
      .fm-sluit{ position:absolute; top:10px; right:10px; width:34px; height:34px; border:0; border-radius:50%;
        background:rgba(255,255,255,.9); color:#262b33; font:600 20px/1 'IBM Plex Sans',system-ui,sans-serif; cursor:pointer; }
      .fm-sluit:focus-visible{ outline:2px solid #2f5fa8; outline-offset:2px; }
      .fm-zij{ display:flex; flex-direction:column; gap:10px; width:min(400px, 92vw); }
      .fm-ranglijst{ background:#fff; border-radius:12px; padding:10px 12px; font-family:'IBM Plex Sans',system-ui,sans-serif; color:#262b33;
        box-shadow:0 10px 30px rgba(0,0,0,.3); font-size:13px; }
      .fm-ranglijst ol{ list-style:none; margin:0; padding:0; max-height:100px; overflow:auto; }
      .fm-ranglijst li{ display:grid; grid-template-columns:22px 22px 1fr auto; gap:8px; align-items:center; padding:3px 4px; border-radius:6px; }
      .fm-ranglijst li.ik{ background:#eef2fa; font-weight:600; }
      .fm-ranglijst li.los{ border-top:1px dashed #d9dde3; border-radius:0; margin-top:2px; padding-top:5px; }
      .fm-ranglijst .nr{ color:#7a8089; font-variant-numeric:tabular-nums; text-align:right; }
      .fm-ranglijst li:nth-child(-n+3) .nr{ color:#b8860b; font-weight:600; }
      .fm-ranglijst img{ width:20px; height:24px; object-fit:cover; border-radius:50%; }
      .fm-ranglijst .wie{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
      .fm-ranglijst .sc{ font-weight:600; font-variant-numeric:tabular-nums; }
      .fm-ranglijst .leeg{ color:#7a8089; font-size:12.5px; }
      @media (min-width:760px){
        .fm-doos{ flex-direction:row; align-items:flex-start; }
        .fm-doos canvas{ width:min(400px, calc(92vh * 2 / 3)); }
        .fm-zij{ width:270px; }
        .fm-winkel .fm-rij{ grid-template-columns:repeat(2, 1fr); }
        .fm-ranglijst ol{ max-height:300px; }
      }
      .fm-winkel{ background:#fff; border-radius:12px; padding:10px 12px; font-family:'IBM Plex Sans',system-ui,sans-serif; color:#262b33;
        box-shadow:0 10px 30px rgba(0,0,0,.3); }
      .fm-winkel-kop, .fm-rang-kop{ display:flex; justify-content:space-between; align-items:baseline; font-size:13px; margin-bottom:8px; }
      .fm-winkel-kop b{ font-size:14px; }
      .fm-credits{ font-weight:600; color:#2f5fa8; font-variant-numeric:tabular-nums; }
      .fm-rij{ display:grid; grid-template-columns:repeat(4, 1fr); gap:6px; }
      .fm-p{ min-width:0; display:flex; flex-direction:column; align-items:center; gap:4px; padding:6px 4px; border:1px solid #d9dde3; border-radius:10px; font-size:12px; text-align:center; }
      .fm-p.gekozen{ border-color:#2f5fa8; background:#eef2fa; }
      .fm-p img{ width:34px; height:46px; object-fit:cover; border-radius:50%; }
      .fm-p.op-slot img{ filter:grayscale(1) brightness(.85); }
      .fm-p button{ font:inherit; font-size:11.5px; font-weight:600; border:1px solid #2f5fa8; color:#2f5fa8; background:#fff; border-radius:6px; padding:3px 6px; cursor:pointer; white-space:nowrap; max-width:100%; }
      .fm-p button.koop{ background:#2f5fa8; color:#fff; }
      .fm-p button:disabled{ border-color:#d9dde3; color:#7a8089; background:#f6f7f9; cursor:default; }
      .fm-melding{ margin-top:8px; padding:6px 8px; border-radius:8px; background:#fff6e0; color:#7a5a00; font-size:12.5px; }
      .fm-p button:focus-visible{ outline:2px solid #2f5fa8; outline-offset:2px; }`;
    document.head.appendChild(stijl);
    overlay = document.createElement('div');
    overlay.className = 'fm-overlay';
    overlay.hidden = true;
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-label', 'Flappy Mat');
    overlay.innerHTML = '<div class="fm-doos"><div class="fm-veld"><canvas width="' + B + '" height="' + H + '" aria-label="Flappy Mat speelveld"></canvas><button class="fm-sluit" aria-label="Sluiten">×</button></div><div class="fm-zij"><div class="fm-ranglijst" aria-label="Ranglijst"></div><div class="fm-winkel" aria-label="Winkel"></div></div></div>';
    document.body.appendChild(overlay);
    canvas = overlay.querySelector('canvas');
    ctx = canvas.getContext('2d');
    canvas.addEventListener('pointerdown', e => { e.preventDefault(); actie(); });
    overlay.querySelector('.fm-sluit').addEventListener('click', sluit);
    overlay.addEventListener('pointerdown', e => { if(e.target === overlay) sluit(); });
    overlay.querySelector('.fm-winkel').addEventListener('click', e => {
      const knop = e.target.closest('button[data-id]');
      if(!knop) return;
      const p = PERSONAGES.find(x => x.id === knop.dataset.id);
      if(p.euro && !gekocht.includes(p.id)){
        melding = `${p.naam} kost echt € ${p.euro},-. Stuur een Tikkie naar Mathieu en misschien zet hij hem vrij.`;
        return renderWinkel();
      }
      if(!gekocht.includes(p.id)){
        if(credits < p.prijs) return;
        credits -= p.prijs; gekocht.push(p.id);
        bewaar('flappyMatCredits', credits); bewaar('flappyMatGekocht', gekocht);
      }
      keuze = p.id; bewaar('flappyMatKeuze', keuze);
      melding = '';
      renderWinkel();
      bewaarOnline();
      canvas.focus && canvas.blur();
    });
  }

  function open(){
    if(!overlay) bouwOverlay();
    nieuwSpel();
    renderWinkel();
    renderRanglijst();
    overlay.hidden = false;
    startOnline();
    document.addEventListener('keydown', toets, true);
    vorige = performance.now();
    frame = requestAnimationFrame(lus);
    overlay.querySelector('.fm-sluit').focus();
  }
  function sluit(){
    overlay.hidden = true;
    document.removeEventListener('keydown', toets, true);
    if(frame) cancelAnimationFrame(frame);
    frame = null;
  }
  function toets(e){
    if(e.key === 'Escape'){ e.preventDefault(); sluit(); return; }
    if(e.target.closest && e.target.closest('.fm-winkel')) return; // knoppen in de winkel gewoon laten werken
    if(e.key === ' ' || e.key === 'ArrowUp' || e.key === 'Enter'){ e.preventDefault(); e.stopPropagation(); actie(); }
  }

  function actie(){
    if(spel.fase === 'start'){ spel.fase = 'vliegen'; spel.v = FLAP; return; }
    if(spel.fase === 'vliegen'){ spel.v = FLAP; return; }
    if(spel.fase === 'over' && performance.now() - spel.einde > 450){ nieuwSpel(); spel.fase = 'vliegen'; spel.v = FLAP; }
  }

  function lus(nu){
    const dt = Math.min(0.033, (nu - vorige) / 1000);
    vorige = nu;
    stap(dt);
    teken();
    frame = requestAnimationFrame(lus);
  }

  function stap(dt){
    spel.wiebel += dt;
    if(spel.fase === 'start'){ spel.y = H/2 - 40 + Math.sin(spel.wiebel * 3) * 8; return; }
    if(spel.fase === 'over'){
      if(spel.y < H - GROND - HOOFD_H/2){ spel.v += ZWAARTE * dt; spel.y = Math.min(H - GROND - HOOFD_H/2, spel.y + spel.v * dt); }
      return;
    }
    spel.v += ZWAARTE * dt;
    spel.y += spel.v * dt;
    // pijpen en munten verschuiven en bijmaken; het tempo loopt op met de score
    const tempo = SNELHEID * (1 + Math.min(0.6, spel.score * 0.015));
    spel.afstand += tempo * dt;
    spel.flits = Math.max(0, spel.flits - dt);
    spel.pijpen.forEach(p => p.x -= tempo * dt);
    spel.munten.forEach(m => m.x -= tempo * dt);
    spel.pijpen = spel.pijpen.filter(p => p.x > -BREEDTE);
    spel.munten = spel.munten.filter(m => m.x > -MUNT_R && !m.weg);
    const laatste = spel.pijpen[spel.pijpen.length - 1];
    if(!laatste || laatste.x < B - AFSTAND){
      const marge = 70, hoogte = GAT - Math.min(35, spel.score * 1.2);   // gat wordt langzaam kleiner
      const gat = marge + Math.random() * (H - GROND - hoogte - marge * 2);
      spel.pijpen.push({ x:B + 10, gat, hoogte, geteld:false });
      // munt net achter deze pijp (nog buiten beeld), ongeveer op hoogte van het gat
      if(spel.pijpen.length > 1 && Math.random() < 0.55)
        spel.munten.push({ x:B + 10 + BREEDTE + (AFSTAND - BREEDTE) / 2, y:gat + hoogte / 2 + (Math.random() - 0.5) * 50 });
    }
    // score en botsingen (iets kleinere hitbox: het is een hoofd, geen vierkant)
    const hx = B * 0.3, kx = HOOFD_B * 0.36, ky = HOOFD_H * 0.4;
    for(const p of spel.pijpen){
      if(!p.geteld && p.x + BREEDTE < hx - kx){ p.geteld = true; spel.score++; }
      const binnenX = hx + kx > p.x && hx - kx < p.x + BREEDTE;
      const binnenGat = spel.y - ky > p.gat && spel.y + ky < p.gat + p.hoogte;
      if(binnenX && !binnenGat) return einde();
    }
    for(const m of spel.munten){
      if(Math.hypot(m.x - hx, m.y - spel.y) < MUNT_R + kx){ m.weg = true; spel.gepakt++; spel.flits = 0.35; }
    }
    if(spel.y + ky > H - GROND || spel.y - ky < 0) return einde();
  }
  function medaille(score){ return MEDAILLES.find(m => score >= m[0]); }

  function einde(){
    spel.fase = 'over';
    spel.einde = performance.now();
    spel.v = Math.max(spel.v, 0);
    if(spel.score > beste){ beste = spel.score; bewaar('flappyMatBest', beste); spel.record = true; }
    const p = PERSONAGES.find(x => x.id === keuze);
    spel.verdiend = (spel.score + spel.gepakt * MUNT_WAARDE) * ((p && p.bonus) || 1);
    credits += spel.verdiend; bewaar('flappyMatCredits', credits);
    gespeeld++; bewaar('flappyMatGespeeld', gespeeld);
    renderWinkel();
    bewaarOnline().then(laadRanglijst);
  }

  function teken(){
    // lucht
    // lucht: van dag naar avond naarmate je verder komt (vol donker vanaf 40 punten)
    const nacht = Math.min(1, spel.score / 40);
    const lucht = ctx.createLinearGradient(0, 0, 0, H);
    lucht.addColorStop(0, meng('#cfe0f5', '#1c2747', nacht)); lucht.addColorStop(1, meng('#eef3fa', '#6a4f7a', nacht));
    ctx.fillStyle = lucht; ctx.fillRect(0, 0, B, H);
    if(nacht > 0.5){
      ctx.fillStyle = `rgba(255,255,255,${(nacht - 0.5) * 1.6})`;
      for(let i = 0; i < 28; i++){
        const x = ((i * 89 - spel.afstand * 0.05) % B + B) % B, y = (i * 53) % (H - GROND - 120);
        ctx.fillRect(x, y, i % 3 ? 1.5 : 2.5, i % 3 ? 1.5 : 2.5);
      }
    }
    // wolkjes, langzaam meeschuivend
    ctx.fillStyle = `rgba(255,255,255,${0.85 - nacht * 0.6})`;
    for(let i = 0; i < 4; i++){
      const x = ((i * 137 - spel.afstand * 0.25) % (B + 120) + B + 120) % (B + 120) - 60, y = 70 + i * 95;
      ctx.beginPath(); ctx.ellipse(x, y, 34, 14, 0, 0, Math.PI * 2); ctx.ellipse(x + 26, y - 8, 24, 13, 0, 0, Math.PI * 2); ctx.fill();
    }
    // pijpen in de kleuren van de bronnenpagina
    for(const p of spel.pijpen){
      pijp(p.x, 0, p.gat, true);
      pijp(p.x, p.gat + p.hoogte, H - GROND - p.gat - p.hoogte, false);
    }
    for(const m of spel.munten) munt(m.x, m.y + Math.sin(spel.wiebel * 4 + m.x / 40) * 3);
    // grond
    ctx.fillStyle = '#d9c9a3'; ctx.fillRect(0, H - GROND, B, GROND);
    ctx.fillStyle = '#7fb069'; ctx.fillRect(0, H - GROND, B, 12);
    ctx.fillStyle = 'rgba(0,0,0,.06)';
    for(let x = -(spel.afstand % 24); x < B; x += 24) ctx.fillRect(x, H - GROND + 12, 12, GROND - 12);
    // het hoofd, kantelt mee met de snelheid
    const hoek = spel.fase === 'start' ? Math.sin(spel.wiebel * 3) * 0.08 : Math.max(-0.45, Math.min(1.1, spel.v / 600));
    ctx.save();
    ctx.translate(B * 0.3, spel.y);
    ctx.rotate(hoek);
    ctx.shadowColor = 'rgba(0,0,0,.25)'; ctx.shadowBlur = 6; ctx.shadowOffsetY = 3;
    const hoofd = huidigBeeld();
    if(hoofd.complete && hoofd.naturalWidth){
      ctx.beginPath(); ctx.ellipse(0, 0, HOOFD_B/2, HOOFD_H/2, 0, 0, Math.PI * 2); ctx.closePath();
      ctx.save(); ctx.clip(); ctx.shadowColor = 'transparent';
      ctx.drawImage(hoofd, -HOOFD_B/2, -HOOFD_H/2, HOOFD_B, HOOFD_H);
      ctx.restore();
      ctx.lineWidth = 2; ctx.strokeStyle = '#fff'; ctx.stroke();
    } else {
      ctx.fillStyle = '#f2c9a0'; ctx.beginPath(); ctx.ellipse(0, 0, HOOFD_B/2, HOOFD_H/2, 0, 0, Math.PI * 2); ctx.fill();
    }
    ctx.restore();
    // teksten
    ctx.textAlign = 'center';
    if(spel.fase !== 'start') tekst(String(spel.score), B/2, 70, 44, '#fff', true);
    if(spel.fase === 'vliegen' && spel.gepakt){
      ctx.textAlign = 'right';
      tekst('● ' + spel.gepakt, B - 16, 34, 18, spel.flits ? '#fff3c4' : '#e3b23c', true);
      ctx.textAlign = 'center';
    }
    if(spel.fase === 'start'){
      paneel(B/2, 150, 300, 120);
      tekst('Flappy Mat', B/2, 140, 34, '#2f5fa8');
      tekst('Tik, klik of spatie om te vliegen', B/2, 172, 15, '#5f656e');
      tekst('Pak de gouden munten: +' + MUNT_WAARDE + ' credits', B/2, 222, 13, '#b8860b');
      if(beste) tekst('Beste: ' + beste, B/2, 196, 14, '#5f656e');
    }
    if(spel.fase === 'over'){
      const med = medaille(spel.score);
      const extra = (spel.gepakt ? ` · ${spel.gepakt} munt${spel.gepakt > 1 ? 'en' : ''}` : '') + (spel.verdiend > spel.score + spel.gepakt * MUNT_WAARDE ? ' · Lucky ×2' : '');
      const onder = (extra ? 306 : 286) + (med ? 40 : 0) + (online.plek ? 22 : 0) + 16;
      paneel(B/2, (172 + onder) / 2, 320, onder - 172);
      tekst('Game over', B/2, 200, 30, '#bf3b2c');
      tekst('Score ' + spel.score + ' · Beste ' + beste, B/2, 234, 17, '#262b33');
      tekst(`${spel.record ? 'Nieuw record! ' : ''}+${spel.verdiend} credits`, B/2, 260, 15, spel.record ? '#2f8a4e' : '#2f5fa8');
      if(extra) tekst(extra.slice(3), B/2, 280, 13, '#5f656e');
      let y = extra ? 306 : 286;
      if(med){
        ctx.beginPath(); ctx.arc(B/2 - 52, y + 6, 15, 0, Math.PI * 2); ctx.fillStyle = med[2]; ctx.fill();
        ctx.lineWidth = 3; ctx.strokeStyle = 'rgba(0,0,0,.15)'; ctx.stroke();
        ctx.textAlign = 'left'; tekst(med[1], B/2 - 30, y + 12, 15, '#262b33'); ctx.textAlign = 'center';
        y += 40;
      }
      if(online.plek) { tekst('#' + online.plek + ' op de ranglijst', B/2, y, 14, '#262b33'); y += 22; }
      tekst('Tik of spatie: opnieuw · Esc: sluiten', B/2, y, 12, '#7a8089');
    }
  }

  function munt(x, y){
    ctx.beginPath(); ctx.arc(x, y, MUNT_R, 0, Math.PI * 2);
    ctx.fillStyle = '#e3b23c'; ctx.fill();
    ctx.lineWidth = 2.5; ctx.strokeStyle = '#b8860b'; ctx.stroke();
    ctx.font = "700 14px 'IBM Plex Sans', system-ui, sans-serif"; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillStyle = '#7a5a00'; ctx.fillText('P', x, y + 1);
    ctx.textBaseline = 'alphabetic';
  }
  function meng(a, b, t){
    const n = h => [1,3,5].map(i => parseInt(h.slice(i, i + 2), 16));
    const [x, y] = [n(a), n(b)];
    return 'rgb(' + x.map((v, i) => Math.round(v + (y[i] - v) * t)).join(',') + ')';
  }
  function pijp(x, y, h, boven){
    if(h <= 0) return;
    ctx.fillStyle = '#4a78c2'; ctx.fillRect(x, y, BREEDTE, h);
    ctx.fillStyle = 'rgba(255,255,255,.18)'; ctx.fillRect(x + 8, y, 8, h);
    ctx.fillStyle = '#2f5fa8';
    const kopY = boven ? y + h - 22 : y;
    ctx.fillRect(x - 5, kopY, BREEDTE + 10, 22);
  }
  function paneel(cx, cy, w, h){
    ctx.fillStyle = 'rgba(255,255,255,.92)';
    const x = cx - w/2, y = cy - h/2, r = 12;
    ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); ctx.fill();
  }
  function tekst(t, x, y, grootte, kleur, rand){
    ctx.font = `600 ${grootte}px 'IBM Plex Sans', system-ui, sans-serif`;
    if(rand){ ctx.lineWidth = 5; ctx.strokeStyle = 'rgba(38,43,51,.55)'; ctx.strokeText(t, x, y); }
    ctx.fillStyle = kleur; ctx.fillText(t, x, y);
  }

  function renderWinkel(){
    const el = overlay && overlay.querySelector('.fm-winkel');
    if(!el) return;
    const zichtbaar = PERSONAGES.filter(p => p.beschikbaar || p.id === 'mat');
    el.innerHTML = `<div class="fm-winkel-kop"><b>Personages</b><span>Credits: <span class="fm-credits">${credits}</span></span></div>
      <div class="fm-rij">${zichtbaar.map(p => {
        const heeft = gekocht.includes(p.id), gekozen = keuze === p.id;
        let knop;
        if(gekozen) knop = '<button disabled>Gekozen</button>';
        else if(heeft) knop = `<button data-id="${p.id}">Kies</button>`;
        else if(p.euro) knop = `<button class="koop" data-id="${p.id}">€ ${p.euro},-</button>`;
        else if(credits >= p.prijs) knop = `<button class="koop" data-id="${p.id}">Koop · ${p.prijs}</button>`;
        else knop = `<button disabled title="Nog ${p.prijs - credits} credits nodig">${p.prijs} credits</button>`;
        if(p.bonus) knop = `<small style="color:#2f8a4e">${p.bonus}× credits</small>` + knop;
        return `<div class="fm-p${gekozen ? ' gekozen' : ''}${heeft ? '' : ' op-slot'}"><img src="${p.src}" alt="">${p.naam}${knop}</div>`;
      }).join('')}</div>${melding ? `<div class="fm-melding" role="status">${melding}</div>` : ''}`;
  }

  // ---- online: per gebruiker opslaan + ranglijst (Supabase, tabel flappy_scores)
  function naamUitEmail(email){
    const deel = String(email || '').split('@')[0];
    return deel.split(/[._-]+/).filter(Boolean).map(w => w[0].toUpperCase() + w.slice(1)).join(' ') || 'Onbekend';
  }
  function esc(t){ return String(t).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
  function db(){ return window.supabase && window.supabase.from ? window.supabase : null; }

  let startBezig = null;
  function startOnline(){
    if(online.klaar || online.fout) return laadRanglijst();
    if(!startBezig) startBezig = koppelGebruiker().catch(() => { online.fout = true; }).then(() => { startBezig = null; renderRanglijst(); return laadRanglijst(); });
    return startBezig;
  }
  async function koppelGebruiker(){
    const sb = db();
    if(!sb || !window.getSession){ online.fout = true; return; }
    const sessie = await window.getSession();
    if(!sessie){ online.fout = true; return; }
    online.id = sessie.user.id;
    online.naam = naamUitEmail(sessie.user.email);
    const { data, error } = await sb.from('flappy_scores').select('*').eq('user_id', online.id).maybeSingle();
    if(error){ online.fout = true; return; }
    if(data){
      // de opgeslagen stand is leidend (dan klopt hij op elk apparaat); de beste score en
      // gekochte personages van deze browser gaan niet verloren
      beste = Math.max(beste, data.beste || 0);
      credits = data.credits || 0;
      gekocht = Array.from(new Set([...(data.gekocht || []), ...gekocht]));
      keuze = gekocht.includes(data.keuze) ? data.keuze : keuze;
      gespeeld = Math.max(gespeeld, data.gespeeld || 0);
      bewaar('flappyMatBest', beste); bewaar('flappyMatCredits', credits);
      bewaar('flappyMatGekocht', gekocht); bewaar('flappyMatKeuze', keuze);
    }
    online.klaar = true;
    renderWinkel();
    await bewaarOnline();
  }
  async function bewaarOnline(){
    const sb = db();
    if(!sb || !online.klaar) return;
    const { error } = await sb.from('flappy_scores').upsert({
      user_id:online.id, naam:online.naam, beste, credits, gekocht, keuze, gespeeld,
      bijgewerkt_op:new Date().toISOString(),
    }, { onConflict:'user_id' });
    if(error) console.warn('Flappy Mat: score niet opgeslagen', error.message);
  }
  async function laadRanglijst(){
    const sb = db();
    if(!sb || !online.klaar) return;
    const { data, error } = await sb.from('flappy_scores').select('user_id, naam, beste, keuze')
      .gt('beste', 0).order('beste', { ascending:false }).order('bijgewerkt_op', { ascending:true }).limit(10);
    if(error) return;
    online.lijst = data || [];
    const i = online.lijst.findIndex(r => r.user_id === online.id);
    if(i >= 0) online.plek = i + 1;
    else if(beste > 0){
      const { count } = await sb.from('flappy_scores').select('user_id', { count:'exact', head:true }).gt('beste', beste);
      online.plek = count == null ? null : count + 1;
    } else online.plek = null;
    renderRanglijst();
  }
  function renderRanglijst(){
    const el = overlay && overlay.querySelector('.fm-ranglijst');
    if(!el) return;
    const kop = '<div class="fm-rang-kop"><b>Ranglijst</b><span>Jouw beste: <span class="fm-credits">' + beste + '</span></span></div>';
    if(online.fout){ el.innerHTML = kop + '<div class="leeg">Ranglijst is nog niet actief; je score wordt in deze browser bewaard.</div>'; return; }
    if(!online.klaar){ el.innerHTML = kop + '<div class="leeg">Laden…</div>'; return; }
    const beeld = id => (PERSONAGES.find(p => p.id === id && (p.beschikbaar || p.id === 'mat')) || PERSONAGES[0]).src;
    const rij = (nr, r, extra) => `<li class="${r.user_id === online.id ? 'ik' : ''}${extra || ''}"><span class="nr">${nr}</span><img src="${beeld(r.keuze)}" alt=""><span class="wie">${esc(r.naam)}</span><span class="sc">${r.beste}</span></li>`;
    let html = online.lijst.map((r, i) => rij(i + 1, r)).join('');
    if(online.plek && online.plek > online.lijst.length)
      html += rij(online.plek, { user_id:online.id, naam:online.naam, beste, keuze }, ' los');
    el.innerHTML = kop + (html ? '<ol>' + html + '</ol>' : '<div class="leeg">Nog geen scores. Zet de eerste neer!</div>');
  }

  // 10 klikken binnen korte tijd op het logo opent het spel
  function koppel(el){
    if(!el) return;
    let aantal = 0, laatst = 0;
    el.addEventListener('click', e => {
      const nu = Date.now();
      aantal = nu - laatst > KLIK_PAUZE ? 1 : aantal + 1;
      laatst = nu;
      if(aantal >= KLIKKEN){ aantal = 0; e.preventDefault(); open(); }
    });
  }

  window.flappyMat = { koppel, open };
})();
