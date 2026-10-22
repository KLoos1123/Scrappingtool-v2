/* Gedeelde marktlogica voor het dashboard (index.html) en de bronnenpagina
   (bronnen.html): trefwoorden, categorieen, regio, sales-score en het
   verrijken van een tenders-rij. Laden vóór het eigen script van de pagina. */

/* ===================== trefwoorden ===================== */
const SAP_STRONG = ['sap','abap','s/4hana','s4hana','s/4','successfactors','fiori','hana','fico','netweaver','sapui5','ariba','ibp'];
const ORACLE_STRONG = ['oracle','ebs','e-business suite','fusion','peoplesoft','jd edwards','jd-edwards','jde','hyperion','oci','netsuite','plsql','pl/sql'];
const IT_KEYWORDS = ['it','ict','software','applicatie','applicatiebeheer','systeembeheer','netwerk','developer','ontwikkelaar','engineer','devops','architect','azure','aws','cloud','data','database','business analist','business analyst','informatieanalist','informatiemanager','informatievoorziening','scrum','agile','security','informatiebeveiliging','cyber','consultant','java','python','.net','javascript','sap','oracle','erp','bi','power bi','powerbi','dynamics','m365','microsoft 365','functioneel beheer','functioneel','technisch beheer','beheerder','servicedesk','support','tester','test','ux','ui','front-end','back-end','fullstack','full-stack','integratie','koppeling','middleware','api','linux','sql','digitalisering','automatisering','rpa','ai','machine learning','platform','servicenow','salesforce','react','angular','node','product owner','scrum master','projectleider ict','implementatie','migratie'];
const IT_STRONG = ['sap','oracle','developer','ontwikkelaar','engineer','software','azure','aws','cloud','devops','architect','security','informatiebeveiliging','ict','data engineer','.net','abap','servicenow','salesforce'];
const EXCLUDE_KEYWORDS = ['schoonmaak','schoonmaker','interieurverzorger','monteur','chauffeur','buschauffeur','verkoper','verkoopmedewerker','verkoopmedewerkster','magazijn','magazijnmedewerker','operator','productiemedewerker','hovenier','servicemedewerker','beveiliger','receptionist','receptie','kok','catering','facilitair','heftruck','lasser','timmerman','schilder','stratenmaker','bezorger','postbezorger','conducteur','machinist','rangeerder','steward','gastheer','gastvrouw','barista','bediening','groenvoorziening','straatreiniger','kassamedewerker','baliemedewerker','verzorgende','verpleegkundige','apotheek','stukadoor','elektromonteur','installatiemonteur','fietsenmaker','vakkenvuller'];
const GROOT_ORG = ['ns','stedin','alliander','enexis','tennet','prorail','kpn','vodafone','rijkswaterstaat','belastingdienst','defensie','politie','rivm','ministerie','gemeente','provincie','waterschap','universiteit','hogeschool','ziekenhuis','rabobank','ing','abn','achmea','vitens','dow','shell','philips','asml'];
const BUREAUS = ['striive','magnit','flextender','harvey nash','yacht','brunel','hays','headfirst','myler','between','sthree','experis','modis','randstad','usg','tempo team','olympia','manpower','adecco','start people','young capital','circle8','bergler','ordina','conclusion','centric','cgi','capgemini','sopra steria','atos','accenture','deloitte','kpmg','pwc','info support','ilionx','valid','quintor','devoteam','profource','freelance','detach','consultancy','consultants','interim','recruit','payroll','staffing','uitzend','flexkracht','sourcing'];
function isBureauOrg(orgL){
  if(!orgL || orgL==='-' || /unknown|onbekend/.test(orgL)) return true;
  return BUREAUS.some(b=>orgL.includes(b));
}
const VACATURE_BRONNEN = new Set(['ns','stedin']);
function soortVan(bron){ return VACATURE_BRONNEN.has(bron) ? 'Vacature' : 'Tender/opdracht'; }

