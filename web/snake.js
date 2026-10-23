/* Tweede easter egg: Snake met de collega's. Openen met de Konami-code
   (↑ ↑ ↓ ↓ ← → ← → B A), door ergens "snake" te typen, of op een telefoon door
   het Profource-logo even ingedrukt te houden. Koppelen met snakeMat.koppel(el).
   Je slang begint met het personage dat je in Flappy Mat hebt gekozen en
   verzamelt collega's in zijn staart; gouden P-munten geven extra punten. Elk
   punt is een credit in dezelfde pot als Flappy Mat (via flappyMat.geefCredits).
   Beste score blijft per browser bewaard; het geluid volgt de knop van Flappy Mat. */
(function(){
  const N = 16, CEL = 25, KOP = 52;          // 16×16 velden van 25 px, plus een balk bovenin
  const B = N * CEL, H = N * CEL + KOP;
  const START_TEMPO = 140, MIN_TEMPO = 68, VERSNELLING = 3.5;   // ms per stap
  const MUNT_PUNTEN = 5, MUNT_DUUR = 7;       // seconden
  const AFTELLEN = 1.5;                       // 3-2-1 voor de start
  const BLAUW = '#2f5fa8', BLAUW_LICHT = '#4a78c2', GOUD = '#e3b23c', ROOD = '#bf3b2c';
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

  let overlay, canvas, ctx, dpr = 1, frame = null, vorige = 0, spel;
  let deeltjes = [], teksten = [];
  let beste = lees('snakeMatBest', 0);
  function lees(k, d){ try{ const v = localStorage.getItem(k); return v == null ? d : JSON.parse(v); }catch(e){ return d; } }
  function bewaar(k, v){ try{ localStorage.setItem(k, JSON.stringify(v)); }catch(e){} }

  // ---- geluid: zelfde instelling als Flappy Mat (standaard uit)
  let audio = null;
  function piep(freq, duur, type, vol, glijTot){
    if(!lees('flappyMatGeluid', false)) return;
    try{
      audio = audio || new (window.AudioContext || window.webkitAudioContext)();
      const o = audio.createOscillator(), g = audio.createGain(), t = audio.currentTime;
      o.type = type || 'square'; o.frequency.setValueAtTime(freq, t);
      if(glijTot) o.frequency.exponentialRampToValueAtTime(glijTot, t + duur);
      g.gain.setValueAtTime(vol || 0.05, t); g.gain.exponentialRampToValueAtTime(0.0001, t + duur);
      o.connect(g); g.connect(audio.destination); o.start(t); o.stop(t + duur);
    }catch(e){}
  }
  const GELUID = {
    eet:   () => { piep(660, 0.06, 'square', 0.035); setTimeout(() => piep(990, 0.08, 'square', 0.035), 55); },
    munt:  () => { piep(990, 0.07, 'square', 0.04); setTimeout(() => piep(1480, 0.14, 'triangle', 0.045), 70); },
    tel:   () => piep(520, 0.09, 'triangle', 0.05),
    start: () => piep(880, 0.16, 'triangle', 0.05),
    dood:  () => piep(320, 0.5, 'sawtooth', 0.06, 50),
  };

  function nieuwSpel(){
    const kop = eigenKeuze(), m = Math.floor(N / 2);
    // slang = posities (kop eerst), ids = het gezicht per segment in dezelfde volgorde
    const slang = [{ x:m, y:m }, { x:m - 1, y:m }, { x:m - 2, y:m }];
    spel = { fase:'start', slang, vorigeSlang:slang.map(d => ({ ...d })), ids:[kop, kop, kop],
             richting:[1, 0], wachtrij:[], score:0, verzameld:0, munten:0, tempo:START_TEMPO, opgespaard:0,
             eten:null, munt:null, schud:0, flits:0, aftellen:0, tong:0, tongWacht:1.5, record:false };
    deeltjes = []; teksten = [];
    nieuwEten();
  }
  function nieuwEten(){
    spel.eten = vrijVeld();
    spel.eten.id = willekeurigeCollega();
    spel.eten.geboren = performance.now();
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
      .sm-overlay{ position:fixed; inset:0; z-index:1000; background:rgba(16,22,34,.78); display:flex; align-items:center; justify-content:center; overflow-y:auto; }
      .sm-overlay[hidden]{ display:none; }
      .sm-veld{ position:relative; margin:auto; padding:10px 0; display:flex; flex-direction:column; align-items:center; gap:8px; }
      .sm-veld canvas{ display:block; width:min(420px, 94vw, calc((88vh - 40px) * ${B} / ${H})); height:auto; aspect-ratio:${B}/${H}; border-radius:16px;
        box-shadow:0 24px 70px rgba(0,0,0,.5), 0 0 0 1px rgba(255,255,255,.06); touch-action:none; cursor:pointer; user-select:none; -webkit-user-select:none; outline:none; }
      .sm-sluit{ position:absolute; top:20px; right:10px; width:32px; height:32px; border:0; border-radius:50%;
        background:rgba(255,255,255,.18); color:#fff; font:600 20px/1 'IBM Plex Sans',system-ui,sans-serif; cursor:pointer; }
      .sm-sluit:hover{ background:rgba(255,255,255,.3); }
      .sm-onder{ display:flex; gap:8px; align-items:center; font:500 12px/1 'IBM Plex Sans',system-ui,sans-serif; color:rgba(255,255,255,.7); }
      .sm-onder button{ font:inherit; font-weight:600; color:#fff; background:rgba(255,255,255,.14); border:0; border-radius:14px; padding:7px 12px; cursor:pointer; }
      @media (hover:none){ .sm-onder span{ display:none; } }
      .sm-onder button:hover{ background:rgba(255,255,255,.24); }
      .sm-sluit:focus-visible, .sm-onder button:focus-visible{ outline:2px solid #8fb3ec; outline-offset:2px; }`;
    document.head.appendChild(stijl);
    overlay = document.createElement('div');
    overlay.className = 'sm-overlay';
    overlay.hidden = true;
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-label', 'Snake met collega\'s');
    overlay.innerHTML = '<div class="sm-veld"><canvas tabindex="-1" aria-label="Snake speelveld"></canvas><button class="sm-sluit" aria-label="Sluiten">×</button>'
      + '<div class="sm-onder"><button class="sm-geluid" aria-pressed="false"></button><button class="sm-pauze">Pauze</button><span>Esc sluit</span></div></div>';
    document.body.appendChild(overlay);
    canvas = overlay.querySelector('canvas');
    ctx = canvas.getContext('2d');
    overlay.querySelector('.sm-sluit').addEventListener('click', sluit);
    overlay.addEventListener('pointerdown', e => { if(e.target === overlay) sluit(); });
    const knopGeluid = overlay.querySelector('.sm-geluid');
    const zetGeluid = () => { const aan = lees('flappyMatGeluid', false); knopGeluid.textContent = aan ? '♪ Geluid aan' : '♪ Geluid uit'; knopGeluid.setAttribute('aria-pressed', String(aan)); };
    zetGeluid();
    knopGeluid.addEventListener('click', () => { bewaar('flappyMatGeluid', !lees('flappyMatGeluid', false)); zetGeluid(); GELUID.eet(); knopGeluid.blur(); });
    overlay.querySelector('.sm-pauze').addEventListener('click', e => { pauzeer(); e.currentTarget.blur(); });
    // vegen op een touchscreen (al tijdens het vegen, voor een snelle reactie); tikken start of herstart
    let begin = null, geveegd = false;
    canvas.addEventListener('pointerdown', e => { e.preventDefault(); begin = { x:e.clientX, y:e.clientY }; geveegd = false; });
    canvas.addEventListener('pointermove', e => {
      if(!begin) return;
      const dx = e.clientX - begin.x, dy = e.clientY - begin.y;
      if(Math.max(Math.abs(dx), Math.abs(dy)) < 22) return;
      if(spel.fase === 'start') startOfHerstart();
      stuur(Math.abs(dx) > Math.abs(dy) ? [Math.sign(dx), 0] : [0, Math.sign(dy)]);
      begin = { x:e.clientX, y:e.clientY }; geveegd = true;
    });
    const los = () => { if(begin && !geveegd) startOfHerstart(); begin = null; };
    canvas.addEventListener('pointerup', los);
    canvas.addEventListener('pointercancel', () => { begin = null; });
    document.addEventListener('visibilitychange', () => { if(document.hidden && spel && spel.fase === 'vliegen') pauzeer(); });
  }

  function open(){
    if(document.querySelector('.fm-overlay:not([hidden])')) return;   // niet over Flappy heen
    if(!overlay) bouwOverlay();
    dpr = Math.min(2, window.devicePixelRatio || 1);                  // scherp op retina en telefoons
    canvas.width = Math.round(B * dpr); canvas.height = Math.round(H * dpr);
    laadGezichten();
    nieuwSpel();
    overlay.hidden = false;
    document.addEventListener('keydown', toets, true);
    vorige = performance.now();
    frame = requestAnimationFrame(lus);
    canvas.focus({ preventScroll:true });
  }
  function sluit(){
    overlay.hidden = true;
    document.removeEventListener('keydown', toets, true);
    if(frame) cancelAnimationFrame(frame);
    frame = null;
  }
  function toets(e){
    if(e.key === 'Escape'){ e.preventDefault(); sluit(); return; }
    if(e.target && e.target.closest && e.target.closest('.sm-onder')) return;
    const r = RICHTING[e.key] || RICHTING[e.key.length === 1 ? e.key.toLowerCase() : ''];
    if(r){
      e.preventDefault(); e.stopPropagation();
      if(spel.fase === 'start' || spel.fase === 'over' || spel.fase === 'pauze') startOfHerstart();
      stuur(r); return;
    }
    if(e.key === ' ' || e.key === 'Enter'){ e.preventDefault(); e.stopPropagation(); spel.fase === 'vliegen' ? pauzeer() : startOfHerstart(); }
    if(e.key === 'p' || e.key === 'P'){ e.preventDefault(); pauzeer(); }
  }
  function startOfHerstart(){
    if(spel.fase === 'start'){ spel.fase = 'aftellen'; spel.aftellen = AFTELLEN; GELUID.tel(); return; }
    if(spel.fase === 'pauze'){ spel.fase = 'vliegen'; return; }
    if(spel.fase === 'over' && performance.now() - spel.einde > 600){ nieuwSpel(); spel.fase = 'aftellen'; spel.aftellen = AFTELLEN; GELUID.tel(); }
  }
  function pauzeer(){
    if(spel.fase === 'vliegen') spel.fase = 'pauze';
    else if(spel.fase === 'pauze') spel.fase = 'vliegen';
  }
  function stuur(r){
    if(spel.fase !== 'vliegen' && spel.fase !== 'aftellen') return;
    const laatste = spel.wachtrij.length ? spel.wachtrij[spel.wachtrij.length - 1] : spel.richting;
    if(r[0] === -laatste[0] && r[1] === -laatste[1]) return;   // niet omkeren
    if(r[0] === laatste[0] && r[1] === laatste[1]) return;
    if(spel.wachtrij.length < 2) spel.wachtrij.push(r);
  }

  function lus(nu){
    frame = requestAnimationFrame(lus);   // eerst plannen: een tekenfout mag het spel niet laten bevriezen
    const dt = Math.min(0.05, (nu - vorige) / 1000);
    vorige = nu;
    if(spel.fase === 'aftellen'){
      const voor = Math.ceil(spel.aftellen / (AFTELLEN / 3));
      spel.aftellen -= dt;
      const na = Math.ceil(spel.aftellen / (AFTELLEN / 3));
      if(spel.aftellen <= 0){ spel.fase = 'vliegen'; spel.opgespaard = 0; GELUID.start(); }
      else if(na !== voor) GELUID.tel();
    }
    if(spel.fase === 'vliegen'){
      spel.opgespaard += dt * 1000;
      while(spel.opgespaard >= spel.tempo && spel.fase === 'vliegen'){ spel.opgespaard -= spel.tempo; stap(); }
      if(spel.munt){ spel.munt.t -= dt; if(spel.munt.t <= 0) spel.munt = null; }
      spel.tongWacht -= dt;
      if(spel.tongWacht <= 0){ spel.tong = 0.22; spel.tongWacht = 1.4 + Math.random() * 1.6; }
      spel.tong = Math.max(0, spel.tong - dt);
    }
    spel.schud = Math.max(0, spel.schud - dt);
    spel.flits = Math.max(0, spel.flits - dt);
    deeltjes.forEach(d => { d.x += d.vx * dt; d.y += d.vy * dt; d.vy += 260 * dt; d.leven -= dt; });
    deeltjes = deeltjes.filter(d => d.leven > 0);
    teksten.forEach(t => { t.y -= 34 * dt; t.leven -= dt; });
    teksten = teksten.filter(t => t.leven > 0);
    teken(nu);
  }

  function stap(){
    if(spel.wachtrij.length) spel.richting = spel.wachtrij.shift();
    spel.vorigeSlang = spel.slang.map(d => ({ ...d }));
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
      spat(x, y, [GOUD, '#fff', BLAUW_LICHT], 14);
      zweef(naamVan(spel.eten.id) || '+1', x, y, '#262b33');
      GELUID.eet();
      spel.tempo = Math.max(MIN_TEMPO, spel.tempo - VERSNELLING);
      nieuwEten();
      if(!spel.munt && Math.random() < 0.18){ spel.munt = vrijVeld(); spel.munt.t = MUNT_DUUR; }
    }
    if(spel.munt && x === spel.munt.x && y === spel.munt.y){
      spel.score += MUNT_PUNTEN; spel.munten++; spel.munt = null;
      spat(x, y, [GOUD, '#fff3c4', '#b8860b'], 20);
      zweef('+' + MUNT_PUNTEN, x, y, '#b8860b');
      GELUID.munt();
    }
  }

  function einde(){
    spel.fase = 'over';
    spel.einde = performance.now();
    spel.vorigeSlang = spel.slang.map(d => ({ ...d }));
    spel.schud = 0.4; spel.flits = 0.3;
    const k = spel.slang[0];
    spat(k.x, k.y, [ROOD, '#fff', BLAUW], 24);
    GELUID.dood();
    if(spel.score > beste){ beste = spel.score; bewaar('snakeMatBest', beste); spel.record = true; }
    if(spel.score > 0 && window.flappyMat && flappyMat.geefCredits) flappyMat.geefCredits(spel.score);
  }

  function midden(x, y){ return [x * CEL + CEL / 2, KOP + y * CEL + CEL / 2]; }
  function spat(x, y, kleuren, aantal){
    const [cx, cy] = midden(x, y);
    for(let i = 0; i < aantal; i++){
      const hoek = Math.random() * Math.PI * 2, snel = 60 + Math.random() * 140;
      deeltjes.push({ x:cx, y:cy, vx:Math.cos(hoek) * snel, vy:Math.sin(hoek) * snel - 60,
                      r:1.5 + Math.random() * 2.5, kleur:kleuren[i % kleuren.length], leven:0.5 + Math.random() * 0.4 });
    }
  }
  function zweef(tekstje, x, y, kleur){
    const [cx, cy] = midden(x, y);
    teksten.push({ tekst:tekstje, x:cx, y:cy - 16, kleur, leven:0.9 });
  }

  // ---- tekenen
  function teken(nu){
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, B, H);
    ctx.save();
    if(spel.schud > 0){ const s = spel.schud / 0.4 * 6; ctx.translate((Math.random() - 0.5) * s, (Math.random() - 0.5) * s); }
    tekenBalk();
    tekenVeld();
    const t = spel.fase === 'vliegen' ? Math.min(1, spel.opgespaard / spel.tempo) : 1;
    if(spel.munt) tekenMunt(nu);
    if(spel.eten) tekenEten(nu);
    tekenSlang(t);
    deeltjes.forEach(d => {
      ctx.globalAlpha = Math.max(0, Math.min(1, d.leven * 2));
      ctx.fillStyle = d.kleur; ctx.beginPath(); ctx.arc(d.x, d.y, d.r, 0, Math.PI * 2); ctx.fill();
    });
    ctx.globalAlpha = 1;
    ctx.textAlign = 'center';
    teksten.forEach(tt => {
      ctx.globalAlpha = Math.min(1, tt.leven * 2);
      tekst(tt.tekst, tt.x, tt.y, 13, tt.kleur, true);
    });
    ctx.globalAlpha = 1;
    if(spel.flits > 0){ ctx.fillStyle = `rgba(191,59,44,${spel.flits})`; ctx.fillRect(0, KOP, B, H - KOP); }
    ctx.restore();
    tekenSchermen(nu);
  }

  function tekenBalk(){
    const g = ctx.createLinearGradient(0, 0, B, KOP);
    g.addColorStop(0, '#2a5398'); g.addColorStop(1, '#3d6fc0');
    ctx.fillStyle = g; ctx.fillRect(0, 0, B, KOP);
    ctx.textAlign = 'left';
    tekst('Snake', 16, 33, 19, '#fff');
    ctx.font = "500 11px 'IBM Plex Sans', system-ui, sans-serif"; ctx.fillStyle = 'rgba(255,255,255,.65)';
    ctx.fillText('met collega\'s', 76, 33);
    // score in een pil in het midden
    const sTekst = String(spel.score);
    ctx.font = "700 20px 'IBM Plex Sans', system-ui, sans-serif";
    const w = Math.max(54, ctx.measureText(sTekst).width + 28);
    ctx.fillStyle = 'rgba(255,255,255,.16)'; pil(B / 2 + 40 - w / 2, 12, w, 28, 14); ctx.fill();
    ctx.textAlign = 'center'; tekst(sTekst, B / 2 + 40, 33, 20, '#fff');
    ctx.textAlign = 'right';
    tekst('🏆 ' + beste, B - 52, 33, 13, 'rgba(255,255,255,.85)');
  }

  function tekenVeld(){
    for(let y = 0; y < N; y++) for(let x = 0; x < N; x++){
      ctx.fillStyle = (x + y) % 2 ? '#e8eef7' : '#f1f5fb';
      ctx.fillRect(x * CEL, KOP + y * CEL, CEL, CEL);
    }
    // zachte schaduw onder de balk
    const g = ctx.createLinearGradient(0, KOP, 0, KOP + 14);
    g.addColorStop(0, 'rgba(20,40,80,.16)'); g.addColorStop(1, 'rgba(20,40,80,0)');
    ctx.fillStyle = g; ctx.fillRect(0, KOP, B, 14);
  }

  function punten(t){
    const v = spel.vorigeSlang, s = spel.slang;
    return s.map((d, i) => {
      const a = v[i] || v[v.length - 1];
      return midden(a.x + (d.x - a.x) * t, a.y + (d.y - a.y) * t);
    });
  }

  function tekenSlang(t){
    const pts = punten(t);
    const dood = spel.fase === 'over';
    // doorlopend lijf onder de gezichten
    ctx.save();
    ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.shadowColor = 'rgba(20,40,80,.25)'; ctx.shadowBlur = 8; ctx.shadowOffsetY = 3;
    ctx.strokeStyle = dood ? '#7d8796' : BLAUW; ctx.lineWidth = CEL * 0.8;
    ctx.beginPath(); pts.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)); ctx.stroke();
    ctx.shadowColor = 'transparent';
    ctx.strokeStyle = dood ? '#9aa3b0' : BLAUW_LICHT; ctx.lineWidth = CEL * 0.42;
    ctx.beginPath(); pts.forEach(([x, y], i) => i ? ctx.lineTo(x, y) : ctx.moveTo(x, y)); ctx.stroke();
    ctx.restore();
    // gezichten van achter naar voren, zodat de kop bovenop ligt
    for(let i = pts.length - 1; i >= 1; i--){
      gezicht(spel.ids[i] || spel.ids[0], pts[i][0], pts[i][1], CEL * 0.4, '#fff', 1.5, dood);
    }
    const [kx, ky] = pts[0];
    if(spel.tong > 0 && !dood){
      const [rx, ry] = spel.richting, r0 = CEL * 0.62, r1 = r0 + 9;
      ctx.strokeStyle = '#d6455d'; ctx.lineWidth = 2; ctx.lineCap = 'round';
      ctx.beginPath(); ctx.moveTo(kx + rx * r0, ky + ry * r0); ctx.lineTo(kx + rx * r1, ky + ry * r1);
      ctx.lineTo(kx + rx * (r1 + 4) - ry * 3, ky + ry * (r1 + 4) + rx * 3);
      ctx.moveTo(kx + rx * r1, ky + ry * r1); ctx.lineTo(kx + rx * (r1 + 4) + ry * 3, ky + ry * (r1 + 4) - rx * 3);
      ctx.stroke();
    }
    ctx.save();
    ctx.shadowColor = 'rgba(20,40,80,.35)'; ctx.shadowBlur = 10; ctx.shadowOffsetY = 3;
    ctx.beginPath(); ctx.arc(kx, ky, CEL * 0.62 + 2, 0, Math.PI * 2); ctx.fillStyle = dood ? '#7d8796' : BLAUW; ctx.fill();
    ctx.restore();
    gezicht(spel.ids[0], kx, ky, CEL * 0.62, '#fff', 2.5, dood);
  }

  function tekenEten(nu){
    const e = spel.eten, [cx, cy] = midden(e.x, e.y);
    const p = Math.min(1, (nu - e.geboren) / 320);
    const pop = p < 1 ? Math.max(0.05, 1 + 2.70158 * Math.pow(p - 1, 3) + 1.70158 * Math.pow(p - 1, 2)) : 1;   // ease-out-back
    const puls = 1 + Math.sin(nu / 200) * 0.05;
    const r = CEL * 0.48 * pop * puls;
    const gloed = ctx.createRadialGradient(cx, cy, r * 0.6, cx, cy, r * 2);
    gloed.addColorStop(0, 'rgba(227,178,60,.45)'); gloed.addColorStop(1, 'rgba(227,178,60,0)');
    ctx.fillStyle = gloed; ctx.beginPath(); ctx.arc(cx, cy, r * 2, 0, Math.PI * 2); ctx.fill();
    gezicht(e.id, cx, cy, r, GOUD, 2.5, false);
  }

  function tekenMunt(nu){
    const m = spel.munt;
    if(m.t < 2 && Math.floor(nu / 140) % 2) return;   // knippert vlak voor hij verdwijnt
    const [cx, cy] = midden(m.x, m.y);
    const draai = Math.abs(Math.cos(nu / 260)) * 0.75 + 0.25, r = CEL / 2 - 2;
    ctx.save();
    ctx.translate(cx, cy); ctx.scale(draai, 1);
    ctx.beginPath(); ctx.arc(0, 0, r, 0, Math.PI * 2);
    const g = ctx.createLinearGradient(-r, -r, r, r);
    g.addColorStop(0, '#f6d77a'); g.addColorStop(1, '#c9951e');
    ctx.fillStyle = g; ctx.fill(); ctx.lineWidth = 2; ctx.strokeStyle = '#a87a12'; ctx.stroke();
    ctx.font = "700 13px 'IBM Plex Sans', system-ui, sans-serif"; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
    ctx.fillStyle = '#7a5a00'; ctx.fillText('P', 0, 1); ctx.textBaseline = 'alphabetic';
    ctx.restore();
  }

  function tekenSchermen(nu){
    if(spel.fase === 'vliegen') return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.textAlign = 'center';
    if(spel.fase === 'aftellen'){
      const deel = AFTELLEN / 3, n = Math.ceil(spel.aftellen / deel), frac = (spel.aftellen % deel) / deel;
      ctx.fillStyle = 'rgba(20,32,56,.18)'; ctx.fillRect(0, KOP, B, H - KOP);
      ctx.globalAlpha = Math.min(1, frac * 2.5);
      tekst(String(n), B / 2, KOP + (H - KOP) / 2 + 24, 64 + (1 - frac) * 26, '#fff', false, true);
      ctx.globalAlpha = 1;
      return;
    }
    ctx.fillStyle = 'rgba(20,32,56,.42)'; ctx.fillRect(0, KOP, B, H - KOP);
    const cy = KOP + (H - KOP) / 2;
    if(spel.fase === 'start'){
      kaart(B / 2, cy, 320, 272);
      ringGezicht(spel.ids[0], B / 2, cy - 90, 28);
      tekst('Snake met collega\'s', B / 2, cy - 34, 24, BLAUW);
      tekst('Verzamel collega\'s in je staart', B / 2, cy - 10, 14, '#5f656e');
      toetsjes(B / 2, cy + 30);
      tekst('of vegen op je telefoon', B / 2, cy + 84, 12, '#7a8089');
      ctx.globalAlpha = 0.55 + Math.sin(nu / 300) * 0.45;
      tekst('Druk op een pijltje of tik om te starten', B / 2, cy + 112, 13, BLAUW);
      ctx.globalAlpha = 1;
    }
    if(spel.fase === 'pauze'){
      kaart(B / 2, cy, 240, 110);
      tekst('Pauze', B / 2, cy - 6, 26, BLAUW);
      tekst('Spatie of tik om verder te gaan', B / 2, cy + 24, 13, '#5f656e');
    }
    if(spel.fase === 'over'){
      const verzameld = spel.ids.slice(3);
      const hoog = verzameld.length ? 240 : 204;
      kaart(B / 2, cy, 330, hoog);
      const top = cy - hoog / 2;
      tekst('Game over', B / 2, top + 40, 24, ROOD);
      tekst(String(spel.score), B / 2, top + 92, 46, '#262b33');
      tekst(spel.record ? 'Nieuw record!' : 'Beste: ' + beste, B / 2, top + 116, 13, spel.record ? '#2f8a4e' : '#7a8089');
      let y = top + 150;
      if(verzameld.length){
        const max = 9, toon = verzameld.slice(-max), r = 12, stapX = 28;
        const breed = (toon.length - 1) * stapX + (verzameld.length > max ? stapX : 0);
        let x = B / 2 - breed / 2;
        toon.forEach(id => { gezicht(id, x, y, r, '#fff', 2, false); x += stapX; });
        if(verzameld.length > max){ ctx.textAlign = 'left'; tekst('+' + (verzameld.length - max), x - 10, y + 5, 12, '#5f656e'); ctx.textAlign = 'center'; }
        y += 36;
      }
      const deel = [spel.verzameld + (spel.verzameld === 1 ? ' collega' : ' collega\'s')];
      if(spel.munten) deel.push(spel.munten + (spel.munten === 1 ? ' munt' : ' munten'));
      tekst(deel.join(' · ') + ' · +' + spel.score + ' credits', B / 2, y, 13, BLAUW);
      ctx.globalAlpha = 0.55 + Math.sin(nu / 300) * 0.45;
      tekst('Tik of spatie: opnieuw', B / 2, y + 28, 12, '#7a8089');
      ctx.globalAlpha = 1;
    }
  }

  function gezicht(id, cx, cy, r, rand, dikte, grijs){
    const img = BEELD[id];
    ctx.save();
    ctx.beginPath(); ctx.arc(cx, cy, r, 0, Math.PI * 2); ctx.closePath();
    if(img && img.naturalWidth){
      ctx.save(); ctx.clip();
      if(grijs) ctx.filter = 'grayscale(1) brightness(.9)';
      // vierkant uitsnijden op het midden-boven (daar zit het gezicht)
      const vh = img.naturalHeight, vb = img.naturalWidth, zijde = Math.min(vb, vh);
      ctx.drawImage(img, (vb - zijde) / 2, Math.max(0, (vh - zijde) * 0.3), zijde, zijde, cx - r, cy - r, r * 2, r * 2);
      ctx.restore();
    } else { ctx.fillStyle = '#f2c9a0'; ctx.fill(); }
    ctx.lineWidth = dikte; ctx.strokeStyle = rand; ctx.stroke();
    ctx.restore();
  }
  function ringGezicht(id, cx, cy, r){
    ctx.beginPath(); ctx.arc(cx, cy, r + 4, 0, Math.PI * 2); ctx.fillStyle = BLAUW; ctx.fill();
    gezicht(id, cx, cy, r, '#fff', 2.5, false);
  }
  function toetsjes(cx, cy){
    const k = 26, gap = 4;
    const toets = (x, y, label) => {
      ctx.fillStyle = '#eef2f8'; pil(x - k / 2, y - k / 2, k, k, 6); ctx.fill();
      ctx.strokeStyle = '#c9d2df'; ctx.lineWidth = 1; ctx.stroke();
      ctx.fillStyle = '#c9d2df'; ctx.fillRect(x - k / 2 + 3, y + k / 2 - 2, k - 6, 2);
      ctx.textAlign = 'center'; tekst(label, x, y + 5, 13, '#3c4450');
    };
    toets(cx, cy - k / 2 - gap / 2 - 2, '↑');
    toets(cx - k - gap, cy + k / 2 + gap / 2 - 2, '←');
    toets(cx, cy + k / 2 + gap / 2 - 2, '↓');
    toets(cx + k + gap, cy + k / 2 + gap / 2 - 2, '→');
  }
  function kaart(cx, cy, w, h){
    ctx.save();
    ctx.shadowColor = 'rgba(10,20,40,.35)'; ctx.shadowBlur = 24; ctx.shadowOffsetY = 8;
    ctx.fillStyle = '#fff'; pil(cx - w / 2, cy - h / 2, w, h, 16); ctx.fill();
    ctx.restore();
  }
  function pil(x, y, w, h, r){
    ctx.beginPath(); ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
  }
  function tekst(t, x, y, grootte, kleur, rand, schaduw){
    ctx.font = `700 ${grootte}px 'IBM Plex Sans', system-ui, sans-serif`;
    if(schaduw){ ctx.save(); ctx.shadowColor = 'rgba(10,20,40,.45)'; ctx.shadowBlur = 12; ctx.fillStyle = kleur; ctx.fillText(t, x, y); ctx.restore(); return; }
    if(rand){ ctx.lineWidth = 4; ctx.strokeStyle = 'rgba(255,255,255,.92)'; ctx.strokeText(t, x, y); }
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
    el.style.webkitUserSelect = 'none'; el.style.userSelect = 'none'; el.style.webkitTouchCallout = 'none';
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
