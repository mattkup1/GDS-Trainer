(function(){
  "use strict";

  // ---------- DOM ----------
  const outputEl = document.getElementById('output');
  const screenEl = document.getElementById('screen');
  const inputEl  = document.getElementById('cmdline');

  function print(text, cls){
    const lines = String(text).split('\n');
    for(const l of lines){
      const div = document.createElement('div');
      div.className = 'line' + (cls ? ' '+cls : '');
      div.textContent = l.length ? l : ' ';
      outputEl.appendChild(div);
    }
    screenEl.scrollTop = screenEl.scrollHeight;
  }
  function printErr(text){ print(text, 'err'); }
  function printBlank(){ print(''); }

  screenEl.addEventListener('click', ()=> inputEl.focus());
  inputEl.focus();

  // ---------- RNG / hashing ----------
  function hashStr(s){
    let h = 2166136261;
    for(let i=0;i<s.length;i++){ h ^= s.charCodeAt(i); h = Math.imul(h, 16777619); }
    return h >>> 0;
  }
  function mulberry32(a){
    return function(){
      a |= 0; a = (a + 0x6D2B79F5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  // ---------- reference data ----------
  const MONTHS = ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC'];
  const WEEKDAYS = ['SUN','MON','TUE','WED','THU','FRI','SAT'];
  const AIRLINES = ['AA','UA','DL','WN','B6','AS','NK','F9'];
  const EQUIP = ['738','73G','320','321','32N','E75','CR9','777','788','319'];
  const CLASSES = ['F','J','C','Y','B','M'];

  // AIRPORTS (code -> [name, city, country]) is loaded globally from airports.js
  function cityName(code){
    const a = typeof AIRPORTS !== 'undefined' ? AIRPORTS[code] : null;
    return a ? a[1].toUpperCase()+' '+code : 'CITY '+code;
  }

  // ---------- date helpers ----------
  function parseDate(dayStr, monStr){
    monStr = monStr.toUpperCase();
    const mi = MONTHS.indexOf(monStr);
    if(mi < 0) return null;
    const day = parseInt(dayStr, 10);
    if(!day || day < 1 || day > 31) return null;
    const now = new Date();
    let year = now.getFullYear();
    let d = new Date(year, mi, day, 12, 0, 0);
    const daysInMonth = new Date(year, mi+1, 0).getDate();
    if(day > daysInMonth) return null;
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    if(d < today){
      year += 1;
      d = new Date(year, mi, day, 12, 0, 0);
    }
    return { date:d, day, mon:monStr, year, weekday: WEEKDAYS[d.getDay()] };
  }
  function minutesToClock(mins){
    mins = ((mins % 1440) + 1440) % 1440;
    let hh = Math.floor(mins/60), mm = mins%60;
    const ampm = hh < 12 ? 'A' : 'P';
    let hh12 = hh % 12; if(hh12 === 0) hh12 = 12;
    return `${hh12}${String(mm).padStart(2,'0')}${ampm}`;
  }
  function pad(s, n){ s = String(s); return s + ' '.repeat(Math.max(0, n - s.length)); }

  // ---------- state ----------
  const state = {
    signedIn: false,
    sine: null,
    pcc: null,
    lastAvail: null,   // {orig,dest,dateInfo,flights:[...]}
    pnr: freshPNR(),
    lastDisplay: [],   // numbered element map for X{n}
    history: {},        // locator -> saved pnr snapshot
    cmdHistory: [],
    cmdHistoryIdx: -1
  };

  function freshPNR(){
    return { locator:null, names:[], segments:[], phones:[], receivedFrom:null, ticketing:null, pricing:null };
  }

  // ---------- availability ----------
  function genAvailability(dayStr, monStr, orig, dest){
    if(orig === dest){ printErr('FORMAT - ORIGIN AND DESTINATION CANNOT BE THE SAME'); return; }
    const dinfo = parseDate(dayStr, monStr);
    if(!dinfo){ printErr('INVALID DATE - CHECK ENTRY AND REENTER'); return; }

    const seed = hashStr(`${orig}${dest}${dinfo.day}${dinfo.mon}${dinfo.year}`);
    const rng = mulberry32(seed);
    const numFlights = 5 + Math.floor(rng()*4);
    const flights = [];
    let dep = 300 + Math.floor(rng()*90);
    for(let i=0;i<numFlights;i++){
      const airline = AIRLINES[Math.floor(rng()*AIRLINES.length)];
      const flightNum = 100 + Math.floor(rng()*2899);
      const duration = 65 + Math.floor(rng()*220);
      const arr = dep + duration;
      const equip = EQUIP[Math.floor(rng()*EQUIP.length)];
      const classAvail = CLASSES.map(c => ({ cls:c, seats: Math.floor(rng()*10) }));
      flights.push({ line:i+1, airline, flightNum, dep, arr, duration, equip, classAvail });
      dep += 55 + Math.floor(rng()*95);
      if(dep > 1380) dep = 300 + Math.floor(rng()*60);
    }
    state.lastAvail = { orig, dest, dinfo, flights };

    print(`** AIR AVAILABILITY **  ${orig}-${dest}  ${dinfo.day}${dinfo.mon}${dinfo.year}  ${dinfo.weekday}`, 'hd');
    print(`  ${cityName(orig)}  TO  ${cityName(dest)}`, 'dim');
    printBlank();
    print(`LN  FLT       ${CLASSES.map(c=>pad(c,3)).join('')} DEP    ARR    EQP`, 'dim');
    for(const f of flights){
      const classStr = f.classAvail.map(c => pad(c.cls + c.seats, 3)).join('');
      print(` ${pad(f.line,2)} ${f.airline} ${pad(f.flightNum,4)}  ${classStr} ${pad(minutesToClock(f.dep),6)} ${pad(minutesToClock(f.arr),6)} ${f.equip}`);
    }
    printBlank();
    print('SELL WITH: 0{LINE}{CLASS}{SEATS}   e.g. 0' + flights[0].line + 'Y1', 'dim');
  }

  function sellFromAvail(lineNum, cls, seats){
    if(!state.lastAvail){ printErr('NO AVAILABILITY DISPLAY IN CONTEXT - ENTER AVAIL FIRST'); return; }
    const f = state.lastAvail.flights.find(fl => fl.line === lineNum);
    if(!f){ printErr('INVALID LINE NUMBER - CHECK ENTRY AND REENTER'); return; }
    const cinfo = f.classAvail.find(c => c.cls === cls.toUpperCase());
    if(!cinfo){ printErr(`CLASS ${cls.toUpperCase()} NOT OFFERED ON THIS FLIGHT`); return; }
    if(cinfo.seats === 0){ printErr(`CLASS ${cls.toUpperCase()} SOLD OUT - CLOSED`); return; }
    if(seats > cinfo.seats){ printErr(`UNABLE - ONLY ${cinfo.seats} SEAT(S) AVAILABLE IN CLASS ${cls.toUpperCase()}`); return; }

    const seg = {
      airline: f.airline, flightNum: f.flightNum, cls: cls.toUpperCase(), seats,
      dinfo: state.lastAvail.dinfo, orig: state.lastAvail.orig, dest: state.lastAvail.dest,
      dep: f.dep, arr: f.arr, status: 'HK'
    };
    state.pnr.segments.push(seg);
    print(`SEGMENT SOLD - ${formatSegmentShort(seg)}`);
    invalidatePricing();
    refreshAndPrintPNR();
  }

  function directSell(airline, flightNum, cls, dayStr, monStr, orig, dest, statusCode, seats){
    if(orig === dest){ printErr('FORMAT - ORIGIN AND DESTINATION CANNOT BE THE SAME'); return; }
    const dinfo = parseDate(dayStr, monStr);
    if(!dinfo){ printErr('INVALID DATE - CHECK ENTRY AND REENTER'); return; }
    const seed = hashStr(`${airline}${flightNum}${orig}${dest}${dinfo.day}${dinfo.mon}`);
    const rng = mulberry32(seed);
    const dep = 300 + Math.floor(rng()*900);
    const arr = dep + 65 + Math.floor(rng()*220);
    const seg = {
      airline: airline.toUpperCase(), flightNum: parseInt(flightNum,10), cls: cls.toUpperCase(), seats,
      dinfo, orig, dest, dep, arr, status: (statusCode||'HK').toUpperCase()
    };
    state.pnr.segments.push(seg);
    print(`SEGMENT SOLD - ${formatSegmentShort(seg)}`);
    invalidatePricing();
    refreshAndPrintPNR();
  }

  function invalidatePricing(){
    if(state.pnr.pricing){
      state.pnr.pricing = null;
      print('FARE QUOTE INVALIDATED - ITINERARY CHANGED, RE-PRICE WITH WP', 'dim');
    }
  }

  function formatSegmentShort(seg){
    return `${seg.airline}${seg.flightNum} ${seg.cls} ${seg.dinfo.day}${seg.dinfo.mon} ${seg.orig}${seg.dest} ${seg.status}${seg.seats}  ${minutesToClock(seg.dep)} ${minutesToClock(seg.arr)}`;
  }

  // ---------- pricing (WP / WPNCS) ----------
  const CLASS_FARE_MULT = { F:5.5, J:4.2, C:3.6, Y:1.6, B:1.3, M:1.0 };
  const TAX_POOL = [
    { code:'US', label:'U.S. TRANSPORTATION TAX' },
    { code:'XF', label:'PASSENGER FACILITY CHARGE' },
    { code:'AY', label:'SEPTEMBER 11TH SECURITY FEE' },
    { code:'ZP', label:'PASSENGER SERVICE CHARGE' },
    { code:'YQ', label:'CARRIER-IMPOSED SURCHARGE' },
    { code:'YR', label:'CARRIER-IMPOSED SURCHARGE' }
  ];

  function priceItinerary(mode){
    const p = state.pnr;
    if(p.segments.length === 0){ printErr('UNABLE TO PRICE - NO ITINERARY SEGMENTS'); return; }
    if(p.names.length === 0){ printErr('UNABLE TO PRICE - NAME FIELD REQUIRED PRIOR TO PRICING'); return; }

    const seed = hashStr(p.segments.map(s => `${s.airline}${s.flightNum}${s.cls}${s.dinfo.day}${s.dinfo.mon}${s.orig}${s.dest}${s.seats}`).join('|') + mode);
    const rng = mulberry32(seed);

    let baseFare = 0;
    for(const s of p.segments){
      const mult = CLASS_FARE_MULT[s.cls] || 1.4;
      const dist = 60 + Math.floor(rng()*400);
      baseFare += Math.round((45 + dist*0.35) * mult * s.seats);
    }

    const numTaxes = 2 + Math.floor(rng()*3);
    const pool = TAX_POOL.slice().sort(() => rng()-0.5).slice(0, numTaxes);
    const taxes = [];
    let taxTotal = 0;
    for(const t of pool){
      const amt = Math.round((3 + rng()*22) * 100)/100;
      taxes.push({ code:t.code, label:t.label, amount:amt });
      taxTotal += amt;
    }
    taxTotal = Math.round(taxTotal*100)/100;
    const total = Math.round((baseFare + taxTotal)*100)/100;
    const fareBasis = `${p.segments[0].cls}OW`;

    p.pricing = { mode, baseFare, taxes, taxTotal, total, fareBasis, currency:'USD' };

    print(mode === 'WPNCS' ? '** LOWEST FARE - WPNCS (SUBJECT TO AVAILABILITY) **' : '** ITINERARY PRICING - WP **', 'hd');
    p.segments.forEach((s,i) => print(`  ${i+1}  ${formatSegmentShort(s)}`, 'dim'));
    printBlank();
    print(`FARE BASIS: ${fareBasis}`);
    print(`BASE FARE      USD ${baseFare.toFixed(2)}`);
    for(const t of taxes){ print(`  ${t.code}   USD ${t.amount.toFixed(2)}   ${t.label}`, 'dim'); }
    print(`TAXES/FEES     USD ${taxTotal.toFixed(2)}`);
    print(`TOTAL          USD ${total.toFixed(2)}`, 'hd');
    printBlank();
    print('FARE QUOTE STORED - REQUIRED PRIOR TO TICKETING', 'dim');
    refreshAndPrintPNR();
  }

  function formatPricingShort(pr){
    return `${pr.mode}  ${pr.fareBasis}  BASE USD${pr.baseFare.toFixed(2)}  TAX USD${pr.taxTotal.toFixed(2)}  TTL USD${pr.total.toFixed(2)}`;
  }

  // ---------- PNR element display / cancel ----------
  function buildElements(){
    const els = [];
    state.pnr.names.forEach((n, i) => els.push({ kind:'name', idx:i, label:`NM${i+1}`, text:n }));
    state.pnr.segments.forEach((s, i) => els.push({ kind:'segment', idx:i, label:`SEG${i+1}`, text: formatSegmentShort(s) + `  ${s.dinfo.weekday}` }));
    if(state.pnr.pricing) els.push({ kind:'fq', idx:0, label:'FQ', text: formatPricingShort(state.pnr.pricing) });
    state.pnr.phones.forEach((p, i) => els.push({ kind:'phone', idx:i, label:'CTC', text:p }));
    if(state.pnr.receivedFrom) els.push({ kind:'rf', idx:0, label:'RF', text: state.pnr.receivedFrom });
    if(state.pnr.ticketing) els.push({ kind:'tk', idx:0, label:'TK', text: state.pnr.ticketing });
    els.forEach((e, i) => e.num = i+1);
    return els;
  }

  function refreshAndPrintPNR(){
    state.lastDisplay = buildElements();
    printBlank();
    print(`RLOC: ${state.pnr.locator || '(NOT SAVED - END TRANSACT TO STORE)'}`, 'hd');
    if(state.lastDisplay.length === 0){
      print('  ** PNR IS EMPTY **', 'dim');
      return;
    }
    for(const e of state.lastDisplay){
      print(` ${pad(e.num,2)}  ${pad(e.label,5)} ${e.text}`);
    }
  }

  function removeElement(e){
    if(e.kind === 'name') state.pnr.names.splice(e.idx, 1);
    else if(e.kind === 'segment'){ state.pnr.segments.splice(e.idx, 1); state.pnr.pricing = null; }
    else if(e.kind === 'fq') state.pnr.pricing = null;
    else if(e.kind === 'phone') state.pnr.phones.splice(e.idx, 1);
    else if(e.kind === 'rf') state.pnr.receivedFrom = null;
    else if(e.kind === 'tk') state.pnr.ticketing = null;
  }

  function cancelElements(nums){
    const uniqDesc = Array.from(new Set(nums)).sort((a,b) => b-a);
    const cancelled = [];
    for(const n of uniqDesc){
      const e = state.lastDisplay.find(x => x.num === n);
      if(!e) continue;
      removeElement(e);
      cancelled.push(n);
    }
    if(cancelled.length === 0){ printErr('INVALID ELEMENT NUMBER - REDISPLAY WITH *R'); return; }
    cancelled.sort((a,b) => a-b);
    print(`ELEMENT${cancelled.length > 1 ? 'S' : ''} ${cancelled.join(',')} CANCELLED`);
    refreshAndPrintPNR();
  }

  function cancelItinerary(){
    if(state.pnr.segments.length === 0){ printErr('NO ITINERARY SEGMENTS TO CANCEL'); return; }
    state.pnr.segments = [];
    state.pnr.pricing = null;
    print('ITINERARY CANCELLED');
    refreshAndPrintPNR();
  }

  // ---------- end transaction ----------
  function genLocator(){
    const chars = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
    let s = '';
    do {
      s = '';
      for(let i=0;i<6;i++) s += chars[Math.floor(Math.random()*chars.length)];
    } while(state.history[s]);
    return s;
  }

  function endTransaction(mode){
    const p = state.pnr;
    if(p.segments.length === 0){ printErr('PNR INCOMPLETE - NO ITINERARY SEGMENTS'); return; }
    if(p.names.length === 0){ printErr('PNR INCOMPLETE - NEED NAME FIELD (ENTRY: -SURNAME/GIVEN)'); return; }
    if(!p.pricing){ printErr('PNR INCOMPLETE - NEED FARE QUOTE (ENTRY: WP)'); return; }
    if(p.phones.length === 0){ printErr('PNR INCOMPLETE - NEED PHONE FIELD (ENTRY: 9...)'); return; }
    if(!p.receivedFrom){ printErr('PNR INCOMPLETE - NEED RECEIVED FROM (ENTRY: 6...)'); return; }
    if(!p.ticketing){ printErr('PNR INCOMPLETE - NEED TICKETING ARRANGEMENT (ENTRY: 7TAW/)'); return; }

    if(!p.locator) p.locator = genLocator();
    state.history[p.locator] = JSON.parse(JSON.stringify(p));

    const now = new Date();
    const ts = `${pad(now.getDate(),2).trim()}${MONTHS[now.getMonth()]}  ${minutesToClock(now.getHours()*60+now.getMinutes())}`;
    print('END OF TRANSACTION COMPLETE', 'hd');
    print(`  ${ts}   RLOC: ${p.locator}`);

    if(mode === 'ET'){
      state.pnr = freshPNR();
      state.lastDisplay = [];
      print('WORK AREA CLEARED - READY FOR NEXT ENTRY', 'dim');
    } else {
      refreshAndPrintPNR();
    }
  }

  function retrieveByLocator(loc){
    const rec = state.history[loc];
    if(!rec){ printErr('RECORD LOCATOR NOT FOUND'); return; }
    state.pnr = JSON.parse(JSON.stringify(rec));
    print(`PNR ${loc} RETRIEVED`);
    refreshAndPrintPNR();
  }

  // ---------- help ----------
  function showHelp(){
    print('SABRE-STYLE ENTRY REFERENCE', 'hd');
    printBlank();
    print('SIGN ON/OFF', 'hd');
    print('  SI[sine/pcc]        Sign in           e.g. SI  or  SI1234AA/DFW1');
    print('  SO                  Sign out');
    printBlank();
    print('AVAILABILITY', 'hd');
    print('  A{DD}{MMM}{ORG}{DST}   Air availability   e.g. A15AUGDFWORD');
    print('  1{DD}{MMM}{ORG}{DST}   Air availability (alternate entry)  e.g. 115AUGDFWORD');
    printBlank();
    print('SELL', 'hd');
    print('  0{LN}{CLASS}{SEATS}                        Sell from avail line   e.g. 04Y1');
    print('  0{AL}{FLT}{CLASS}{DD}{MMM}{ORG}{DST}{STATUS}{SEATS}');
    print('                                              Direct/long sell   e.g. 0AA100Y15AUGDFWORDNN1');
    printBlank();
    print('PNR BUILD', 'hd');
    print('  -{SURNAME}/{GIVEN} {TITLE}          Name field   e.g. -SMITH/JOHN MR');
    print('  -{N}{SURNAME}/{G1} {T1}/{G2} {T2}   Multiple passengers, same surname');
    print('                                       e.g. -2SMITH/JOHN MR/JANE MRS');
    print('  9{NUMBER}-{LOC}                     Phone field   e.g. 9214555-1234-A');
    print('  9/{CTY}{NUMBER}-{LOC}               Phone field, out-of-area   e.g. 9/BOS617-555-1234-A');
    print('  6{TEXT}                             Received from   e.g. 6JSMITH');
    print('  WP                                  Price itinerary (required before ticketing)');
    print('  WPNCS                               Price - lowest fare regardless of availability');
    print('  7TAW/                               Ticketing: at will (ticket on/before departure)');
    print('  7TAW{DD}{MMM}/{HHMM}                Ticketing at will, queued to date/time');
    print('  7TAX{DD}{MMM}/{HHMM}                Ticketing time limit   e.g. 7TAX16AUG/1800');
    printBlank();
    print('PNR MANAGEMENT', 'hd');
    print('  *R  or  *              Display current PNR');
    print('  *{LOCATOR}             Retrieve PNR by record locator');
    print('  X{N}                   Cancel numbered element N');
    print('  X{N}-{M}, X{N},{M}     Cancel a range or list of elements');
    print('  XI                     Cancel entire itinerary (all segments)');
    print('  IG                     Ignore PNR (discard unsaved work)');
    print('  ER                     End transaction, redisplay');
    print('  ET                     End transaction, clear work area');
    printBlank();
    print('Everything above is entered on the command line and submitted with Enter.', 'dim');
  }

  // ---------- sign in/out ----------
  function signIn(rest){
    rest = (rest||'').trim();
    let sine = '9TAA', pcc = 'DFW1';
    if(rest){
      const parts = rest.split('/');
      if(parts[0]) sine = parts[0].toUpperCase();
      if(parts[1]) pcc = parts[1].toUpperCase();
    }
    state.signedIn = true;
    state.sine = sine;
    state.pcc = pcc;
    const now = new Date();
    print('SABRE SYSTEM ONE - SIGN IN COMPLETE', 'hd');
    print(`  AGENT SINE: ${sine}   PCC: ${pcc}   ${MONTHS[now.getMonth()]}${pad(now.getDate(),2).trim()} ${now.getFullYear()}`);
    printBlank();
    print('TYPE HELP FOR COMMAND REFERENCE', 'dim');
  }

  function signOut(){
    print('SIGNED OFF', 'hd');
    state.signedIn = false;
    state.sine = null;
    state.pcc = null;
  }

  // ---------- boot ----------
  function boot(){
    print('S*A*B*R*E*  ------------------------------------------------', 'hd');
    print('            GLOBAL DISTRIBUTION SYSTEM - TERMINAL EMULATION');
    print('            ------------------------------------------------');
    printBlank();
    print('NOT SIGNED IN', 'dim');
    print('TYPE SI TO SIGN IN   ·   HELP FOR COMMAND REFERENCE', 'dim');
  }
  boot();

  // ---------- command dispatch ----------
  function processCommand(raw){
    const cmd = raw.trim();
    if(cmd.length === 0) return;
    const U = cmd.toUpperCase();

    if(!state.signedIn){
      if(/^SI/.test(U)){ signIn(U.slice(2)); return; }
      if(/^HELP/.test(U)){ showHelp(); return; }
      printErr('NOT SIGNED IN - ENTER: SI');
      return;
    }

    let m;
    if(U === 'SO'){ signOut(); return; }
    if(/^HELP/.test(U)){ showHelp(); return; }

    if((m = U.match(/^A(\d{1,2})([A-Z]{3})([A-Z]{3})([A-Z]{3})$/))){
      genAvailability(m[1], m[2], m[3], m[4]); return;
    }
    if((m = U.match(/^1(\d{1,2})([A-Z]{3})([A-Z]{3})([A-Z]{3})$/))){
      genAvailability(m[1], m[2], m[3], m[4]); return;
    }
    if((m = U.match(/^0(\d{1,2})([A-Z])(\d{1,2})$/))){
      sellFromAvail(parseInt(m[1],10), m[2], parseInt(m[3],10)); return;
    }
    if((m = U.match(/^0([A-Z]{2})(\d{1,4})([A-Z])(\d{1,2})([A-Z]{3})([A-Z]{3})([A-Z]{3})([A-Z]{2})(\d{1,2})$/))){
      directSell(m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], parseInt(m[9],10)); return;
    }
    if(U.startsWith('-')){
      const text = cmd.slice(1).trim();
      if(!text.includes('/')){ printErr('FORMAT - NAME MUST BE SURNAME/GIVEN NAME'); return; }
      const parts = text.split('/').map(s => s.trim()).filter(s => s.length);
      const headMatch = parts.length >= 2 ? parts[0].match(/^(\d{1,2})?([A-Z][A-Z\-' ]*)$/i) : null;
      if(!headMatch){ printErr('FORMAT - NAME MUST BE SURNAME/GIVEN NAME'); return; }
      const surname = headMatch[2].toUpperCase();
      const added = [];
      for(const g of parts.slice(1)){
        const full = `${surname}/${g.toUpperCase()}`;
        state.pnr.names.push(full);
        added.push(full);
      }
      print(`NAME${added.length > 1 ? 'S' : ''} ADDED - ${added.join('  ')}`);
      refreshAndPrintPNR();
      return;
    }
    if(U.startsWith('9')){
      const text = cmd.slice(1).trim();
      const pm = text.match(/^(?:\/([A-Z]{3}))?(\d[\d\-]{4,14})-([A-Z]{1,3})$/i);
      const PHONE_LOC_CODES = ['A','H','B','C','M','F','HTL'];
      if(!pm || !PHONE_LOC_CODES.includes(pm[3].toUpperCase())){
        printErr('FORMAT - PHONE MUST BE 9[/CTY]NUMBER-LOC  e.g. 9DFW555-1234-A'); return;
      }
      const formatted = `${pm[1] ? '/'+pm[1].toUpperCase() : ''}${pm[2]}-${pm[3].toUpperCase()}`;
      state.pnr.phones.push(formatted);
      print(`PHONE ADDED - 9${formatted}`);
      refreshAndPrintPNR();
      return;
    }
    if(U.startsWith('6') && U !== '6'){
      const text = cmd.slice(1).trim();
      if(!text){ printErr('FORMAT - RECEIVED FROM TEXT REQUIRED'); return; }
      state.pnr.receivedFrom = text.toUpperCase();
      print(`RECEIVED FROM ADDED - ${text.toUpperCase()}`);
      refreshAndPrintPNR();
      return;
    }
    if(U === 'WP' || U === 'WPNCS'){ priceItinerary(U); return; }
    if(U === '7TAW/' || U === '7TAW'){
      state.pnr.ticketing = '7TAW/ (TICKETING AT WILL - TICKET ON OR BEFORE DEPARTURE)';
      print('TICKETING ARRANGEMENT ADDED - 7TAW/');
      refreshAndPrintPNR();
      return;
    }
    if((m = U.match(/^7TAW(\d{1,2})([A-Z]{3})\/(\d{3,4})?$/))){
      const dinfo = parseDate(m[1], m[2]);
      if(!dinfo){ printErr('INVALID DATE - CHECK ENTRY AND REENTER'); return; }
      const timeSuffix = m[3] ? '/'+m[3] : '/';
      state.pnr.ticketing = `7TAW${dinfo.day}${dinfo.mon}${timeSuffix} (TICKETING AT WILL - QUEUED ${dinfo.day}${dinfo.mon}${m[3] ? ' '+m[3] : ''})`;
      print(`TICKETING ARRANGEMENT ADDED - 7TAW${dinfo.day}${dinfo.mon}${timeSuffix}`);
      refreshAndPrintPNR();
      return;
    }
    if((m = U.match(/^7TAX(\d{1,2})([A-Z]{3})\/(\d{3,4})$/))){
      const dinfo = parseDate(m[1], m[2]);
      if(!dinfo){ printErr('INVALID DATE - CHECK ENTRY AND REENTER'); return; }
      state.pnr.ticketing = `7TAX${dinfo.day}${dinfo.mon}/${m[3]} (TIME LIMIT - TICKET BY ${dinfo.day}${dinfo.mon} ${m[3]})`;
      print(`TICKETING ARRANGEMENT ADDED - 7TAX${dinfo.day}${dinfo.mon}/${m[3]}`);
      refreshAndPrintPNR();
      return;
    }
    if(U === '*R' || U === '*'){ refreshAndPrintPNR(); return; }
    if((m = U.match(/^\*([A-Z0-9]{6})$/))){ retrieveByLocator(m[1]); return; }
    if(U === 'XI'){ cancelItinerary(); return; }
    if((m = U.match(/^X([\d,\-]+)$/))){
      const nums = [];
      let valid = true;
      for(const part of m[1].split(',')){
        if(part.includes('-')){
          const bounds = part.split('-');
          const a = parseInt(bounds[0],10), b = parseInt(bounds[1],10);
          if(bounds.length !== 2 || !a || !b || a > b){ valid = false; break; }
          for(let i=a;i<=b;i++) nums.push(i);
        } else {
          const v = parseInt(part,10);
          if(!v){ valid = false; break; }
          nums.push(v);
        }
      }
      if(!valid || nums.length === 0){ printErr('INVALID ELEMENT RANGE - CHECK ENTRY AND REENTER'); return; }
      cancelElements(nums);
      return;
    }
    if(U === 'IG'){
      state.pnr = freshPNR();
      state.lastDisplay = [];
      print('IGNORED - PNR NOT SAVED');
      return;
    }
    if(U === 'ER'){ endTransaction('ER'); return; }
    if(U === 'ET'){ endTransaction('ET'); return; }

    printErr('FORMAT - INVALID ENTRY, CHECK ENTRY AND REENTER (TYPE HELP)');
  }

  // ---------- input handling ----------
  inputEl.addEventListener('keydown', (e) => {
    if(e.key === 'Enter'){
      const raw = inputEl.value;
      print('> ' + raw.toUpperCase(), 'echo');
      if(raw.trim().length){
        state.cmdHistory.push(raw);
        state.cmdHistoryIdx = state.cmdHistory.length;
      }
      inputEl.value = '';
      try{ processCommand(raw); } catch(err){ printErr('SYSTEM ERROR - ' + err.message); }
      screenEl.scrollTop = screenEl.scrollHeight;
    } else if(e.key === 'ArrowUp'){
      if(state.cmdHistoryIdx > 0){
        state.cmdHistoryIdx--;
        inputEl.value = state.cmdHistory[state.cmdHistoryIdx] || '';
        setTimeout(()=>inputEl.setSelectionRange(inputEl.value.length, inputEl.value.length));
      }
      e.preventDefault();
    } else if(e.key === 'ArrowDown'){
      if(state.cmdHistoryIdx < state.cmdHistory.length - 1){
        state.cmdHistoryIdx++;
        inputEl.value = state.cmdHistory[state.cmdHistoryIdx] || '';
      } else {
        state.cmdHistoryIdx = state.cmdHistory.length;
        inputEl.value = '';
      }
      e.preventDefault();
    }
  });

  // ---------- toolbar ----------
  document.getElementById('btnClear').addEventListener('click', () => { outputEl.innerHTML = ''; });
  document.getElementById('btnReset').addEventListener('click', () => {
    outputEl.innerHTML = '';
    state.signedIn = false; state.sine = null; state.pcc = null;
    state.lastAvail = null; state.pnr = freshPNR(); state.lastDisplay = [];
    state.history = {}; state.cmdHistory = []; state.cmdHistoryIdx = -1;
    boot();
    inputEl.focus();
  });

  // ---------- settings panel ----------
  const shellEl = document.getElementById('shell');
  const settingsPanel = document.getElementById('settingsPanel');
  const btnSettings = document.getElementById('btnSettings');
  const SETTINGS_KEY = 'sabreSimSettings';
  const DEFAULT_SETTINGS = { theme:'green', scanlines:true, glow:'med', vignette:true, fontSize:'md' };

  function loadSettings(){
    try{
      const raw = localStorage.getItem(SETTINGS_KEY);
      if(raw) return Object.assign({}, DEFAULT_SETTINGS, JSON.parse(raw));
    }catch(e){}
    return Object.assign({}, DEFAULT_SETTINGS);
  }
  function saveSettings(){
    try{ localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings)); }catch(e){}
  }

  const settings = loadSettings();

  function applySettings(){
    shellEl.dataset.theme = settings.theme;
    shellEl.dataset.glow = settings.glow;
    shellEl.dataset.fontsize = settings.fontSize;
    shellEl.classList.toggle('scanlines-off', !settings.scanlines);
    shellEl.classList.toggle('vignette-off', !settings.vignette);
    syncPanelUI();
  }

  function syncPanelUI(){
    settingsPanel.querySelectorAll('.swatch').forEach(b => {
      b.classList.toggle('active', b.dataset.theme === settings.theme);
    });
    settingsPanel.querySelectorAll('.segmented').forEach(seg => {
      const key = seg.dataset.setting;
      seg.querySelectorAll('button').forEach(b => {
        const val = b.dataset.value;
        let active;
        if(key === 'scanlines') active = settings.scanlines === (val === 'on');
        else if(key === 'vignette') active = settings.vignette === (val === 'on');
        else active = settings[key] === val;
        b.classList.toggle('active', active);
      });
    });
  }

  settingsPanel.querySelectorAll('.swatch').forEach(b => {
    b.addEventListener('click', () => {
      settings.theme = b.dataset.theme;
      applySettings(); saveSettings();
    });
  });
  settingsPanel.querySelectorAll('.segmented').forEach(seg => {
    const key = seg.dataset.setting;
    seg.querySelectorAll('button').forEach(b => {
      b.addEventListener('click', () => {
        const val = b.dataset.value;
        if(key === 'scanlines') settings.scanlines = (val === 'on');
        else if(key === 'vignette') settings.vignette = (val === 'on');
        else settings[key] = val;
        applySettings(); saveSettings();
      });
    });
  });

  function positionPanel(){
    const r = btnSettings.getBoundingClientRect();
    const panelW = settingsPanel.offsetWidth || 280;
    let left = r.right - panelW;
    left = Math.max(12, Math.min(left, window.innerWidth - panelW - 12));
    settingsPanel.style.left = left + 'px';
    settingsPanel.style.top = (r.bottom + 8) + 'px';
  }

  btnSettings.addEventListener('click', (e) => {
    e.stopPropagation();
    const isHidden = settingsPanel.classList.contains('hidden');
    if(isHidden){
      settingsPanel.classList.remove('hidden');
      positionPanel();
    } else {
      settingsPanel.classList.add('hidden');
    }
  });
  document.getElementById('btnCloseSettings').addEventListener('click', () => {
    settingsPanel.classList.add('hidden');
  });
  document.addEventListener('click', (e) => {
    if(!settingsPanel.classList.contains('hidden') &&
       !settingsPanel.contains(e.target) && e.target !== btnSettings){
      settingsPanel.classList.add('hidden');
    }
  });
  document.addEventListener('keydown', (e) => {
    if(e.key === 'Escape') settingsPanel.classList.add('hidden');
  });
  window.addEventListener('resize', () => {
    if(!settingsPanel.classList.contains('hidden')) positionPanel();
  });

  applySettings();

})();
