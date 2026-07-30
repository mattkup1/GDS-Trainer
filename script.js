(function(){
  "use strict";

  // ---------- DOM ----------
  const outputEl = document.getElementById('output');
  const screenEl = document.getElementById('screen');
  const inputEl  = document.getElementById('cmdline');
  const crtEl    = document.getElementById('crt');

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
  const CITY_NAMES = {
    DFW:'DALLAS/FT WORTH', ORD:"CHICAGO O'HARE", JFK:'NEW YORK JFK', LAX:'LOS ANGELES',
    ATL:'ATLANTA', SFO:'SAN FRANCISCO', SEA:'SEATTLE/TACOMA', MIA:'MIAMI',
    BOS:'BOSTON LOGAN', DEN:'DENVER', LAS:'LAS VEGAS', PHX:'PHOENIX',
    IAH:'HOUSTON INTERCONTINENTAL', EWR:'NEWARK', MCO:'ORLANDO', CLT:'CHARLOTTE',
    MSP:'MINNEAPOLIS/ST PAUL', DTW:'DETROIT', PHL:'PHILADELPHIA', LGA:'NEW YORK LAGUARDIA',
    BWI:'BALTIMORE/WASHINGTON', SAN:'SAN DIEGO', TPA:'TAMPA', PDX:'PORTLAND',
    STL:'ST LOUIS', HOU:'HOUSTON HOBBY', AUS:'AUSTIN', DCA:'WASHINGTON REAGAN',
    SLC:'SALT LAKE CITY', RDU:'RALEIGH/DURHAM', BNA:'NASHVILLE', SJC:'SAN JOSE',
    OAK:'OAKLAND', FLL:'FT LAUDERDALE', MDW:'CHICAGO MIDWAY', LHR:'LONDON HEATHROW',
    CDG:'PARIS CHARLES DE GAULLE', NRT:'TOKYO NARITA', DXB:'DUBAI', SYD:'SYDNEY'
  };
  const AIRLINES = ['AA','UA','DL','WN','B6','AS','NK','F9'];
  const EQUIP = ['738','73G','320','321','32N','E75','CR9','777','788','319'];
  const CLASSES = ['F','J','C','Y','B','M'];

  function cityName(code){ return CITY_NAMES[code] ? CITY_NAMES[code]+' '+code : 'CITY '+code; }

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
    return { locator:null, names:[], segments:[], phones:[], receivedFrom:null, ticketing:null };
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
    refreshAndPrintPNR();
  }

  function directSell(seats, cls, airline, flightNum, dayStr, monStr, orig, dest, statusCode){
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
    refreshAndPrintPNR();
  }

  function formatSegmentShort(seg){
    return `${seg.airline}${seg.flightNum} ${seg.cls} ${seg.dinfo.day}${seg.dinfo.mon} ${seg.orig}${seg.dest} ${seg.status}${seg.seats}  ${minutesToClock(seg.dep)} ${minutesToClock(seg.arr)}`;
  }

  // ---------- PNR element display / cancel ----------
  function buildElements(){
    const els = [];
    state.pnr.names.forEach((n, i) => els.push({ kind:'name', idx:i, label:`NM${i+1}`, text:n }));
    state.pnr.segments.forEach((s, i) => els.push({ kind:'segment', idx:i, label:`SEG${i+1}`, text: formatSegmentShort(s) + `  ${s.dinfo.weekday}` }));
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

  function cancelElement(n){
    const e = state.lastDisplay.find(x => x.num === n);
    if(!e){ printErr('INVALID ELEMENT NUMBER - REDISPLAY WITH *R'); return; }
    if(e.kind === 'name') state.pnr.names.splice(e.idx, 1);
    else if(e.kind === 'segment') state.pnr.segments.splice(e.idx, 1);
    else if(e.kind === 'phone') state.pnr.phones.splice(e.idx, 1);
    else if(e.kind === 'rf') state.pnr.receivedFrom = null;
    else if(e.kind === 'tk') state.pnr.ticketing = null;
    print(`ELEMENT ${n} CANCELLED`);
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
    if(p.phones.length === 0){ printErr('PNR INCOMPLETE - NEED PHONE FIELD (ENTRY: 9...)'); return; }
    if(!p.receivedFrom){ printErr('PNR INCOMPLETE - NEED RECEIVED FROM (ENTRY: P...)'); return; }
    if(!p.ticketing){ printErr('PNR INCOMPLETE - NEED TICKETING ARRANGEMENT (ENTRY: TAW/ )'); return; }

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
    printBlank();
    print('SELL', 'hd');
    print('  0{LN}{CLASS}{SEATS}    Sell from avail line   e.g. 04Y1');
    print('  SS{SEATS}{CLASS} {AL}{FLT} {DD}{MMM}{ORG}{DST}{STATUS}');
    print('                         Direct sell   e.g. SS1Y AA100 15AUGDFWORDNN');
    printBlank();
    print('PNR BUILD', 'hd');
    print('  -{SURNAME}/{GIVEN} {TITLE}   Name field   e.g. -SMITH/JOHN MR');
    print('  9{PHONE}                     Phone field  e.g. 9DFW555-1234-A');
    print('  P{TEXT}                      Received from  e.g. PJSMITH');
    print('  TAW/                         Ticketing: will call');
    print('  TAU{DD}{MMM}/{HHMM}          Ticketing by date/time  e.g. TAU16AUG/1800');
    printBlank();
    print('PNR MANAGEMENT', 'hd');
    print('  *R  or  *          Display current PNR');
    print('  *{LOCATOR}         Retrieve PNR by record locator');
    print('  X{N}               Cancel numbered element N');
    print('  IG                 Ignore PNR (discard unsaved work)');
    print('  ER                 End transaction, redisplay');
    print('  ET                 End transaction, clear work area');
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
    if((m = U.match(/^0(\d{1,2})([A-Z])(\d{1,2})$/))){
      sellFromAvail(parseInt(m[1],10), m[2], parseInt(m[3],10)); return;
    }
    if((m = U.match(/^SS(\d{1,2})([A-Z])\s+([A-Z]{2})(\d{1,4})\s+(\d{1,2})([A-Z]{3})([A-Z]{3})([A-Z]{3})([A-Z]{2})$/))){
      directSell(parseInt(m[1],10), m[2], m[3], m[4], m[5], m[6], m[7], m[8], m[9]); return;
    }
    if(U.startsWith('-')){
      const text = cmd.slice(1).trim();
      if(!text.includes('/')){ printErr('FORMAT - NAME MUST BE SURNAME/GIVEN NAME'); return; }
      state.pnr.names.push(text.toUpperCase());
      print(`NAME ADDED - ${text.toUpperCase()}`);
      refreshAndPrintPNR();
      return;
    }
    if(U.startsWith('9')){
      const text = cmd.slice(1).trim();
      if(!text){ printErr('FORMAT - PHONE FIELD REQUIRED'); return; }
      state.pnr.phones.push(text.toUpperCase());
      print(`PHONE ADDED - ${text.toUpperCase()}`);
      refreshAndPrintPNR();
      return;
    }
    if(U.startsWith('P') && U !== 'P'){
      const text = cmd.slice(1).trim();
      if(!text){ printErr('FORMAT - RECEIVED FROM TEXT REQUIRED'); return; }
      state.pnr.receivedFrom = text.toUpperCase();
      print(`RECEIVED FROM ADDED - ${text.toUpperCase()}`);
      refreshAndPrintPNR();
      return;
    }
    if(U === 'TAW/' || U === 'TAW'){
      state.pnr.ticketing = 'TAW/ (TICKET ON OR BEFORE DEPARTURE - WILL CALL)';
      print('TICKETING ARRANGEMENT ADDED - TAW/');
      refreshAndPrintPNR();
      return;
    }
    if((m = U.match(/^TAU(\d{1,2})([A-Z]{3})\/(\d{3,4})$/))){
      const dinfo = parseDate(m[1], m[2]);
      if(!dinfo){ printErr('INVALID DATE - CHECK ENTRY AND REENTER'); return; }
      state.pnr.ticketing = `TAU${dinfo.day}${dinfo.mon}/${m[3]} (TICKET BY ${dinfo.day}${dinfo.mon} ${m[3]})`;
      print(`TICKETING ARRANGEMENT ADDED - TAU${dinfo.day}${dinfo.mon}/${m[3]}`);
      refreshAndPrintPNR();
      return;
    }
    if(U === '*R' || U === '*'){ refreshAndPrintPNR(); return; }
    if((m = U.match(/^\*([A-Z0-9]{6})$/))){ retrieveByLocator(m[1]); return; }
    if((m = U.match(/^X(\d{1,2})$/))){ cancelElement(parseInt(m[1],10)); return; }
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
  const btnAmberEl = document.getElementById('btnAmber');
  btnAmberEl.addEventListener('click', () => {
    crtEl.classList.toggle('amber');
    btnAmberEl.classList.toggle('active', crtEl.classList.contains('amber'));
  });
  document.getElementById('btnClear').addEventListener('click', () => { outputEl.innerHTML = ''; });
  document.getElementById('btnReset').addEventListener('click', () => {
    outputEl.innerHTML = '';
    state.signedIn = false; state.sine = null; state.pcc = null;
    state.lastAvail = null; state.pnr = freshPNR(); state.lastDisplay = [];
    state.history = {}; state.cmdHistory = []; state.cmdHistoryIdx = -1;
    boot();
    inputEl.focus();
  });

})();
