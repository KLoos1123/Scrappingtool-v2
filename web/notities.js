/* Notities per opdracht (geschikt voor, tarief, opmerking) en gescrapete
   tarieven, gedeeld door het dashboard (index.html) en de bronnenpagina
   (bronnen.html). Laden na auth.js. Tabellen: supabase/notities_tarieven.sql.

   Gebruik:
     await laadNotitiesEnTarieven();          // vult NOTITIES en TARIEVEN
     notitieHtml(bron, tenderId)              // formulier voor in een detailrij
     koppelNotities(container, naOpslaan)     // één keer, via event delegation
     volgNotities(naWijziging)                // live updates van collega's
*/
let NOTITIES = new Map();   // "bron|tender_id" -> {geschikt_voor, tarief, opmerking, gewijzigd_door, gewijzigd_op}
let TARIEVEN = new Map();   // "bron|tender_id" -> {tarief, tarief_min, tarief_max, herkomst}
let NOTITIES_ACTIEF = true; // false zolang de tabel 'notities' nog niet bestaat

function notitieSleutel(bron, tid){ return `${bron}|${tid}`; }
function notitieEsc(s){ return String(s??'').replace(/[&<>"']/g,c=>({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }

async function haalTabel(tabel, select){
  const PAGINA=1000;
  let uit=[], from=0;
  for(;;){
    const {data, error}=await supabase.from(tabel).select(select)
      .order('bron',{ascending:true}).order('tender_id',{ascending:true}).range(from, from+PAGINA-1);
    if(error) throw error;
    uit=uit.concat(data||[]);
    if(!data || data.length<PAGINA) return uit;
    from+=PAGINA;
  }
}

async function laadNotitiesEnTarieven(){
  const [notities, tarieven]=await Promise.all([
    haalTabel('notities','bron, tender_id, geschikt_voor, tarief, opmerking, gewijzigd_door, gewijzigd_op')
      .catch(err=>{ console.warn('notities niet beschikbaar:', err.message||err); NOTITIES_ACTIEF=false; return []; }),
    haalTabel('tarieven','bron, tender_id, tarief, tarief_min, tarief_max, herkomst')
      .catch(err=>{ console.warn('tarieven niet beschikbaar:', err.message||err); return []; }),
  ]);
  NOTITIES=new Map(notities.map(n=>[notitieSleutel(n.bron, n.tender_id), n]));
  TARIEVEN=new Map(tarieven.map(t=>[notitieSleutel(t.bron, t.tender_id), t]));
}

function heeftNotitie(bron, tid){
  const n=NOTITIES.get(notitieSleutel(bron, tid));
  return !!(n && (n.geschikt_voor || n.tarief || n.opmerking));
}
// Klein icoon voor in de titelcel, met de notitie als tooltip.
function notitieIcoon(bron, tid){
  if(!heeftNotitie(bron, tid)) return '';
  const n=NOTITIES.get(notitieSleutel(bron, tid));
  const tip=[n.geschikt_voor&&`Geschikt voor: ${n.geschikt_voor}`, n.tarief&&`Tarief: ${n.tarief}`, n.opmerking]
    .filter(Boolean).join('\n');
  return `<span class="notitie-icoon" title="${notitieEsc(tip)}">💬</span>`;
}
// Een tarief uit de notitie (zelf ingevuld) gaat voor het gescrapete tarief.
function tariefInhoud(bron, tid){
  const n=NOTITIES.get(notitieSleutel(bron, tid));
  if(n && n.tarief){
    const t=TARIEVEN.get(notitieSleutel(bron, tid));
    const tip='Tarief uit de notitie'+(n.gewijzigd_door?` van ${n.gewijzigd_door}`:'')+(t?` (gescrapet: ${t.tarief})`:'');
    return `<span class="tarief tarief-notitie" title="${notitieEsc(tip)}">${notitieEsc(n.tarief)}</span>`;
  }
  const t=TARIEVEN.get(notitieSleutel(bron, tid));
  if(!t) return '<span class="muted">—</span>';
  const titel={ai:'uit de AI-verrijking van de omschrijving', bron:'zoals de bron het opgeeft'}[t.herkomst] || 'uit de omschrijving';
  return `<span class="tarief" title="Tarief ${titel}">${notitieEsc(t.tarief)}</span>`;
}
function tariefCel(bron, tid){
  return `<span class="tariefcel" data-sleutel="${notitieEsc(notitieSleutel(bron, tid))}">${tariefInhoud(bron, tid)}</span>`;
}
// Werk de tariefkolom bij van alle regels van deze opdracht (na opslaan of een live wijziging).
function werkTariefCellenBij(bron, tid){
  const sleutel=notitieSleutel(bron, tid);
  document.querySelectorAll('.tariefcel').forEach(el=>{
    if(el.dataset.sleutel===sleutel) el.innerHTML=tariefInhoud(bron, tid);
  });
}

function fmtNotitieTijd(iso){
  const d=new Date(iso);
  return isNaN(d.getTime()) ? '' : d.toLocaleString('nl-NL',{day:'2-digit',month:'short',hour:'2-digit',minute:'2-digit'});
}

function notitieHtml(bron, tid){
  if(!NOTITIES_ACTIEF){
    return `<div class="notitie notitie-uit">Notities zijn nog niet geactiveerd: voer eenmalig
      <code>supabase/notities_tarieven.sql</code> uit in de Supabase SQL Editor.</div>`;
  }
  const n=NOTITIES.get(notitieSleutel(bron, tid))||{};
  const t=TARIEVEN.get(notitieSleutel(bron, tid));
  const wie=n.gewijzigd_door ? `Laatst bijgewerkt door ${notitieEsc(n.gewijzigd_door)} · ${fmtNotitieTijd(n.gewijzigd_op)}` : 'Nog geen notitie';
  return `<div class="notitie" data-bron="${notitieEsc(bron)}" data-tid="${notitieEsc(tid)}">
    <div class="notitie-kop">Notitie <span class="notitie-wie">${wie}</span></div>
    <div class="notitie-velden">
      <label>Geschikt voor<input type="text" data-veld="geschikt_voor" maxlength="300" placeholder="Bijv. Jan de Vries, Priya" value="${notitieEsc(n.geschikt_voor)}"></label>
      <label>Tarief<input type="text" data-veld="tarief" maxlength="100" placeholder="${t ? 'Gescrapet: '+notitieEsc(t.tarief) : 'Bijv. € 95 /uur'}" value="${notitieEsc(n.tarief)}"></label>
      <label class="breed">Opmerking<textarea data-veld="opmerking" rows="2" maxlength="4000" placeholder="Bijv. eerst navragen bij de klant of remote kan">${notitieEsc(n.opmerking)}</textarea></label>
    </div>
    <div class="notitie-acties"><button type="button" class="notitie-opslaan">Opslaan</button><span class="notitie-melding"></span></div>
  </div>`;
}

async function slaNotitieOp(bron, tid, velden){
  const session=await getSession();
  const rij={
    bron, tender_id:String(tid),
    geschikt_voor: velden.geschikt_voor.trim()||null,
    tarief: velden.tarief.trim()||null,
    opmerking: velden.opmerking.trim()||null,
    gewijzigd_door: session?.user?.email||null,
    gewijzigd_op: new Date().toISOString(),
  };
  const {error}=await supabase.from('notities').upsert(rij, {onConflict:'bron,tender_id'});
  if(error) throw error;
  NOTITIES.set(notitieSleutel(bron, tid), rij);
  return rij;
}

// Eén keer aanroepen op een container die de notitieformulieren bevat (ook als
// die later opnieuw gerenderd worden). naOpslaan(bron, tid) mag iconen bijwerken.
function koppelNotities(container, naOpslaan){
  container.addEventListener('click', async e=>{
    const knop=e.target.closest('.notitie-opslaan');
    if(!knop) return;
    e.stopPropagation();
    const blok=knop.closest('.notitie');
    const melding=blok.querySelector('.notitie-melding');
    const velden={};
    blok.querySelectorAll('[data-veld]').forEach(el=>{ velden[el.dataset.veld]=el.value; });
    knop.disabled=true;
    melding.textContent='Opslaan…';
    try{
      const rij=await slaNotitieOp(blok.dataset.bron, blok.dataset.tid, velden);
      melding.textContent='Opgeslagen';
      blok.querySelector('.notitie-wie').textContent=`Laatst bijgewerkt door ${rij.gewijzigd_door||'jou'} · ${fmtNotitieTijd(rij.gewijzigd_op)}`;
      werkTariefCellenBij(blok.dataset.bron, blok.dataset.tid);
      if(naOpslaan) naOpslaan(blok.dataset.bron, blok.dataset.tid);
    }catch(err){
      melding.textContent='Opslaan mislukt: '+(err.message||err);
    }finally{
      knop.disabled=false;
    }
  });
}

function bezigMetNotitie(){
  return !!(document.activeElement && document.activeElement.closest && document.activeElement.closest('.notitie'));
}

// Notities van collega's live binnenhalen. naWijziging() wordt niet aangeroepen
// terwijl je zelf in een notitieveld typt, zodat je invoer niet verdwijnt.
let notitieKanaal=null;
function volgNotities(naWijziging){
  if(notitieKanaal || !NOTITIES_ACTIEF || !supabase.channel) return;
  notitieKanaal=supabase.channel('notities-live')
    .on('postgres_changes', {event:'*', schema:'public', table:'notities'}, payload=>{
      const rec=(payload.new && Object.keys(payload.new).length) ? payload.new : payload.old;
      if(!rec) return;
      const key=notitieSleutel(rec.bron, rec.tender_id);
      if(payload.eventType==='DELETE') NOTITIES.delete(key); else NOTITIES.set(key, payload.new);
      werkTariefCellenBij(rec.bron, rec.tender_id);
      if(naWijziging && !bezigMetNotitie()) naWijziging();
    })
    .subscribe();
}

// Opmaak voor de notitieformulieren; staat hier zodat beide pagina's dezelfde krijgen.
(function(){
  const css=`
  .notitie{ white-space:normal; background:rgba(255,255,255,0.03); border:1px solid var(--border); border-radius:10px; padding:10px 14px; margin-bottom:12px; font-size:12.5px; }
  .notitie-uit{ color:var(--muted); }
  .notitie-uit code{ display:inline; color:var(--sub); font-size:12px; }
  .notitie-kop{ font-weight:600; color:var(--text); margin-bottom:8px; }
  .notitie-wie{ font-weight:400; color:var(--dim); font-size:11px; margin-left:8px; }
  .notitie-velden{ display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:8px 12px; }
  .notitie-velden label{ display:flex; flex-direction:column; gap:4px; font-size:11px; color:var(--muted); }
  .notitie-velden .breed{ grid-column:1 / -1; }
  .notitie-velden input, .notitie-velden textarea{ font-family:inherit; font-size:12.5px; padding:7px 10px; border-radius:8px;
    border:1px solid var(--border); background:var(--bg2); color:var(--text); min-width:0; width:100%; resize:vertical; }
  .notitie-velden input:focus, .notitie-velden textarea:focus{ outline:2px solid var(--blauw); outline-offset:1px; }
  .notitie-acties{ display:flex; align-items:center; gap:10px; margin-top:8px; }
  .notitie-opslaan{ font-family:inherit; font-size:12px; font-weight:600; padding:7px 14px; border-radius:8px; border:none; background:var(--blauw); color:#08151f; cursor:pointer; }
  .notitie-opslaan:hover{ background:var(--blauw-l); }
  .notitie-opslaan:disabled{ opacity:.6; cursor:default; }
  .notitie-melding{ font-size:11px; color:var(--muted); }
  .notitie-icoon{ margin-left:6px; font-size:11px; cursor:help; }
  .tarief{ white-space:nowrap; color:var(--sub); font-size:12px; }
  .tarief-notitie{ color:var(--text); font-weight:600; }
  @media (max-width:700px){ .notitie-velden{ grid-template-columns:1fr; } }`;
  const st=document.createElement('style');
  st.textContent=css;
  document.head.appendChild(st);
})();