const SKILLS = [
  ['SAP','sap'],['Oracle','oracle|ebs|fusion|peoplesoft'],['ABAP','abap'],['S/4HANA','s/?4hana'],['SuccessFactors','successfactors'],
  ['Azure','azure'],['AWS','aws'],['Cloud','cloud'],['Power BI','power ?bi'],['Python','python'],
  ['Java','java'],['.NET','\\.net'],['DevOps','devops'],['Data','data'],['Security','security|informatiebeveiliging'],
  ['Dynamics','dynamics'],['M365','m365|microsoft 365'],['Scrum','scrum|agile'],
  ['SQL','sql'],['Linux','linux'],['ServiceNow','servicenow'],['Salesforce','salesforce'],['RPA','rpa'],['AI/ML','\\bai\\b|machine learning']
];
const SKILL_MAP = {};
SKILLS.forEach(([label,pat])=>{ SKILL_MAP[label]=new RegExp('(^|[^a-z0-9])(?:'+pat+')($|[^a-z0-9])','i'); });

const REGIO_STEDEN = {
  'Randstad':['amsterdam','rotterdam','den haag','s-gravenhage','gravenhage','utrecht','haarlem','leiden','delft','zoetermeer','amstelveen','almere','hilversum','gouda','dordrecht','schiphol','diemen','capelle','rijswijk','heinenoord'],
  'Noord':['groningen','leeuwarden','assen','drachten','heerenveen','emmen','hoogeveen'],
  'Oost':['zwolle','deventer','enschede','apeldoorn','arnhem','nijmegen','hengelo','ede','doetinchem'],
  'Zuid':['eindhoven','tilburg','breda','den bosch','s-hertogenbosch','hertogenbosch','maastricht','venlo','roermond','helmond','sittard','geleen','bergen op zoom'],
  'Midden':['amersfoort','veenendaal','nieuwegein','houten','zeist','baarn','soest']
};

const CAT_COLORS = { 'SAP':'#199DD9','Oracle':'#E9167D','Security':'#83007D','Data & BI':'#11448D','Cloud & Infra':'#4ab8e6','Development':'#2f6fb5','Functioneel & Beheer':'#b0468f','Project & Agile':'#6b7f96','Overig IT':'#5f7488','Niet-IT':'#3a4a5c' };
const CAT_ORDER = ['SAP','Oracle','Security','Data & BI','Cloud & Infra','Development','Functioneel & Beheer','Project & Agile','Overig IT','Niet-IT'];
const SMART_VIEWS = [
  {key:'hot', label:'Hot SAP & Oracle'},
  {key:'urgent', label:'Sluit binnen 7 dagen'},
  {key:'today', label:'Nieuw vandaag'},
  {key:'groot', label:'Grote eindklanten'}
];

// Interne workflow-status per tender. Puur tekstueel in de database (geen
// vaste enum), dus deze lijst is vrij aan te passen zonder migratie: gewoon
// labels toevoegen/verwijderen/hernoemen. Bestaande waarden die niet meer in
// de lijst staan blijven gewoon zichtbaar in het dropdown van die rij.
const STATUS_OPTIONS = [
  'Nog te bekijken', 'Interessant', 'Contact gelegd', 'Aanbieding verstuurd',
  'In onderhandeling', 'Gewonnen', 'Verloren', 'Niet interessant',
];
const STATUS_COLORS = {
  'Nog te bekijken':   '#5f7488',
  'Interessant':       '#199DD9',
  'Contact gelegd':    '#4ab8e6',
  'Aanbieding verstuurd':'#11448D',
  'In onderhandeling': '#83007D',
  'Gewonnen':          '#1fae6a',
  'Verloren':          '#8ea2b8',
  'Niet interessant':  '#5f7690',
};

function wordMatch(text, kw){
  const e = kw.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
  return new RegExp('(^|[^a-z0-9])'+e+'($|[^a-z0-9])','i').test(text);
}
function anyMatch(text, list){ return list.some(k=>wordMatch(text,k)); }

