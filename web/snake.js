/* Tweede easter egg: Snake met de collega's. Openen met de Konami-code
   (↑ ↑ ↓ ↓ ← → ← → B A), door ergens "snake" te typen, of op een telefoon door
   het Profource-logo even ingedrukt te houden. Koppelen met snakeMat.koppel(el).
   Je slang begint met het personage dat je in Flappy Mat hebt gekozen en
   verzamelt collega's in zijn staart; gouden P-munten geven extra punten. Elk
   punt is een credit in dezelfde pot als Flappy Mat (via flappyMat.geefCredits).
   Beste score blijft per browser bewaard. */
(function(){
  const N = 16, CEL = 25, KOP = 44;          // 16×16 velden van 25 px, plus een balk bovenin
  const B = N * CEL, H = N * CEL + KOP;
  const START_TEMPO = 150, MIN_TEMPO = 70;    // ms per stap
  const MUNT_PUNTEN = 5, MUNT_DUUR = 7;       // seconden
  const KONAMI = ['ArrowUp','ArrowUp','ArrowDown','ArrowDown','ArrowLeft','ArrowRight','ArrowLeft','ArrowRight','b','a'];
  const RICHTING = { ArrowUp:[0,-1], ArrowDown:[0,1], ArrowLeft:[-1,0], ArrowRight:[1,0],
                     w:[0,-1], s:[0,1], a:[-1,0], d:[1,0] };

  // Gezichten: dezelfde personages als Flappy Mat (zelfde bestanden in web/)
  const RESERVE = [
    { id:'mat', naam:'Mat', src:'mat.png' }, { id:'p4', naam:'Overloper', src:'persoon4.png' },
    { id:'p3', naam:'Luckyluuk', src:'persoon3.png' }, { id:'p5', naam:'Troy', src:'persoon5.png' },
    { id:'p2', naam:'Markkie', src:'persoon2.png' }, { id:'p6', naam:'Chantal', src:'persoon6.png' },
  ];
  const BEELD = {};
  let gezichten = [];
  function laadGezichten(){
    const lijst = (window.flappyMat && flappyMat.personages && flappyMat.personages().length) ? flappyMat.personages() : RESERVE;
    gezichten = lijst;
    lijst.forEach(p => { if(!BEELD[p.id]){ const img = new Image(); img.src = p.src; BEELD[p.id] = img; } });
  }
  function eigenKeuze(){
    const k = window.flappyMat && flappyMat.keuze ? flappyMat.keuze() : 'mat';
    return gezichten.some(p => p.id === k) ? k : 'mat';
  }
  function naamVan(id){ const p = gezichten.find(x => x.id === id); return p ? p.naam : ''; }

  let overlay, canvas, ctx, frame = null, vorige = 0, opgespaard = 0, spel;
  let beste = lees('snakeMatBest', 0);
  function lees(k, d){ try{ const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); }catch(e){ return d; } }
  function bewaar(k, v){ try{ localStorage.setItem(k, JSON.stringify(v)); }catch(e){} }

  function nieuwSpel(){
    const kop = eigenKeuze(), m = Math.floor(N / 2);
    // slang = posities (kop eerst), ids = het gezicht per segment in dezelfde volgorde
    spel = { fase:'start', slang:[{ x:m, y:m }, { x:m - 1, y:m }, { x:m - 2, y:m }], ids:[kop, kop, kop],
             richting:[1, 0], wachtrij:[], score:0, verzameld:0, munten:0, tempo:START_TEMPO,
             eten:null, munt:null, laatsteNaam:'', naamTijd:0 };
    spel.eten = vrijVeld(); spel.eten.id = willekeurigeCollega();
  }
  function willekeurigeCollega(){
    const kop = spel ? spel.ids[0] : eigenKeuze();
    const anderen = gezichten.filter(p => p.id !== kop && BEELD[p.id] && BEELD[p.id].naturalWidth);
    const lijst = anderen.length ? anderen : gezichten;
    return lijst[Math.floor(Math.random() * lijst.length)].id;
  }
  function bezet(x, y){
    return spel.slang.some(d => d.x === x && d.y === y) || (spel.eten && spel.eten.x === x && spel.eten.y === y)
      || (spel.munt && spel.munt.x === x && spel.munt.y === y);
  }
  function vrijVeld(){
    for(let i = 0; i < 500; i++){
      const x = Math.floor(Math.random() * N), y = Math.floor(Math.random() * N);
      if(!bezet(x, y)) return { x, y };
    }
    return { x:0, y:0 };
  }

  function bouwOverlay(){
    const stijl = document.createElement('style');
    stijl.textContent = `
      .sm-overlay{ position:fixed; inset:0; z-index:1000; background:rgba(20,26,38,.72); display:flex; align-items:center; justify-content:center; overflow-y:auto; }
      .sm-overlay[hidden]{ display:none; }
      .sm-veld{ position:relative; margin:auto; padding:8px 0; }
      .sm-veld canvas{ display:block; width:min(400px, 94vw, calc(90vh * ${B} / ${H})); height:auto; aspect-ratio:${B}/${H}; border-radius:14px;
        box-shadow:0 20px 60px rgba(0,0,0,.45); touch-action:none; cursor:pointer; }
      .sm-sluit{ position:absolute; top:14px; right:6px; width:32px; height:32px; border:0; border-radius:50%;
        background:rgba(255,255,255,.92); color:#262b33; font:600 20px/1 'IBM Plex Sans',system-ui,sans-serif; cursor:pointer; }
      .sm-sluit:focus-visible{ outline:2px solid #2f5fa8; outline-offset:2px; }`;
    document.head.appendChild(stijl);
    overlay = document.createElement('div');
    overlay.className = 'sm-overlay';
    overlay.hidden = true;
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-label', 'Snake met collega\'s');
    overlay.innerHTML = '<div class="sm-veld"><canvas width="' + B + '" height="' + H + '" aria-label="Snake speelveld"></canvas><button class="sm-sluit" aria-label="Sluiten">×</button></div>';
    document.body.appendChild(overlay);
    canvas = overlay.querySelector('canvas');
    ctx = canvas.getContext('2d');
    overlay.querySelector('.sm-sluit').addEventListener('click', sluit);
    overlay.addEventListener('pointerdown', e => { if(e.target === overlay) sluit(); });
    // vegen op een touchscreen; tikken start of herstart
    let begin = null;
    canvas.addEventListener('pointerdown', e => { e.preventDefault(); begin = { x:e.clientX, y:e.clientY }; });
    canvas.addEventListener('pointerup', e => {
      if(!begin) return;
      const dx = e.clientX - begin.x, dy = e.clientY - begin.y;
      begin = null;
      if(Math.max(Math.abs(dx), Math.abs(dy)) < 18){ startOfHerstart(); return; }
      stuur(Math.abs(dx) > Math.abs(dy) ? [Math.sign(dx), 0] : [0, Math.sign(dy)]);
    });
  }

  function open(){
    if(window.flappyMat && document.querySelector('.fm-overlay:not([hidden])')) return;   // niet over Flappy heen
    if(!overlay) bouwOverlay();
    laadGezichten();
    nieuwSpel();
    overlay.hidden = false;
    document.addEventListener('keydown', toets, true);
    vorige = performance.now(); opgespaard = 0;
    frame = requestAnimationFrame(lus);
    overlay.querySelector('.sm-sluit').focus();
  }
  function sluit(){
    overlay.hidden = true;
    document.removeEventListener('keydown', toets, true);
    if(frame) cancelAnimationFrame(frame);
    frame = null;
  }
  function toets(e){
    if(e.key === 'Escape'){ e.preventDefault(); sluit(); return; }
    const r = RICHTING[e.key] || RICHTING[e.key.toLowerCase && e.key.toLowerCase()];
    if(r){ e.preventDefault(); e.stopPropagation(); if(spel.fase !== 'vliegen') startOfHerstart(); stuur(r); return; }
    if(e.key === ' ' || e.key === 'Enter'){ e.preventDefault(); e.stopPropagation(); startOfHerstart(); }
  }
  function startOfHerstart(){
    if(spel.fase === 'start'){ spel.fase = 'vliegen'; return; }
    if(spel.fase === 'over' && performance.now() - spel.einde > 500){ nieuwSpel(); spel.fase = 'vliegen'; }
  }
  function stuur(r){
    if(spel.fase !== 'vliegen') return;
    const laatste = spel.wachtrij.length ? spel.wachtrij[spel.wachtrij.length - 1] : spel.richting;
    if(r[0] === -laatste[0] && r[1] === -laatste[1]) return;   // niet omkeren
    if(r[0] === laatste[0] && r[1] === laatste[1]) return;
    if(spel.wachtrij.length < 2) spel.wachtrij.push(r);
  }

  function lus(nu){
    const dt = Math.min(250, nu - vorige);
    vorige = nu;
    if(spel.fase === 'vliegen'){
      opgespaard += dt;
      while(opgespaard >= spel.tempo && spel.fase === 'vliegen'){ opgespaard -= spel.tempo; stap(); }
      if(spel.munt){ spel.munt.t -= dt / 1000; if(spel.munt.t <= 0) spel.munt = null; }
      spel.naamTijd = Math.max(0, spel.naamTijd - dt / 1000);
    }
    teken(nu);
    frame = requestAnimationFrame(lus);
  }

  function stap(){
    if(spel.wachtrij.length) spel.richting = spel.wachtrij.shift();
    const kop = spel.slang[0];
    const x = kop.x + spel.richting[0], y = kop.y + spel.richting[1];
    const eet = spel.eten && x === spel.eten.x && y === spel.eten.y;
    const laatste = spel.slang.length - 1;
    // de staart schuift weg, dus dat veld mag je in (behalve als je net groeit)
    const raaktZelf = spel.slang.some((d, i) => d.x === x && d.y === y && !(i === laatste && !eet));
    if(x < 0 || y < 0 || x >= N || y >= N || raaktZelf) return einde();
    spel.slang.unshift({ x, y });
    if(!eet) spel.slang.pop();
    if(eet){
      // de opgegeten collega sluit achteraan aan
      spel.ids.push(spel.eten.id);
      spel.score++; spel.verzameld++;
      spel.laatsteNaam = naamVan(spel.eten.id); spel.naamTijd = 1.2;
      spel.tempo = Math.max(MIN_TEMPO, spel.tempo - 4);
      spel.eten = null;
      spel.eten = vrijVeld(); spel.eten.id = willekeurigeCollega();
      if(!spel.munt && Math.random() < 0.18){ spel.munt = vrijVeld(); spel.munt.t = MUNT_DUUR; }
    }
    if(spel.munt && x === spel.munt.x && y === spel.munt.y){
      spel.score += MUNT_PUNTEN; spel.munten++; spel.munt = null;
      spel.laatsteNaam = '+' + MUNT_PUNTEN; spel.naamTijd = 1;
    }
  }

  function einde(){
    spel.fase = 'over';
    spel.einde = performance.now();
    if(spel.score > beste){ beste = spel.score; bewaar('snakeMatBest', beste); spel.record = true; }
    if(spel.score > 0 && window.flappyMat && flappyMat.geefCredits) flappyMat.geefCredits(spel.score);
  }

  // ---- tekenen
  function teken(nu){
    ctx.fillStyle = '#2f5fa8'; ctx.fillRect(0, 0, B, KOP);
    ctx.textAlign = 'left';
    tekst('Snake', 14, 29, 20, '#fff');
    ctx.textAlign = 'center';
    tekst('Score ' + spel.score, B / 2, 29, 17, '#fff');
    ctx.textAlign = 'right';
    tekst('Beste ' + beste, B - 48, 29, 14, 'rgba(255,255,255,.8)');
    // geblokt veld
    for(let y = 0; y < N; y++) for(let x = 0; x < N; x++){
      ctx.fillStyle = (x + y) % 2 ? '#e9eff8' : '#f3f6fb';
      ctx.fillRect(x * CEL, KOP + y * CEL, CEL, CEL);
    }
    if(spel.munt){
      const knipper = spel.munt.t < 2 && Math.floor(nu / 150) % 2;
      if(!knipper) munt(spel.munt.x, spel.munt.y);
    }
    if(spel.eten) gezicht(spel.eten.id, spel.eten.x, spel.eten.y, 1 + Math.sin(nu / 180) * 0.06, '#e3b23c');
    // lijf van achter naar voren, zodat de kop bovenop ligt
    for(let i = spel.slang.length - 1; i >= 0; i--){
      const d = spel.slang[i];
      gezicht(spel.ids[i] || spel.ids[0], d.x, d.y, i === 0 ? 1.18 : 1.0, i === 0 ? '#2f5fa8' : '#fff');
    }
    if(spel.naamTijd > 0 && spel.laatsteNaam){
      const k = spel.slang[0];
      ctx.globalAlpha = Math.min(1, spel.naamTijd * 2);
      ctx.textAlign = 'center';
      tekst(spel.laatsteNaam, k.x * CEL + CEL / 2, KOP + k.y * CEL - 8 - (1.2 - spel.naamTijd) * 14, 13, '#262b33', true);
      ctx.globalAlpha = 1;
    }
    ctx.textAlign = 'center';
    if(spel.fase === 'start'){
      paneel(B / 2, KOP + 150, 320, 170);
      tekst('Snake met collega\'s', B / 2, KOP + 102, 26, '#2f5fa8');
      tekst('Pijltjes, WASD of vegen om te sturen', B / 2, KOP + 134, 14, '#5f656e');
      tekst('Verzamel collega\'s in je staart', B / 2, KOP + 160, 14, '#5f656e');
      tekst('Gouden munt = +' + MUNT_PUNTEN + ' · elk punt = 1 credit', B / 2, KOP + 186, 13, '#b8860b');
      tekst('Druk op een pijltje of tik om te starten', B / 2, KOP + 214, 12, '#7a8089');
    }
    if(spel.fase === 'over'){
      paneel(B / 2, KOP + 160, 320, 170);
      tekst('Game over', B / 2, KOP + 112, 28, '#bf3b2c');
      tekst('Score ' + spel.score + ' · Beste ' + beste, B / 2, KOP + 144, 16, '#262b33');
      tekst(spel.verzameld + ' collega\'s verzameld' + (spel.munten ? ' · ' + spel.munten + ' munt' + (spel.munten > 1 ? 'en' : '') : ''), B / 2, KOP + 168, 13, '#5f656e');
      tekst((spel.record ? 'Nieuw record! ' : '') + '+' + spel.score + ' credits voor Flappy Mat', B / 2, KOP + 194, 14, spel.record ? '#2f8a4e' : '#2f5fa8');
      tekst('Tik of spatie: opnieuw · Esc: sluiten', B / 2, KOP + 222, 12, '#7a8089');
    }
  }
  function gezicht(id, x, y, schaal, rand){
    const cx = x * CEL + CEL / 2, cy = KOP + y * CEL + CEL / 2, r = CEL / 2 * schaal;
    const img = BEELD[id];
    ctx.save();
    ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.closePath();
    if(img && img.naturalWidth){
      ctx.save(); ctx.clip();
      // gezicht vullend in de cirkel, uitgesneden op het midden-boven (daar zit het gezicht)
      const vh = img.naturalHeight, vb = img.naturalWidth, zijde = Math.min(vb, vh);
      ctx.drawImage(img, (vb - zijde) / 2, Math.max(0, (vh - zijde) * 0.3), zijde, zijde, cx - r, cy - r, r * 2, r * 2);
      ctx.restore();
    } else { ctx.fillStyle = '#f2c9a0'; ctx.fill(); }
    ctx.lineWidth = 2; ctx.strokeStyle = rand; ctx.stroke();
    ctx.restore();
  }
  function munt(x, y){
    const cx = x * CEL + CEL / 2, cy = KOP + y * CEL + CEL / 2;
    ctx.beginPath(); ctx.arc(cx, cy, CEL / 2 - 2, 0, Math.PI * 2);
    ctx.fillStyle = '#e3b23c'; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = '#b8860b'; ctx.stroke();
    ctx.font = "700 13px 'IBM Plex Sans', system-ui, sans-serif"; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillStyle = '#7a5a00'; ctx.fillText('P', cx, cy + 1); ctx.textBaseline = 'alphabetic';
  }
  function paneel(cx, cy, w, h){
    ctx.fillStyle = 'rgba(255,255,255,.94)';
    const x = cx - w / 2, y = cy - h / 2, r = 12;
    ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath(); ctx.fill();
    ctx.strokeStyle = 'rgba(0,0,0,.08)'; ctx.lineWidth = 1; ctx.stroke();
  }
  function tekst(t, x, y, grootte, kleur, rand){
    ctx.font = `600 ${grootte}px 'IBM Plex Sans', system-ui, sans-serif`;
    if(rand){ ctx.lineWidth = 4; ctx.strokeStyle = 'rgba(255,255,255,.9)'; ctx.strokeText(t, x, y); }
    ctx.fillStyle = kleur; ctx.fillText(t, x, y);
  }

  // ---- openen: Konami-code of "snake" typen; op een telefoon het logo ingedrukt houden
  function inInvoer(t){ return t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName)); }
  let konamiPos = 0, getypt = '';
  document.addEventListener('keydown', e => {
    if(overlay && !overlay.hidden) return;
    if(inInvoer(e.target)) return;
    const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
    konamiPos = k === KONAMI[konamiPos] ? konamiPos + 1 : (k === KONAMI[0] ? 1 : 0);
    if(konamiPos === KONAMI.length){ konamiPos = 0; open(); return; }
    if(k.length === 1){ getypt = (getypt + k).slice(-5); if(getypt === 'snake'){ getypt = ''; open(); } }
  });
  function koppel(el){
    if(!el) return;
    let timer = null, start = null;
    el.addEventListener('pointerdown', e => {
      start = { x:e.clientX, y:e.clientY };
      timer = setTimeout(() => { timer = null; open(); }, 700);
    });
    const stop = () => { if(timer){ clearTimeout(timer); timer = null; } };
    el.addEventListener('pointerup', stop);
    el.addEventListener('pointerleave', stop);
    el.addEventListener('pointermove', e => { if(start && Math.hypot(e.clientX - start.x, e.clientY - start.y) > 10) stop(); });
    el.addEventListener('contextmenu', e => { if(e.pointerType !== 'mouse') e.preventDefault(); });
  }

  window.snakeMat = { koppel, open };
})();
