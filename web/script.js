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
  // Sourced from REFERENCE_DATA (spec/reference-data.json via reference-data.js) so the web
  // and CLI editions share one spec - see spec/README.md. Local names kept as-is to avoid
  // touching everywhere they're used below.
  const MONTHS = REFERENCE_DATA.months;
  const WEEKDAYS = REFERENCE_DATA.weekdays;
  const AIRLINES = REFERENCE_DATA.airlines;
  const AIRLINE_NUMERIC_CODES = REFERENCE_DATA.airlineNumericCodes;
  const EQUIP = REFERENCE_DATA.equipment;
  const CLASSES = REFERENCE_DATA.classes;
  const CLASS_FARE_MULT = REFERENCE_DATA.classFareMultipliers;
  const TAX_POOL = REFERENCE_DATA.taxPool;
  const FARE_FORMULA = REFERENCE_DATA.fareFormula;
  const SSR_CODES = REFERENCE_DATA.ssrCodes;
  const CARD_TYPES = REFERENCE_DATA.cardTypes;
  const PHONE_LOC_CODES = REFERENCE_DATA.phoneLocationCodes;
  const DOCUMENT_TYPES = REFERENCE_DATA.documentTypes;
  const LOYALTY_TIERS = REFERENCE_DATA.loyaltyTiers;
  const FARE_RULES = REFERENCE_DATA.fareRules;
  const CORPORATE_CODES = REFERENCE_DATA.corporateCodes;

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
    return { locator:null, names:[], segments:[], phones:[], receivedFrom:null, ticketing:null, pricing:null,
              infants:[], ssrs:[], osis:[], seats:[], formOfPayment:null, activityLog:[], tickets:[],
              docs:[], remarks:[] };
  }

  function nowStamp(){
    const now = new Date();
    return `${pad(now.getDate(),2).trim()}${MONTHS[now.getMonth()]}/${String(now.getHours()).padStart(2,'0')}${String(now.getMinutes()).padStart(2,'0')}`;
  }
  function logActivity(text){
    state.pnr.activityLog.push({ stamp: nowStamp(), sine: state.sine || '----', text });
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

    // A class at exactly 0 remaining sells as a waitlist request (HL) instead of being
    // blocked outright - matches how a real GDS lets you request a closed class. Partial
    // shortfalls (some seats left, just not enough for this request) still hard-block below,
    // to keep the "how many can I actually get right now" signal meaningful.
    if(cinfo.seats === 0){
      const seg = {
        airline: f.airline, flightNum: f.flightNum, cls: cls.toUpperCase(), seats,
        dinfo: state.lastAvail.dinfo, orig: state.lastAvail.orig, dest: state.lastAvail.dest,
        dep: f.dep, arr: f.arr, status: 'HL', equip: f.equip
      };
      state.pnr.segments.push(seg);
      print(`SEGMENT WAITLISTED - ${formatSegmentShort(seg)}`);
      logActivity(`SEGMENT WAITLISTED - ${formatSegmentShort(seg)}`);
      invalidatePricing();
      refreshAndPrintPNR();
      return;
    }
    if(seats > cinfo.seats){ printErr(`UNABLE - ONLY ${cinfo.seats} SEAT(S) AVAILABLE IN CLASS ${cls.toUpperCase()}`); return; }

    const seg = {
      airline: f.airline, flightNum: f.flightNum, cls: cls.toUpperCase(), seats,
      dinfo: state.lastAvail.dinfo, orig: state.lastAvail.orig, dest: state.lastAvail.dest,
      dep: f.dep, arr: f.arr, status: 'HK', equip: f.equip
    };
    state.pnr.segments.push(seg);
    cinfo.seats -= seats;
    print(`SEGMENT SOLD - ${formatSegmentShort(seg)}`);
    logActivity(`SEGMENT SOLD - ${formatSegmentShort(seg)}`);
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
    const equip = EQUIP[Math.floor(rng()*EQUIP.length)];
    const seg = {
      airline: airline.toUpperCase(), flightNum: parseInt(flightNum,10), cls: cls.toUpperCase(), seats,
      dinfo, orig, dest, dep, arr, status: (statusCode||'HK').toUpperCase(), equip
    };
    state.pnr.segments.push(seg);
    print(`SEGMENT SOLD - ${formatSegmentShort(seg)}`);
    logActivity(`SEGMENT SOLD - ${formatSegmentShort(seg)}`);
    invalidatePricing();
    refreshAndPrintPNR();
  }

  function invalidatePricing(){
    if(state.pnr.pricing){
      state.pnr.pricing = null;
      print('FARE QUOTE INVALIDATED - ITINERARY CHANGED, RE-PRICE WITH WP', 'dim');
      logActivity('FARE QUOTE INVALIDATED - ITINERARY CHANGED');
    }
    if(state.pnr.tickets.length){
      state.pnr.tickets = [];
      print('TICKETS VOIDED - ITINERARY CHANGED, REISSUE WITH TKTT AFTER RE-PRICING', 'dim');
      logActivity('TICKETS VOIDED - ITINERARY CHANGED');
    }
  }

  function formatSegmentShort(seg){
    return `${seg.airline}${seg.flightNum} ${seg.cls} ${seg.dinfo.day}${seg.dinfo.mon} ${seg.orig}${seg.dest} ${seg.status}${seg.seats}  ${minutesToClock(seg.dep)} ${minutesToClock(seg.arr)}`;
  }

  // ---------- pricing (WP / WPNCS) ----------
  function tripType(segments){
    if(segments.length === 1) return 'OW';
    const first = segments[0], last = segments[segments.length-1];
    if(segments.length === 2 && first.orig === last.dest && first.dest === last.orig) return 'RT';
    if(first.orig === last.dest) return 'CT';
    return 'OJ';
  }

  function priceItinerary(mode, corpCode){
    const p = state.pnr;
    if(p.segments.length === 0){ printErr('UNABLE TO PRICE - NO ITINERARY SEGMENTS'); return; }
    if(p.names.length === 0){ printErr('UNABLE TO PRICE - NAME FIELD REQUIRED PRIOR TO PRICING'); return; }
    let corporate = null;
    if(corpCode){
      corporate = CORPORATE_CODES[corpCode];
      if(!corporate){ printErr(`UNKNOWN CORPORATE CODE ${corpCode} - VALID: ${Object.keys(CORPORATE_CODES).join(' ')}`); return; }
    }

    const seed = hashStr(p.segments.map(s => `${s.airline}${s.flightNum}${s.cls}${s.dinfo.day}${s.dinfo.mon}${s.orig}${s.dest}${s.seats}`).join('|') + mode);
    const rng = mulberry32(seed);

    let baseFare = 0;
    for(const s of p.segments){
      const mult = CLASS_FARE_MULT[s.cls] || 1.4;
      const dist = FARE_FORMULA.distanceMin + Math.floor(rng()*FARE_FORMULA.distanceRange);
      baseFare += Math.round((FARE_FORMULA.baseFareCoefficient + dist*FARE_FORMULA.baseFarePerMile) * mult * s.seats);
    }
    if(corporate){ baseFare = Math.round(baseFare * (1 - corporate.discount)); }

    const numTaxes = FARE_FORMULA.minTaxes + Math.floor(rng()*FARE_FORMULA.additionalTaxesRange);
    const pool = TAX_POOL.slice().sort(() => rng()-0.5).slice(0, numTaxes);
    const taxes = [];
    let taxTotal = 0;
    for(const t of pool){
      const amt = Math.round((FARE_FORMULA.taxAmountMin + rng()*FARE_FORMULA.taxAmountRange) * 100)/100;
      taxes.push({ code:t.code, label:t.label, amount:amt });
      taxTotal += amt;
    }
    taxTotal = Math.round(taxTotal*100)/100;
    const total = Math.round((baseFare + taxTotal)*100)/100;
    const fareBasis = `${p.segments[0].cls}${tripType(p.segments)}`;
    const rules = FARE_RULES[p.segments[0].cls] || null;

    p.pricing = {
      mode, baseFare, taxes, taxTotal, total, fareBasis, currency:'USD', rules,
      corporateCode: corporate ? { code: corpCode, label: corporate.label, discount: corporate.discount } : null,
    };

    print(mode === 'WPNCS' ? '** LOWEST FARE - WPNCS (SUBJECT TO AVAILABILITY) **' : '** ITINERARY PRICING - WP **', 'hd');
    p.segments.forEach((s,i) => print(`  ${i+1}  ${formatSegmentShort(s)}`, 'dim'));
    printBlank();
    print(`FARE BASIS: ${fareBasis}`);
    if(corporate){ print(`CORPORATE CODE APPLIED - ${corporate.label} (${Math.round(corporate.discount*100)}% DISCOUNT)`, 'dim'); }
    print(`BASE FARE      USD ${baseFare.toFixed(2)}`);
    for(const t of taxes){ print(`  ${t.code}   USD ${t.amount.toFixed(2)}   ${t.label}`, 'dim'); }
    print(`TAXES/FEES     USD ${taxTotal.toFixed(2)}`);
    print(`TOTAL          USD ${total.toFixed(2)}`, 'hd');
    if(rules){
      printBlank();
      print('FARE RULES', 'dim');
      print(`  CHANGE FEE                  USD ${rules.changeFee.toFixed(2)}`, 'dim');
      print(`  REFUNDABLE                  ${rules.refundable ? 'YES' : 'NO'}`, 'dim');
      print(`  ADVANCE PURCHASE REQUIRED   ${rules.advancePurchaseDays} DAYS`, 'dim');
    }
    printBlank();
    print('FARE QUOTE STORED - REQUIRED PRIOR TO TICKETING', 'dim');
    logActivity(`PRICED - ${formatPricingShort(p.pricing)}`);
    refreshAndPrintPNR();
  }

  function formatPricingShort(pr){
    return `${pr.mode}  ${pr.fareBasis}  BASE USD${pr.baseFare.toFixed(2)}  TAX USD${pr.taxTotal.toFixed(2)}  TTL USD${pr.total.toFixed(2)}`;
  }

  // ---------- special service requests / other service info ----------

  // ---------- seat maps ----------
  function getSeatMap(seg){
    const seed = hashStr(`${seg.airline}${seg.flightNum}${seg.dinfo.day}${seg.dinfo.mon}${seg.orig}${seg.dest}SEATMAP`);
    const rng = mulberry32(seed);
    const rows = [];
    const occupied = new Set();
    for(let r=1; r<=30; r++){
      const seats = 'ABCDEF'.split('').map(col => {
        const occ = rng() < 0.4;
        if(occ) occupied.add(`${r}${col}`);
        return occ;
      });
      rows.push({ num:r, seats });
    }
    return { rows, occupied };
  }

  function showSeatMap(n){
    const seg = state.pnr.segments[n-1];
    if(!seg){ printErr('INVALID SEGMENT NUMBER - CHECK ITINERARY'); return; }
    const map = getSeatMap(seg);
    const mine = new Set(state.pnr.seats.filter(s => s.segIdx === n-1).map(s => s.seat));
    print(`SEAT MAP - ${seg.airline}${seg.flightNum}  ${seg.equip || ''}  ${seg.dinfo.day}${seg.dinfo.mon}  ${seg.orig}-${seg.dest}`, 'hd');
    printBlank();
    print('      A  B  C     D  E  F', 'dim');
    for(const row of map.rows){
      const cols = row.seats.map((occ, i) => {
        const seatId = `${row.num}${'ABCDEF'[i]}`;
        return mine.has(seatId) ? ' * ' : (occ ? ' X ' : ' . ');
      });
      print(` ${pad(row.num,3)}  ${cols.slice(0,3).join('')}   ${cols.slice(3).join('')}`);
    }
    printBlank();
    print('. OPEN   X OCCUPIED   * YOUR ASSIGNMENT', 'dim');
    print(`ASSIGN WITH: 4${n}-{SEAT}   e.g. 4${n}-14A`, 'dim');
  }

  function assignSeat(n, seatStr){
    const seg = state.pnr.segments[n-1];
    if(!seg){ printErr('INVALID SEGMENT NUMBER - CHECK ITINERARY'); return; }
    const rowMatch = seatStr.match(/^(\d{1,2})([A-F])$/);
    const row = parseInt(rowMatch[1],10);
    if(row < 1 || row > 30){ printErr('INVALID SEAT ROW - VALID RANGE 1-30'); return; }
    const map = getSeatMap(seg);
    if(map.occupied.has(seatStr)){ printErr(`SEAT ${seatStr} NOT AVAILABLE - SELECT ANOTHER (SEE SEAT MAP: 4${n})`); return; }
    if(state.pnr.seats.some(s => s.segIdx === n-1 && s.seat === seatStr)){ printErr(`SEAT ${seatStr} ALREADY ASSIGNED ON THIS SEGMENT`); return; }
    state.pnr.seats.push({ segIdx: n-1, seat: seatStr });
    print(`SEAT ASSIGNED - SEG${n} ${seatStr}`);
    logActivity(`SEAT ASSIGNED - SEG${n} ${seatStr}`);
    refreshAndPrintPNR();
  }

  // ---------- form of payment ----------
  function maskCard(num){
    return 'X'.repeat(Math.max(0, num.length-4)) + num.slice(-4);
  }

  // ---------- PNR element display / cancel ----------
  function buildElements(){
    const els = [];
    state.pnr.names.forEach((n, i) => els.push({ kind:'name', idx:i, label:`NM${i+1}`, text:n }));
    state.pnr.infants.forEach((inf, i) => els.push({ kind:'infant', idx:i, label:'IN', text:`${inf.surname}/${inf.given}  DOB ${inf.dob}  (INFANT - TRAVELS WITH ${inf.adult})` }));
    state.pnr.docs.forEach((d, i) => els.push({ kind:'docs', idx:i, label:'DOC', text:`${d.desc} ${d.country} ${d.number}  NATIONALITY ${d.nationality}  DOB ${d.dob}  ${d.sex}  EXP ${d.expiry}  PAX ${d.pax} (${state.pnr.names[d.pax-1] || '?'})` }));
    state.pnr.segments.forEach((s, i) => els.push({ kind:'segment', idx:i, label:`SEG${i+1}`, text: formatSegmentShort(s) + `  ${s.dinfo.weekday}` }));
    state.pnr.seats.forEach((st, i) => els.push({ kind:'seat', idx:i, label:'SEAT', text:`SEG${st.segIdx+1} - SEAT ${st.seat}` }));
    state.pnr.ssrs.forEach((r, i) => els.push({ kind:'ssr', idx:i, label:'SSR', text: r.text }));
    state.pnr.osis.forEach((o, i) => els.push({ kind:'osi', idx:i, label:'OSI', text: o.text }));
    state.pnr.remarks.forEach((r, i) => els.push({ kind:'remark', idx:i, label:'RM', text: r }));
    if(state.pnr.pricing) els.push({ kind:'fq', idx:0, label:'FQ', text: formatPricingShort(state.pnr.pricing) });
    state.pnr.phones.forEach((p, i) => els.push({ kind:'phone', idx:i, label:'CTC', text:p }));
    if(state.pnr.receivedFrom) els.push({ kind:'rf', idx:0, label:'RF', text: state.pnr.receivedFrom });
    if(state.pnr.formOfPayment) els.push({ kind:'fp', idx:0, label:'FP', text: state.pnr.formOfPayment.display });
    if(state.pnr.ticketing) els.push({ kind:'tk', idx:0, label:'TK', text: state.pnr.ticketing });
    state.pnr.tickets.forEach((t, i) => els.push({ kind:'tkt', idx:i, label:'TKT', text: `${t.passenger}${t.isInfant ? ' (INF)' : ''}  ${t.ticketNum}` }));
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
    else if(e.kind === 'infant') state.pnr.infants.splice(e.idx, 1);
    else if(e.kind === 'docs') state.pnr.docs.splice(e.idx, 1);
    else if(e.kind === 'remark') state.pnr.remarks.splice(e.idx, 1);
    else if(e.kind === 'segment'){
      state.pnr.segments.splice(e.idx, 1);
      state.pnr.pricing = null;
      state.pnr.tickets = [];
      state.pnr.seats = state.pnr.seats
        .filter(st => st.segIdx !== e.idx)
        .map(st => st.segIdx > e.idx ? { segIdx: st.segIdx - 1, seat: st.seat } : st);
    }
    else if(e.kind === 'seat') state.pnr.seats.splice(e.idx, 1);
    else if(e.kind === 'ssr') state.pnr.ssrs.splice(e.idx, 1);
    else if(e.kind === 'osi') state.pnr.osis.splice(e.idx, 1);
    else if(e.kind === 'fq'){ state.pnr.pricing = null; state.pnr.tickets = []; }
    else if(e.kind === 'phone') state.pnr.phones.splice(e.idx, 1);
    else if(e.kind === 'rf') state.pnr.receivedFrom = null;
    else if(e.kind === 'fp') state.pnr.formOfPayment = null;
    else if(e.kind === 'tk') state.pnr.ticketing = null;
    else if(e.kind === 'tkt') state.pnr.tickets.splice(e.idx, 1);
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
    logActivity(`ELEMENT${cancelled.length > 1 ? 'S' : ''} ${cancelled.join(',')} CANCELLED`);
    refreshAndPrintPNR();
  }

  function cancelItinerary(){
    if(state.pnr.segments.length === 0){ printErr('NO ITINERARY SEGMENTS TO CANCEL'); return; }
    state.pnr.segments = [];
    state.pnr.pricing = null;
    state.pnr.tickets = [];
    state.pnr.seats = [];
    print('ITINERARY CANCELLED');
    logActivity('ITINERARY CANCELLED');
    refreshAndPrintPNR();
  }

  // ---------- PNR completeness (shared spec: PNR_COMPLETENESS) ----------
  const PNR_FIELD_ACCESSORS = {
    segments: () => state.pnr.segments,
    names: () => state.pnr.names,
    pricing: () => state.pnr.pricing,
    phones: () => state.pnr.phones,
    received_from: () => state.pnr.receivedFrom,
    form_of_payment: () => state.pnr.formOfPayment,
    ticketing: () => state.pnr.ticketing,
    tickets: () => state.pnr.tickets,
    locator: () => state.pnr.locator,
  };

  function completenessCheckPasses(kind, value){
    if(kind === 'non_empty') return Array.isArray(value) && value.length > 0;
    if(kind === 'present') return value !== null && value !== undefined;
    if(kind === 'empty') return Array.isArray(value) && value.length === 0;
    return true;
  }

  function firstIncompleteMessage(ruleKey){
    const rules = PNR_COMPLETENESS[ruleKey] || [];
    for(const rule of rules){
      const value = PNR_FIELD_ACCESSORS[rule.field]();
      if(!completenessCheckPasses(rule.check, value)) return rule.message;
    }
    return null;
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
    const incomplete = firstIncompleteMessage('end_transaction');
    if(incomplete){ printErr(incomplete); return; }

    if(!p.locator) p.locator = genLocator();
    logActivity(`PNR SAVED (${mode}) - RLOC ${p.locator}`);
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
    logActivity(`PNR RETRIEVED - RLOC ${loc}`);
    refreshAndPrintPNR();
  }

  // ---------- ticketing (TKTT) ----------
  function genTicketNumber(locator, identifier){
    const seed = hashStr(`${locator}${identifier}TKT`);
    const rng = mulberry32(seed);
    const serial = String(Math.floor(rng()*10000000000)).padStart(10,'0');
    return serial;
  }

  function issueTickets(){
    const p = state.pnr;
    const incomplete = firstIncompleteMessage('issue_tickets');
    if(incomplete){ printErr(incomplete); return; }

    const validatingCarrier = p.segments[0].airline;
    const numericCode = AIRLINE_NUMERIC_CODES[validatingCarrier] || '000';

    for(const name of p.names){
      const serial = genTicketNumber(p.locator, name);
      p.tickets.push({ passenger: name, ticketNum: `${numericCode}-${serial}`, isInfant:false });
    }
    for(const inf of p.infants){
      const identifier = `${inf.surname}/${inf.given}`;
      const serial = genTicketNumber(p.locator, identifier);
      p.tickets.push({ passenger: identifier, ticketNum: `${numericCode}-${serial}`, isInfant:true });
    }

    print('** ELECTRONIC TICKET ISSUED **', 'hd');
    for(const t of p.tickets){
      print(`  ${pad(t.passenger + (t.isInfant ? ' (INF)' : ''), 28)} ${t.ticketNum}`);
    }
    print(`VALIDATING CARRIER: ${validatingCarrier}   FORM OF PAYMENT: ${p.formOfPayment.display}`, 'dim');
    logActivity(`TICKETED - ${p.tickets.length} TICKET(S) ISSUED, VALIDATING CARRIER ${validatingCarrier}`);
    refreshAndPrintPNR();
  }

  function showHistory(){
    const log = state.pnr.activityLog || [];
    if(log.length === 0){ print('NO HISTORY AVAILABLE FOR THIS PNR', 'dim'); return; }
    print(`PNR ACTIVITY HISTORY${state.pnr.locator ? '  RLOC: '+state.pnr.locator : ''}`, 'hd');
    printBlank();
    for(const entry of log){
      print(` ${entry.stamp}  ${pad(entry.sine,6)} ${entry.text}`);
    }
  }

  // ---------- help ----------
  function showHelp(){
    print('GDS TRAINER ENTRY REFERENCE', 'hd');
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
    print('  A class at 0 remaining sells as a waitlist request (status HL) instead of', 'dim');
    print('  being blocked - a real seat count still short-blocks as before.', 'dim');
    printBlank();
    print('PNR BUILD', 'hd');
    print('  -{SURNAME}/{GIVEN} {TITLE}          Name field   e.g. -SMITH/JOHN MR');
    print('  -{N}{SURNAME}/{G1} {T1}/{G2} {T2}   Multiple passengers, same surname');
    print('                                       e.g. -2SMITH/JOHN MR/JANE MRS');
    print('  -{SURNAME}/{GIVEN} {TITLE}(INF{ISURNAME}/{IGIVEN}/{DOB})');
    print('                                       Name with an associated lap infant');
    print('                                       e.g. -SMITH/JOHN MR(INFSMITH/BABY/12JAN26)');
    print('  9{NUMBER}-{LOC}                     Phone field   e.g. 9214555-1234-A');
    print('  9/{CTY}{NUMBER}-{LOC}               Phone field, out-of-area   e.g. 9/BOS617-555-1234-A');
    print('  6{TEXT}                             Received from   e.g. 6JSMITH');
    print('  5{TEXT}                             General remark (agency-internal, not sent to the carrier)   e.g. 5VIP - HANDLE WITH CARE');
    print('  WP[/{CORPCODE}]                     Price itinerary (required before ticketing)   e.g. WP or WP/ACME01');
    print('  WPNCS[/{CORPCODE}]                  Price - lowest fare regardless of availability');
    print('  7TAW/                               Ticketing: at will (ticket on/before departure)');
    print('  7TAW{DD}{MMM}/{HHMM}                Ticketing at will, queued to date/time');
    print('  7TAX{DD}{MMM}/{HHMM}                Ticketing time limit   e.g. 7TAX16AUG/1800');
    print('  FPCASH  /  FPCHECK                  Form of payment - cash / check');
    print('  FPCC{TYPE}{CARDNUM}/{MMYY}          Form of payment - credit card   e.g. FPCCVI4111111111111111/1225');
    print('                                       Card types: VI CA AX DC DS JC');
    printBlank();
    print('TICKETING', 'hd');
    print('  TKTT     Issue ticket(s) - requires a saved PNR (ER/ET) with fare quote,');
    print('           ticketing arrangement, and form of payment already on file.');
    print('           Distinct from the ticketing ARRANGEMENT above: TAW/TAX just sets');
    print('           a deadline, TKTT actually issues ticket numbers. Changing the');
    print('           itinerary after ticketing voids the ticket(s) - reissue with WP then TKTT.');
    printBlank();
    print('SPECIAL SERVICE / OTHER SERVICE INFO', 'hd');
    print('  3{SSRCODE}[-{PAX#}][/{TEXT}]   Special service request   e.g. 3VGML  or  3WCHR-1/AISLE SEAT');
    print('  3OSI{AL}{TEXT}                 Other service info   e.g. 3OSIAA VIP PASSENGER');
    print('  3FQTV{AL}{NUMBER}[/{TIER}]     Frequent flyer number, optional tier   e.g. 3FQTVAA1234567 or 3FQTVAA1234567/GLD');
    print('                                  Tiers: SLV GLD PLT DIA', 'dim');
    print('  SSR codes: WCHR WCHS WCHC VGML BBML CHML KSML MOML DBML BLND DEAF UMNR PETC BSCT SPML XBAG', 'dim');
    printBlank();
    print('PASSENGER DOCUMENTS (APIS)', 'hd');
    print('  3DOCS{TYPE}/{COUNTRY}/{NUMBER}/{NATIONALITY}/{DOB}/{SEX}/{EXPIRY}-{PAX#}');
    print('    e.g. 3DOCSP/US/123456789/US/12JAN90/M/25DEC30-1', 'dim');
    print('    TYPE: P (passport). DOB/EXPIRY: DDMONYY. SEX: M or F.', 'dim');
    printBlank();
    print('SEATS', 'hd');
    print('  4{N}            Display seat map for itinerary segment N   e.g. 41');
    print('  4{N}-{SEAT}     Assign a seat on segment N   e.g. 41-14A');
    printBlank();
    print('ENCODE / DECODE', 'hd');
    print('  DC{CODE}        Decode a 3-letter airport/city code   e.g. DCORD');
    print('  DAN{TEXT}       Search airports/cities by name   e.g. DANCHICAGO');
    printBlank();
    print('PNR MANAGEMENT', 'hd');
    print('  *R  or  *              Display current PNR');
    print('  *H                     Display PNR activity history (chronological log)');
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
    print('GDS TRAINER - SIGN IN COMPLETE', 'hd');
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
    print('G*D*S*  T*R*A*I*N*E*R*  -----------------------------------------------', 'hd');
    print('                        GLOBAL DISTRIBUTION SYSTEM - TERMINAL EMULATION');
    print('                        -----------------------------------------------');
    printBlank();
    print('NOT SIGNED IN', 'dim');
    print('TYPE SI TO SIGN IN   ·   HELP FOR COMMAND REFERENCE', 'dim');
  }
  boot();

  // ---------- command handlers (dispatched via COMMAND_GRAMMAR, see spec/README.md) ----------
  function handleName(u){
    let workingText = u.slice(1).trim();
    const infMatch = workingText.match(/\(INF([A-Z][A-Z\-' ]*)\/([A-Z][A-Z\-' ]*)\/(\d{1,2}[A-Z]{3}\d{2})\)\s*$/);
    let infantData = null;
    if(infMatch){
      infantData = { surname: infMatch[1].trim(), given: infMatch[2].trim(), dob: infMatch[3] };
      workingText = workingText.slice(0, infMatch.index).trim();
    }
    if(!workingText.includes('/')){ printErr('FORMAT - NAME MUST BE SURNAME/GIVEN NAME'); return; }
    const parts = workingText.split('/').map(s => s.trim()).filter(s => s.length);
    const headMatch = parts.length >= 2 ? parts[0].match(/^(\d{1,2})?([A-Z][A-Z\-' ]*)$/) : null;
    if(!headMatch){ printErr('FORMAT - NAME MUST BE SURNAME/GIVEN NAME'); return; }
    const surname = headMatch[2];
    const incoming = parts.slice(1);
    const maxParty = state.pnr.segments.length ? Math.min(...state.pnr.segments.map(s => s.seats)) : null;
    if(maxParty !== null && state.pnr.names.length + incoming.length > maxParty){
      printErr(`UNABLE TO ADD NAME - PARTY SIZE EXCEEDS SEATS SOLD (${maxParty}) - SELL ADDITIONAL SEATS OR CANCEL A NAME`);
      return;
    }
    const added = [];
    for(const g of incoming){
      const full = `${surname}/${g}`;
      state.pnr.names.push(full);
      added.push(full);
    }
    print(`NAME${added.length > 1 ? 'S' : ''} ADDED - ${added.join('  ')}`);
    logActivity(`NAME${added.length > 1 ? 'S' : ''} ADDED - ${added.join('  ')}`);
    if(infantData){
      const dv = infantData.dob.match(/^(\d{1,2})([A-Z]{3})(\d{2})$/);
      const day = dv ? parseInt(dv[1],10) : 0;
      if(!dv || MONTHS.indexOf(dv[2]) < 0 || day < 1 || day > 31){
        printErr('FORMAT - INVALID INFANT DOB, USE DDMONYY e.g. 12JAN26');
      } else {
        const adultRef = added[added.length-1];
        state.pnr.infants.push({ adult: adultRef, surname: infantData.surname, given: infantData.given, dob: infantData.dob });
        print(`INFANT ADDED - ${infantData.surname}/${infantData.given}  DOB ${infantData.dob}  (TRAVELS WITH ${adultRef})`);
        logActivity(`INFANT ADDED - ${infantData.surname}/${infantData.given}  DOB ${infantData.dob}`);
      }
    }
    refreshAndPrintPNR();
  }

  function handlePhone(u){
    const text = u.slice(1).trim();
    const pm = text.match(/^(?:\/([A-Z]{3}))?(\d[\d\-]{4,14})-([A-Z]{1,3})$/);
    if(!pm || !PHONE_LOC_CODES.includes(pm[3].toUpperCase())){
      printErr('FORMAT - PHONE MUST BE 9NUMBER-LOC or 9/CTYNUMBER-LOC  e.g. 9214555-1234-A or 9/DFW555-1234-A'); return;
    }
    const formatted = `${pm[1] ? '/'+pm[1].toUpperCase() : ''}${pm[2]}-${pm[3].toUpperCase()}`;
    state.pnr.phones.push(formatted);
    print(`PHONE ADDED - 9${formatted}`);
    logActivity(`PHONE ADDED - 9${formatted}`);
    refreshAndPrintPNR();
  }

  function handleReceivedFrom(u){
    const text = u.slice(1).trim();
    if(!text){ printErr('FORMAT - RECEIVED FROM TEXT REQUIRED'); return; }
    state.pnr.receivedFrom = text;
    print(`RECEIVED FROM ADDED - ${text}`);
    logActivity(`RECEIVED FROM ADDED - ${text}`);
    refreshAndPrintPNR();
  }

  function addTicketingAtWill(){
    state.pnr.ticketing = '7TAW/ (TICKETING AT WILL - TICKET ON OR BEFORE DEPARTURE)';
    print('TICKETING ARRANGEMENT ADDED - 7TAW/');
    logActivity('TICKETING ARRANGEMENT ADDED - 7TAW/');
    refreshAndPrintPNR();
  }

  function addTicketingAtWillDated(day, mon, time){
    const dinfo = parseDate(day, mon);
    if(!dinfo){ printErr('INVALID DATE - CHECK ENTRY AND REENTER'); return; }
    const timeSuffix = time ? '/'+time : '/';
    state.pnr.ticketing = `7TAW${dinfo.day}${dinfo.mon}${timeSuffix} (TICKETING AT WILL - QUEUED ${dinfo.day}${dinfo.mon}${time ? ' '+time : ''})`;
    print(`TICKETING ARRANGEMENT ADDED - 7TAW${dinfo.day}${dinfo.mon}${timeSuffix}`);
    logActivity(`TICKETING ARRANGEMENT ADDED - 7TAW${dinfo.day}${dinfo.mon}${timeSuffix}`);
    refreshAndPrintPNR();
  }

  function addTicketingTimeLimit(day, mon, time){
    const dinfo = parseDate(day, mon);
    if(!dinfo){ printErr('INVALID DATE - CHECK ENTRY AND REENTER'); return; }
    state.pnr.ticketing = `7TAX${dinfo.day}${dinfo.mon}/${time} (TIME LIMIT - TICKET BY ${dinfo.day}${dinfo.mon} ${time})`;
    print(`TICKETING ARRANGEMENT ADDED - 7TAX${dinfo.day}${dinfo.mon}/${time}`);
    logActivity(`TICKETING ARRANGEMENT ADDED - 7TAX${dinfo.day}${dinfo.mon}/${time}`);
    refreshAndPrintPNR();
  }

  function addFopCash(){
    state.pnr.formOfPayment = { type:'CASH', display:'CASH' };
    print('FORM OF PAYMENT ADDED - CASH');
    logActivity('FORM OF PAYMENT ADDED - CASH');
    refreshAndPrintPNR();
  }

  function addFopCheck(){
    state.pnr.formOfPayment = { type:'CHECK', display:'CHECK' };
    print('FORM OF PAYMENT ADDED - CHECK');
    logActivity('FORM OF PAYMENT ADDED - CHECK');
    refreshAndPrintPNR();
  }

  function addFopCreditCard(type, num, mmStr, yy){
    const mm = parseInt(mmStr,10);
    if(!CARD_TYPES[type]){ printErr(`UNKNOWN CARD TYPE ${type} - VALID: ${Object.keys(CARD_TYPES).join(' ')}`); return; }
    if(mm < 1 || mm > 12){ printErr('INVALID EXPIRY MONTH - USE MMYY'); return; }
    const display = `CC ${type} ${maskCard(num)}  EXP ${mmStr}/${yy}  (${CARD_TYPES[type]})`;
    state.pnr.formOfPayment = { type:'CC', display };
    print(`FORM OF PAYMENT ADDED - ${display}`);
    logActivity(`FORM OF PAYMENT ADDED - ${display}`);
    refreshAndPrintPNR();
  }

  function addFqtv(airline, num, tierCode){
    let text = `FQTV ${airline} FREQUENT FLYER NUMBER  ${airline}${num}`;
    if(tierCode){
      const tierName = LOYALTY_TIERS[tierCode];
      if(!tierName){ printErr(`UNKNOWN LOYALTY TIER ${tierCode} - VALID: ${Object.keys(LOYALTY_TIERS).join(' ')}`); return; }
      text += `  TIER: ${tierName}`;
    }
    const entry = { code:'FQTV', text };
    state.pnr.ssrs.push(entry);
    print(`SSR ADDED - ${entry.text}`);
    logActivity(`SSR ADDED - ${entry.text}`);
    refreshAndPrintPNR();
  }

  function addDocs(type, country, number, nationality, dob, sex, expiry, paxStr){
    const desc = DOCUMENT_TYPES[type];
    if(!desc){ printErr(`UNKNOWN DOCUMENT TYPE ${type} - VALID: ${Object.keys(DOCUMENT_TYPES).join(' ')}`); return; }
    const paxNum = parseInt(paxStr,10);
    if(!paxNum || paxNum < 1 || paxNum > state.pnr.names.length){ printErr('INVALID PASSENGER NUMBER - CHECK NAME FIELD'); return; }
    const dobMatch = dob.match(/^(\d{1,2})([A-Z]{3})(\d{2})$/);
    const dobDay = dobMatch ? parseInt(dobMatch[1],10) : 0;
    if(!dobMatch || MONTHS.indexOf(dobMatch[2]) < 0 || dobDay < 1 || dobDay > 31){
      printErr('FORMAT - INVALID DOB, USE DDMONYY e.g. 12JAN90'); return;
    }
    const expMatch = expiry.match(/^(\d{1,2})([A-Z]{3})(\d{2})$/);
    const expDay = expMatch ? parseInt(expMatch[1],10) : 0;
    if(!expMatch || MONTHS.indexOf(expMatch[2]) < 0 || expDay < 1 || expDay > 31){
      printErr('FORMAT - INVALID EXPIRY DATE, USE DDMONYY e.g. 25DEC30'); return;
    }
    const entry = { type, desc, country, number, nationality, dob, sex, expiry, pax: paxNum };
    state.pnr.docs.push(entry);
    const text = `${desc} ${country} ${number}  NATIONALITY ${nationality}  DOB ${dob}  ${sex}  EXP ${expiry}  PAX ${paxNum} (${state.pnr.names[paxNum-1]})`;
    print(`DOCUMENT ADDED - ${text}`);
    logActivity(`DOCUMENT ADDED - ${text}`);
    refreshAndPrintPNR();
  }

  function handleGeneralRemark(u){
    const text = u.slice(1).trim();
    if(!text){ printErr('FORMAT - REMARK TEXT REQUIRED'); return; }
    state.pnr.remarks.push(text);
    print(`GENERAL REMARK ADDED - ${text}`);
    logActivity(`GENERAL REMARK ADDED - ${text}`);
    refreshAndPrintPNR();
  }

  function addOsi(airline, rawText){
    const text = rawText.trim();
    if(!text){ printErr('FORMAT - OSI REQUIRES FREE TEXT, e.g. 3OSIAA VIP PASSENGER'); return; }
    const entry = { airline, text: `${airline} ${text}` };
    state.pnr.osis.push(entry);
    print(`OSI ADDED - ${entry.text}`);
    logActivity(`OSI ADDED - ${entry.text}`);
    refreshAndPrintPNR();
  }

  function addSsr(code, paxStr, freeTextRaw){
    const desc = SSR_CODES[code];
    if(!desc){ printErr(`UNKNOWN SSR CODE ${code} - TYPE HELP FOR LIST`); return; }
    const paxNum = paxStr ? parseInt(paxStr,10) : null;
    if(paxNum && (paxNum < 1 || paxNum > state.pnr.names.length)){ printErr('INVALID PASSENGER NUMBER - CHECK NAME FIELD'); return; }
    const freeText = freeTextRaw ? freeTextRaw.trim() : '';
    let text = `${code} ${desc}`;
    if(paxNum) text += `  PAX ${paxNum} (${state.pnr.names[paxNum-1]})`;
    if(freeText) text += `  /${freeText}`;
    state.pnr.ssrs.push({ code, text });
    print(`SSR ADDED - ${text}`);
    logActivity(`SSR ADDED - ${text}`);
    refreshAndPrintPNR();
  }

  function decodeAirport(code){
    const a = typeof AIRPORTS !== 'undefined' ? AIRPORTS[code] : null;
    if(!a){ printErr(`UNABLE TO DECODE - ${code} NOT FOUND`); return; }
    print(`${code}  ${a[0].toUpperCase()}`, 'hd');
    print(`  ${a[1].toUpperCase()}, ${a[2].toUpperCase()}`, 'dim');
  }

  function searchAirports(rawTerm){
    const term = rawTerm.trim();
    if(term.length < 2){ printErr('FORMAT - ENTER AT LEAST 2 CHARACTERS TO SEARCH'); return; }
    const results = [];
    for(const code in AIRPORTS){
      const a = AIRPORTS[code];
      if(a[0].toUpperCase().includes(term) || a[1].toUpperCase().includes(term)){
        results.push({ code, name:a[0], city:a[1], country:a[2] });
        if(results.length >= 25) break;
      }
    }
    if(results.length === 0){ printErr(`NO MATCH FOUND FOR "${term}"`); return; }
    print(`CITY/AIRPORT NAME SEARCH - "${term}"  (${results.length}${results.length===25?'+':''} MATCH${results.length===1?'':'ES'})`, 'hd');
    printBlank();
    for(const r of results){
      print(` ${pad(r.code,4)} ${pad(r.name.toUpperCase(),34)} ${pad(r.city.toUpperCase(),20)} ${r.country.toUpperCase()}`);
    }
  }

  function handleCancel(rangeStr){
    const nums = [];
    let valid = true;
    for(const part of rangeStr.split(',')){
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
  }

  function ignorePnr(){
    state.pnr = freshPNR();
    state.lastDisplay = [];
    print('IGNORED - PNR NOT SAVED');
  }

  // handler token (from COMMAND_GRAMMAR, shared with the CLI edition) -> local function.
  // Every handler is called as handler(rawMatchedString, ...captureGroups) so the dispatch
  // loop below stays fully generic - see spec/README.md.
  const HANDLERS = {
    SIGN_OUT: () => signOut(),
    HELP: () => showHelp(),
    AVAILABILITY: (raw, day, mon, orig, dest) => genAvailability(day, mon, orig, dest),
    SELL_FROM_AVAIL: (raw, line, cls, seats) => sellFromAvail(parseInt(line,10), cls, parseInt(seats,10)),
    LONG_SELL: (raw, al, flt, cls, day, mon, orig, dest, status, seats) => directSell(al, flt, cls, day, mon, orig, dest, status, parseInt(seats,10)),
    NAME_FIELD: (raw) => handleName(raw),
    PHONE: (raw) => handlePhone(raw),
    RECEIVED_FROM: (raw) => handleReceivedFrom(raw),
    GENERAL_REMARK: (raw) => handleGeneralRemark(raw),
    PRICE_ITINERARY: (raw, mode, corpCode) => priceItinerary(mode, corpCode),
    TICKETING_AT_WILL: () => addTicketingAtWill(),
    TICKETING_AT_WILL_DATED: (raw, day, mon, time) => addTicketingAtWillDated(day, mon, time),
    TICKETING_TIME_LIMIT: (raw, day, mon, time) => addTicketingTimeLimit(day, mon, time),
    FOP_CASH: () => addFopCash(),
    FOP_CHECK: () => addFopCheck(),
    FOP_CREDIT_CARD: (raw, type, num, mm, yy) => addFopCreditCard(type, num, mm, yy),
    ISSUE_TICKETS: () => issueTickets(),
    DOCS: (raw, type, country, number, nationality, dob, sex, expiry, pax) => addDocs(type, country, number, nationality, dob, sex, expiry, pax),
    SSR_FQTV: (raw, airline, num, tier) => addFqtv(airline, num, tier),
    OSI: (raw, airline, text) => addOsi(airline, text),
    SSR: (raw, code, pax, freeText) => addSsr(code, pax, freeText),
    SEAT_MAP: (raw, n) => showSeatMap(parseInt(n,10)),
    SEAT_ASSIGN: (raw, n, seat) => assignSeat(parseInt(n,10), seat),
    DECODE_AIRPORT: (raw, code) => decodeAirport(code),
    SEARCH_AIRPORTS: (raw, term) => searchAirports(term),
    PNR_REDISPLAY: () => refreshAndPrintPNR(),
    PNR_HISTORY: () => showHistory(),
    PNR_RETRIEVE: (raw, loc) => retrieveByLocator(loc),
    CANCEL_ITINERARY: () => cancelItinerary(),
    CANCEL_ELEMENTS: (raw, rangeStr) => handleCancel(rangeStr),
    IGNORE: () => ignorePnr(),
    END_TRANSACT_ER: () => endTransaction('ER'),
    END_TRANSACT_ET: () => endTransaction('ET'),
  };

  // ---------- command dispatch ----------
  // The signed-in/signed-out gate is structural (different handling entirely, not a
  // repeating pattern) and stays hardcoded here. Everything after it is spec-driven from
  // COMMAND_GRAMMAR (spec/command-grammar.json) - same ordered list the CLI edition loops
  // over, so the two editions can't silently drift out of sync on syntax or ordering.
  const COMPILED_GRAMMAR = COMMAND_GRAMMAR.map(entry => ({ ...entry, re: new RegExp(entry.pattern) }));

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

    for(const entry of COMPILED_GRAMMAR){
      const m = U.match(entry.re);
      if(m){
        HANDLERS[entry.handler](U, ...m.slice(1));
        return;
      }
    }

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
  const SETTINGS_KEY = 'gdsTrainerSettings';
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