/* ===================== verrijking ===================== */
function isSap(t){ return SAP_STRONG.some(k=>wordMatch(t,k)); }
function isOracle(t){ return ORACLE_STRONG.some(k=>wordMatch(t,k)); }
function isIt(t){
  if(anyMatch(t, IT_STRONG)) return true;
  if(anyMatch(t, EXCLUDE_KEYWORDS)) return false;
  return anyMatch(t, IT_KEYWORDS);
}
function categorie(t, sap){
  if(sap) return 'SAP';
  if(isOracle(t)) return 'Oracle';
  if(wordMatch(t,'security')||wordMatch(t,'informatiebeveiliging')||wordMatch(t,'cyber')||wordMatch(t,'soc')) return 'Security';
  if(wordMatch(t,'data')||wordMatch(t,'bi')||wordMatch(t,'power bi')||wordMatch(t,'powerbi')||wordMatch(t,'analytics')||wordMatch(t,'analist')) return 'Data & BI';
  if(wordMatch(t,'cloud')||wordMatch(t,'azure')||wordMatch(t,'aws')||wordMatch(t,'infra')||wordMatch(t,'netwerk')||wordMatch(t,'devops')||wordMatch(t,'systeembeheer')||wordMatch(t,'linux')) return 'Cloud & Infra';
  if(wordMatch(t,'developer')||wordMatch(t,'ontwikkelaar')||wordMatch(t,'engineer')||wordMatch(t,'java')||wordMatch(t,'python')||wordMatch(t,'.net')||wordMatch(t,'software')||wordMatch(t,'front-end')||wordMatch(t,'back-end')||wordMatch(t,'fullstack')) return 'Development';
  if(wordMatch(t,'functioneel')||wordMatch(t,'beheer')||wordMatch(t,'beheerder')||wordMatch(t,'support')||wordMatch(t,'servicedesk')||wordMatch(t,'applicatiebeheer')||wordMatch(t,'tester')||wordMatch(t,'test')) return 'Functioneel & Beheer';
  if(wordMatch(t,'projectleider')||wordMatch(t,'projectmanager')||wordMatch(t,'programmamanager')||wordMatch(t,'scrum')||wordMatch(t,'agile')||wordMatch(t,'product owner')||wordMatch(t,'implementatie')||wordMatch(t,'transitie')) return 'Project & Agile';
  return 'Overig IT';
}
function sapRol(t){
  if(wordMatch(t,'abap')) return 'ABAP';
  if(wordMatch(t,'basis')) return 'Basis';
  if(wordMatch(t,'fico')||wordMatch(t,'finance')) return 'FICO / Finance';
  if(wordMatch(t,'successfactors')||wordMatch(t,'hcm')) return 'SuccessFactors / HCM';
  if(wordMatch(t,'s/4hana')||wordMatch(t,'s4hana')||wordMatch(t,'s/4')) return 'S/4HANA';
  if(wordMatch(t,'sd')) return 'SD (Sales)';
  if(wordMatch(t,'mm')) return 'MM (Materials)';
  if(wordMatch(t,'pm')) return 'PM (Onderhoud)';
  if(wordMatch(t,'pp')) return 'PP (Productie)';
  if(wordMatch(t,'ewm')||wordMatch(t,'wm')) return 'EWM / Logistiek';
  if(wordMatch(t,'bw')||wordMatch(t,'analytics')) return 'BW / Analytics';
  if(wordMatch(t,'ariba')) return 'Ariba / Inkoop';
  if(wordMatch(t,'functioneel')) return 'Functioneel beheer';
  return 'SAP consultant / overig';
}
function oracleRol(t){
  if(wordMatch(t,'ebs')||wordMatch(t,'e-business')) return 'EBS';
  if(wordMatch(t,'fusion')) return 'Fusion';
  if(wordMatch(t,'peoplesoft')) return 'PeopleSoft';
  if(wordMatch(t,'jde')||wordMatch(t,'jd edwards')||wordMatch(t,'jd-edwards')) return 'JD Edwards';
  if(wordMatch(t,'hyperion')||wordMatch(t,'epm')) return 'Hyperion / EPM';
  if(wordMatch(t,'netsuite')) return 'NetSuite';
  if(wordMatch(t,'oci')||wordMatch(t,'oracle cloud')) return 'OCI / Cloud';
  if(wordMatch(t,'plsql')||wordMatch(t,'pl/sql')||wordMatch(t,'dba')) return 'DBA / PL-SQL';
  return 'Oracle consultant / overig';
}
function grootOrg(o){ return GROOT_ORG.some(k=>o.includes(k)); }
function regioVan(plaats, org){
  const p=(plaats||'').toLowerCase();
  if(/remote|thuis|hybride/.test(p)) return 'Remote';
  for(const [regio, steden] of Object.entries(REGIO_STEDEN)){ if(steden.some(s=>p.includes(s))) return regio; }
  const o=(org||'').toLowerCase();
  for(const [regio, steden] of Object.entries(REGIO_STEDEN)){ if(steden.some(s=>o.includes(s))) return regio; }
  return 'Overig / onbekend';
}
function recencyDagen(v){
  const ref = v._eerst || v._pub;
  if(!ref) return null;
  return (Date.now()-ref)/86400000;
}
function tijdComponent(v){
  if(v._deadline!=null){
    const dg=v.dagenTotDeadline;
    if(dg<0) return -40;
    if(dg<=3) return 22;
    if(dg<=7) return 18;
    if(dg<=21) return 12;
    return 8;
  }
  const d=(v.leeftijdDagen!=null)? v.leeftijdDagen : recencyDagen(v);
  if(d===null) return 6;
  const weken=d/7;
  return Math.round(20 - 5*weken);
}
function salesScore(v){
  let s=0;
  if(v.isIt) s+=30;
  if(v.isSap||v.isOracle) s+=35;
  if(v.grootOrg) s+=15;
  if(!v.isBureau) s+=8;
  s+=tijdComponent(v);
  if(/s\/?4hana|public cloud|\becc\b|\berp\b/i.test(v.titel)) s+=8;
  if((v.bron_status||'').toLowerCase()!=='open') s-=15;
  return Math.max(0,Math.min(100,s));
}
function scoreKlasse(s){ return s>=80?'s-hot':s>=55?'s-warm':'s-cool'; }
function rolVan(r){ return r.isSap?sapRol(r.titel):(r.isOracle?oracleRol(r.titel):null); }

/* ===================== rij verrijken ===================== */
// Eén rij uit de 'tenders'-tabel omzetten naar het verrijkte rij-object dat
// dashboard en bronnenpagina gebruiken. ai = de korte AI-verrijking (of null).
function verrijkRij(r, ai){
  const titel=r.titel||'(geen titel)';
  const organisatie=r.organisatie||'-';
  const orgL=organisatie.toLowerCase();
  const aiModules=(ai && ai.modules || []).join(' ');
  const sap=isSap(titel) || /\bSAP\b/i.test(aiModules);
  const orc=isOracle(titel) || /oracle|jd edwards|peoplesoft|netsuite|hyperion/i.test(aiModules);
  const it=sap||orc||isIt(titel);
  const bron=r.bron||'onbekend';
  const v={
    bron, tender_id:String(r.tender_id||r.nummer||''), nummer:r.nummer||'', titel, organisatie,
    bron_status:r.bron_status||'-', url:r.url||'', locatie:r.locatie||'', deadline:r.deadline||'',
    publicatiedatum:r.publicatiedatum||'',
    status: r.status||'', status_gewijzigd_door: r.status_gewijzigd_door||'',
    status_gewijzigd_op: r.status_gewijzigd_op||'',
    _pub: r.publicatiedatum? new Date(r.publicatiedatum).getTime(): (r.eerst_gezien? new Date(r.eerst_gezien).getTime():null),
    _eerst: r.eerst_gezien? new Date(r.eerst_gezien).getTime(): null,
    _deadline: r.deadline? new Date(r.deadline).getTime(): null,
    isSap:sap, isOracle:orc, isIt:it, ai,
    isBureau: isBureauOrg(orgL), grootOrg:grootOrg(orgL),
    soort: soortVan(bron),
    categorie: it? categorie(titel,sap) : 'Niet-IT',
    regio: regioVan(r.locatie, organisatie),
  };
  if(v._pub && isNaN(v._pub)) v._pub=null;
  if(v._eerst && isNaN(v._eerst)) v._eerst=null;
  if(v._deadline && isNaN(v._deadline)) v._deadline=null;
  v.datum = v._pub;
  const _now=Date.now();
  v.dagenTotDeadline = v._deadline!=null ? Math.floor((v._deadline - _now)/86400000) : null;
  v.verlopen = v._deadline!=null && v._deadline < _now;
  const _pubRef = v._pub || v._eerst;
  v.leeftijdDagen = _pubRef!=null ? (_now-_pubRef)/86400000 : null;
  const _heeftToekomstDeadline = v._deadline!=null && v._deadline >= _now;
  v.verouderd = !_heeftToekomstDeadline && v.leeftijdDagen!=null && v.leeftijdDagen > 90;
  v.score = salesScore(v);
  const d=recencyDagen(v);
  v.isVandaag = d!==null && d<1;
  v.isWeek = d!==null && d<7;
  return v;
}

/* ===================== dubbele opdrachten ===================== */
// Dezelfde opdracht staat vaak bij meerdere brokers/portalen (bv. een gemeente
// via Mercell én TenderNed). groepeerDubbel voegt die samen tot één regel; de
// andere vindplaatsen komen in r.ookOp. Regels: zelfde titel (zonder nummers,
// codes en woorden als zzp/interim), zelfde organisatie of een bron die de
// organisatie verbergt, en deadlines hooguit een week uit elkaar.
const DUBBEL_RUIS = /\b(tk\d?|m\/v(\/x)?|v\/m|h\/v|zzp|zzp'er|freelance|freelancer|interim|inhuur|opdracht|vacature|gezocht)\b/g;
function titelSleutel(t){
  return String(t || '').toLowerCase()
    .replace(/\(.*?\)/g, ' ')
    .replace(/\b[a-z]{0,4}\d[\w./-]*\b/g, ' ')
    .replace(DUBBEL_RUIS, ' ')
    .replace(/[^a-zà-ÿ ]+/g, ' ')
    .replace(/\s+/g, ' ').trim();
}
function orgSleutel(r){
  const o = String(r.organisatie || '').toLowerCase().trim();
  if(!o || o === '-' || r.isBureau || /^client team|onbekend|unknown/.test(o)) return '';
  return o.replace(/\b(gemeente|provincie|b\.?v\.?|n\.?v\.?)\b/g, ' ').replace(/[^a-z0-9à-ÿ]+/g, ' ').trim();
}
function deadlinesPassen(a, b){
  return a._deadline == null || b._deadline == null || Math.abs(a._deadline - b._deadline) <= 7 * 86400000;
}
// Hoe geschikt een regel is om de samengevoegde opdracht te tonen.
function voorkeur(r){
  return (r.status ? 1000 : 0) + (orgSleutel(r) ? 100 : 0) + (r._deadline != null ? 50 : 0) + (r.url ? 5 : 0) + r.score / 100;
}
function groepeerDubbel(rows){
  const perTitel = new Map();
  // eerst regels met een bekende organisatie, dan pas de rest aan een groep koppelen
  const volgorde = rows.map((r, i) => [r, i]).sort((a, b) => (orgSleutel(a[0]) ? 0 : 1) - (orgSleutel(b[0]) ? 0 : 1));
  volgorde.forEach(([r, i]) => {
    const t = titelSleutel(r.titel);
    if(t.length < 8){ perTitel.set('#' + i, [[r]]); return; }   // te kort om op te vertrouwen
    if(!perTitel.has(t)) perTitel.set(t, []);
    const groepen = perTitel.get(t), o = orgSleutel(r);
    let doel = null;
    if(o){
      doel = groepen.find(g => g.some(x => orgSleutel(x) === o) && g.every(x => deadlinesPassen(x, r)))
        || null;
    } else {
      // zonder organisatie alleen bij precies één passende groep mét bekende organisatie;
      // twee onbekenden met een algemene titel ("Java ontwikkelaar") zijn vaak verschillende klanten
      const passend = groepen.filter(g => g.some(x => orgSleutel(x)) && g.every(x => deadlinesPassen(x, r)));
      if(passend.length === 1) doel = passend[0];
    }
    if(doel) doel.push(r); else groepen.push([r]);
  });
  const hoofd = new Map();   // regel -> samengevoegde groep, in de oorspronkelijke volgorde
  for(const groepen of perTitel.values()){
    for(const g of groepen){
      const beste = g.reduce((a, b) => voorkeur(b) > voorkeur(a) ? b : a);
      beste.ookOp = g.filter(x => x !== beste);
      g.forEach(x => hoofd.set(x, beste));
    }
  }
  const gezien = new Set(), uit = [];
  rows.forEach(r => { const b = hoofd.get(r); if(!gezien.has(b)){ gezien.add(b); uit.push(b); } });
  return uit;
}
