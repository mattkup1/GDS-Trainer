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
  // AIRLINES_DATA (code -> {name, numericCode}) is loaded globally from
  // spec/airlines.json via airlines.js - see spec/README.md. Kept as three
  // derived views since that's how the rest of this file already reads them.
  const AIRLINES = Object.keys(AIRLINES_DATA);
  const AIRLINE_NUMERIC_CODES = {};
  const AIRLINE_NAMES = {};
  for(const code of AIRLINES){
    AIRLINE_NUMERIC_CODES[code] = AIRLINES_DATA[code].numericCode;
    AIRLINE_NAMES[code] = AIRLINES_DATA[code].name;
  }
  const EQUIP = REFERENCE_DATA.equipment;
  const SEAT_LAYOUTS = REFERENCE_DATA.seatLayouts;
  const CLASSES = REFERENCE_DATA.classes;
  const CLASS_FARE_MULT = REFERENCE_DATA.classFareMultipliers;
  const TAX_POOL = REFERENCE_DATA.taxPool;
  const FARE_FORMULA = REFERENCE_DATA.fareFormula;
  const SCHEDULE_CHANGE = REFERENCE_DATA.scheduleChange;
  const WAITLIST_CLEAR = REFERENCE_DATA.waitlistClear;
  const SSR_CODES = REFERENCE_DATA.ssrCodes;
  const CARD_TYPES = REFERENCE_DATA.cardTypes;
  const QUEUE_CATEGORIES = REFERENCE_DATA.queueCategories;
  const PHONE_LOC_CODES = REFERENCE_DATA.phoneLocationCodes;
  const DOCUMENT_TYPES = REFERENCE_DATA.documentTypes;
  const LOYALTY_TIERS = REFERENCE_DATA.loyaltyTiers;
  const FARE_RULES = REFERENCE_DATA.fareRules;
  const CORPORATE_CODES = REFERENCE_DATA.corporateCodes;
  const EMAIL_DOCUMENTS = REFERENCE_DATA.emailDocuments;
  const SEGMENT_STATUS_LABELS = REFERENCE_DATA.segmentStatusLabels;

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
    queues: {},          // queue number -> [locator, ...] FIFO
    cmdHistory: [],
    cmdHistoryIdx: -1,
    nextMarriedGroupId: 1   // monotonic - never reused, unlike a segment's array index
  };

  function freshPNR(){
    return { locator:null, names:[], segments:[], phones:[], receivedFrom:null, ticketing:null, pricing:null,
              infants:[], ssrs:[], osis:[], seats:[], formOfPayment:null, activityLog:[], tickets:[],
              docs:[], remarks:[], priorTickets:[], priorPricing:null };
  }

  function nowStamp(){
    const now = new Date();
    return `${pad(now.getDate(),2).trim()}${MONTHS[now.getMonth()]}/${String(now.getHours()).padStart(2,'0')}${String(now.getMinutes()).padStart(2,'0')}`;
  }
  function logActivity(text){
    state.pnr.activityLog.push({ stamp: nowStamp(), sine: state.sine || '----', text });
  }

  // ---------- availability ----------
  // Matches real Sabre: every line is one ordinary flight leg, shown with its own
  // origin/destination (a connection candidate leg's city pair differs from the
  // overall search) - there is no "grouped" multi-leg line. Connections are built
  // by the agent recognizing two lines whose cities/times line up and selling both
  // together (see sellConnection below), never a single system-bundled line.
  function genFlight(rng, dep, orig, dest){
    const airline = AIRLINES[Math.floor(rng()*AIRLINES.length)];
    const flightNum = 100 + Math.floor(rng()*2899);
    const duration = 65 + Math.floor(rng()*220);
    const arr = dep + duration;
    const equip = EQUIP[Math.floor(rng()*EQUIP.length)];
    const classAvail = CLASSES.map(c => ({ cls:c, seats: Math.floor(rng()*10) }));
    return { airline, flightNum, dep, arr, duration, equip, classAvail, orig, dest };
  }

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
      flights.push({ line:i+1, ...genFlight(rng, dep, orig, dest) });
      dep += 55 + Math.floor(rng()*95);
      if(dep > 1380) dep = 300 + Math.floor(rng()*60);
    }

    // Always append exactly 2 workable connections (4 more lines: 2 legs each) after the
    // nonstops, continuing to draw from the same RNG stream (search stays one deterministic
    // sequence per orig/dest/date). Keeping them last means line 1 is always a nonstop for
    // every route/date. Each pair of lines is a real, separately-numbered flight - nothing
    // marks them as "connectable"; the agent reads the city pairs/times like on real Sabre.
    const airportCodes = typeof AIRPORTS !== 'undefined' ? Object.keys(AIRPORTS) : [];
    let nextLine = numFlights+1;
    for(let i=0;i<2;i++){
      let via = orig;
      if(airportCodes.length){
        for(let tries=0; tries<10 && (via===orig || via===dest); tries++){
          via = airportCodes[Math.floor(rng()*airportCodes.length)];
        }
      }
      const dep1 = 300 + Math.floor(rng()*600);
      const leg1 = genFlight(rng, dep1, orig, via);
      const layover = 45 + Math.floor(rng()*135);
      const leg2 = genFlight(rng, leg1.arr + layover, via, dest);
      flights.push({ line: nextLine++, ...leg1 });
      flights.push({ line: nextLine++, ...leg2 });
    }
    state.lastAvail = { orig, dest, dinfo, flights };

    print(`** AIR AVAILABILITY **  ${orig}-${dest}  ${dinfo.day}${dinfo.mon}${dinfo.year}  ${dinfo.weekday}`, 'hd');
    print(`  ${cityName(orig)}  TO  ${cityName(dest)}`, 'dim');
    printBlank();
    // Built from the same field widths as the data rows below (not hand-counted spaces)
    // so the header can't drift out of alignment with them - see the seat map header's
    // identical rationale.
    print(` ${pad('LN',2)} ${pad('FLT',7)}  ${pad('RTE',6)}  ${CLASSES.map(c=>pad(c,3)).join('')} ${pad('DEP',6)} ${pad('ARR',6)} EQP`, 'dim');
    for(const f of flights){
      const classStr = f.classAvail.map(c => pad(c.cls + c.seats, 3)).join('');
      print(` ${pad(f.line,2)} ${f.airline} ${pad(f.flightNum,4)}  ${f.orig}${f.dest}  ${classStr} ${pad(minutesToClock(f.dep),6)} ${pad(minutesToClock(f.arr),6)} ${f.equip}`);
    }
    printBlank();
    print('SELL WITH: 0{LINE}{CLASS}{SEATS}   e.g. 0' + flights[0].line + 'Y1', 'dim');
    print('SELL CONNECTION: 0{SEATS}{CLASS}{LINE}{CLASS}{LINE}   e.g. 02Y' + flights[0].line + 'Y' + flights[flights.length-1].line, 'dim');
  }

  // Real Sabre's schedule display: identical entry shape to availability ("S" instead of
  // "A"/"1"), but shows what flies across a several-day window - no booking classes/seat
  // counts, since it's not tied to sellable inventory. Reuses genAvailability's exact
  // per-date seeding/generation (same hashStr/mulberry32/genFlight calls) once per date in
  // the window rather than a second, disconnected formula - so a date also covered by an
  // availability search on the same route shows the literal same flights here, just without
  // the booking columns. Nonstop only - connections are an availability/booking-time
  // concept, not a schedule-lookup one.
  function genSchedule(dayStr, monStr, orig, dest){
    if(orig === dest){ printErr('FORMAT - ORIGIN AND DESTINATION CANNOT BE THE SAME'); return; }
    const startInfo = parseDate(dayStr, monStr);
    if(!startInfo){ printErr('INVALID DATE - CHECK ENTRY AND REENTER'); return; }

    const days = [];
    for(let i=0;i<7;i++){
      const d = new Date(startInfo.date.getTime());
      d.setDate(d.getDate()+i);
      days.push({ day: d.getDate(), mon: MONTHS[d.getMonth()], year: d.getFullYear(), weekday: WEEKDAYS[d.getDay()] });
    }

    print(`** SCHEDULE **  ${orig}-${dest}  ${days[0].day}${days[0].mon}${days[0].year} - ${days[6].day}${days[6].mon}${days[6].year}`, 'hd');
    print(`  ${cityName(orig)}  TO  ${cityName(dest)}`, 'dim');
    for(const day of days){
      const seed = hashStr(`${orig}${dest}${day.day}${day.mon}${day.year}`);
      const rng = mulberry32(seed);
      const numFlights = 5 + Math.floor(rng()*4);
      let dep = 300 + Math.floor(rng()*90);
      printBlank();
      print(`${pad(day.day,2)}${day.mon} ${day.weekday}`, 'hd');
      print(`  FLT       DEP    ARR    ELAPSED EQP`, 'dim');
      for(let i=0;i<numFlights;i++){
        const f = genFlight(rng, dep, orig, dest);
        const elapsed = `${Math.floor(f.duration/60)}:${String(f.duration%60).padStart(2,'0')}`;
        print(`  ${f.airline} ${pad(f.flightNum,4)}  ${pad(minutesToClock(f.dep),6)} ${pad(minutesToClock(f.arr),6)} ${pad(elapsed,7)} ${f.equip}`);
        dep += 55 + Math.floor(rng()*95);
        if(dep > 1380) dep = 300 + Math.floor(rng()*60);
      }
    }
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
        dinfo: state.lastAvail.dinfo, orig: f.orig, dest: f.dest,
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
      dinfo: state.lastAvail.dinfo, orig: f.orig, dest: f.dest,
      dep: f.dep, arr: f.arr, status: 'HK', equip: f.equip
    };
    state.pnr.segments.push(seg);
    cinfo.seats -= seats;
    print(`SEGMENT SOLD - ${formatSegmentShort(seg)}`);
    logActivity(`SEGMENT SOLD - ${formatSegmentShort(seg)}`);
    invalidatePricing();
    refreshAndPrintPNR();
  }

  // Real Sabre connection sell: "0{SEATS}{CLASS1}{LINE1}{CLASS2}{LINE2}" - the agent
  // picks two lines from the display whose cities/times work as a connection (nothing
  // in the display marks them as connectable) and sells both in one entry.
  function sellConnection(seats, cls1, line1Num, cls2, line2Num){
    if(!state.lastAvail){ printErr('NO AVAILABILITY DISPLAY IN CONTEXT - ENTER AVAIL FIRST'); return; }
    const f1 = state.lastAvail.flights.find(fl => fl.line === line1Num);
    const f2 = state.lastAvail.flights.find(fl => fl.line === line2Num);
    if(!f1 || !f2){ printErr('INVALID LINE NUMBER - CHECK ENTRY AND REENTER'); return; }
    if(f1.dest !== f2.orig){ printErr(`INVALID CONNECTION - ${f1.dest} DOES NOT MATCH ${f2.orig}`); return; }
    if(f2.dep < f1.arr + 30){ printErr('UNABLE - INSUFFICIENT CONNECTION TIME'); return; }

    const legs = [ {flight:f1, cls:cls1.toUpperCase()}, {flight:f2, cls:cls2.toUpperCase()} ];
    // Validate both legs before mutating anything, so a shortfall on the second leg
    // never leaves the PNR half-sold.
    const cinfos = [];
    for(const {flight, cls} of legs){
      const cinfo = flight.classAvail.find(c => c.cls === cls);
      if(!cinfo){ printErr(`CLASS ${cls} NOT OFFERED ON THIS FLIGHT`); return; }
      if(cinfo.seats > 0 && seats > cinfo.seats){ printErr(`UNABLE - ONLY ${cinfo.seats} SEAT(S) AVAILABLE IN CLASS ${cls}`); return; }
      cinfos.push(cinfo);
    }

    // Married segments: the two legs are tagged with a shared group id so cancelElements
    // can later require both be cancelled together, matching real Sabre. Marriage is only
    // ever created here - the one place two segments are known to belong to one itinerary.
    const marriedGroup = state.nextMarriedGroupId++;
    legs.forEach(({flight, cls}, i) => {
      const cinfo = cinfos[i];
      const waitlisted = cinfo.seats === 0;
      const seg = {
        airline: flight.airline, flightNum: flight.flightNum, cls, seats,
        dinfo: state.lastAvail.dinfo, orig: flight.orig, dest: flight.dest,
        dep: flight.dep, arr: flight.arr, status: waitlisted ? 'HL' : 'HK', equip: flight.equip,
        marriedGroup
      };
      state.pnr.segments.push(seg);
      if(!waitlisted) cinfo.seats -= seats;
      const label = waitlisted ? 'SEGMENT WAITLISTED' : 'SEGMENT SOLD';
      print(`${label} - ${formatSegmentShort(seg)}`);
      logActivity(`${label} - ${formatSegmentShort(seg)}`);
    });
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

  // Shared by every path that stales out a fare quote/ticket (sell, cancel, schedule
  // change): snapshots the outgoing pricing/tickets into priorPricing/priorTickets - but
  // only when the PNR was actually ticketed (both set), since there's nothing meaningful to
  // exchange from a merely-priced-but-not-ticketed PNR - before clearing them, so a later
  // WFR{TICKET#} exchange can still reference what the passenger already paid.
  function clearPricingAndTickets(p){
    if(p.pricing && p.tickets.length){
      p.priorTickets = p.tickets;
      p.priorPricing = p.pricing;
    }
    p.pricing = null;
    p.tickets = [];
  }

  function invalidatePricing(){
    const hadPricing = !!state.pnr.pricing;
    const hadTickets = state.pnr.tickets.length > 0;
    clearPricingAndTickets(state.pnr);
    if(hadPricing){
      print('FARE QUOTE INVALIDATED - ITINERARY CHANGED, RE-PRICE WITH WP', 'dim');
      logActivity('FARE QUOTE INVALIDATED - ITINERARY CHANGED');
    }
    if(hadTickets){
      print('TICKETS VOIDED - ITINERARY CHANGED, REISSUE WITH TKTT OR EXCHANGE WITH WFR AFTER RE-PRICING', 'dim');
      logActivity('TICKETS VOIDED - ITINERARY CHANGED');
    }
  }

  function formatSegmentShort(seg){
    return `${seg.airline}${seg.flightNum} ${seg.cls} ${seg.dinfo.day}${seg.dinfo.mon} ${seg.orig}${seg.dest} ${seg.status}${seg.seats}  ${minutesToClock(seg.dep)} ${minutesToClock(seg.arr)}`;
  }

  // ---------- pricing (WP / WPNCS) ----------
  // Real Sabre's "FQ" entry: a bare fare quote by city pair, independent of any PNR/
  // itinerary - unlike priceItinerary below, there's no segment to derive a fare from, so
  // this seeds off the route only and reuses the same shared spec constants (FARE_FORMULA/
  // CLASS_FARE_MULT/TAX_POOL) via its own parallel calculation, one indicative total per
  // booking class. Purely informational - no PNR mutation, no activity log entry, matching
  // DC/DAN's existing precedent as pure lookups with no PNR side effects.
  function fareQuoteShop(orig, dest){
    if(orig === dest){ printErr('FORMAT - ORIGIN AND DESTINATION CANNOT BE THE SAME'); return; }
    const rng = mulberry32(hashStr(`FQ${orig}${dest}`));
    const dist = FARE_FORMULA.distanceMin + Math.floor(rng()*FARE_FORMULA.distanceRange);

    print(`** FARE QUOTE SHOP **  ${orig}-${dest}`, 'hd');
    print(`  ${cityName(orig)}  TO  ${cityName(dest)}`, 'dim');
    printBlank();
    print('CLS  BASE FARE    TAXES/FEES    TOTAL', 'dim');
    for(const cls of CLASSES){
      const mult = CLASS_FARE_MULT[cls] || 1.4;
      const baseFare = Math.round((FARE_FORMULA.baseFareCoefficient + dist*FARE_FORMULA.baseFarePerMile) * mult);

      const numTaxes = FARE_FORMULA.minTaxes + Math.floor(rng()*FARE_FORMULA.additionalTaxesRange);
      const pool = TAX_POOL.slice().sort(() => rng()-0.5).slice(0, numTaxes);
      let taxTotal = 0;
      for(const t of pool){
        taxTotal += Math.round((FARE_FORMULA.taxAmountMin + rng()*FARE_FORMULA.taxAmountRange) * 100)/100;
      }
      taxTotal = Math.round(taxTotal*100)/100;
      const total = Math.round((baseFare + taxTotal)*100)/100;
      print(` ${cls}    USD ${pad(baseFare.toFixed(2),9)}  USD ${pad(taxTotal.toFixed(2),9)}  USD ${total.toFixed(2)}`);
    }
    printBlank();
    print('INDICATIVE ONLY - PRICE THE ACTUAL ITINERARY WITH WP AFTER BOOKING', 'dim');
  }

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

  // ---------- itinerary/invoice document (EM/EMI/EMT, browser-only render) ----------
  // Real Sabre's EM/EMI/EMT end-transaction variants mail the passenger an
  // itinerary/invoice/e-ticket document. This offline simulator has no real
  // email, so the honest equivalent is opening a formatted, print-ready
  // document in a new tab the user can print or "Save as PDF" - presenting
  // data end_transaction already produced, not a new source of truth.
  function buildItineraryDocument(mode){
    const p = state.pnr;
    const cfg = EMAIL_DOCUMENTS[mode];
    const has = (s) => cfg.sections.includes(s);
    return {
      mode, label: cfg.label,
      pcc: state.pcc, sine: state.sine, issued: new Date(), locator: p.locator,
      passengers: p.names.map(n => ({ name: n, infants: p.infants.filter(inf => inf.adult === n) })),
      segments: has('segments') ? p.segments : [],
      seats: has('seats') ? p.seats : [],
      ssrs: has('ssrs') ? p.ssrs : [],
      osis: has('osis') ? p.osis : [],
      pricing: has('pricing') ? p.pricing : null,
      formOfPayment: has('formOfPayment') ? p.formOfPayment : null,
      tickets: has('tickets') ? p.tickets : null,
    };
  }

  function escapeHtml(s){
    return String(s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  // Deterministic per-carrier accent color/badge - the default stand-in for a
  // real airline logo. If a real logo was dropped into spec/airline-logos/ and
  // baked in via spec/build.py (gitignored, see that folder's README - real
  // airline logos are trademarked/copyrighted assets this repo doesn't ship),
  // it's used instead; airlineLogoHTML() is what call sites actually use.
  function airlineBadgeColor(code){
    return `hsl(${hashStr(code) % 360} 62% 40%)`;
  }
  function airlineBadgeSVG(code){
    const label = escapeHtml(code);
    return `<svg class="carrier-badge" viewBox="0 0 44 44" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="${label}">
      <rect width="44" height="44" rx="10" fill="${airlineBadgeColor(code)}"/>
      <path d="M22 7 L25.4 18.5 L36 22 L25.4 24 L23 35 L21 24 L9 22 L20.6 18.5 Z" fill="#ffffff" opacity=".22"/>
      <text x="22" y="27" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="15" font-weight="700" fill="#fff">${label}</text>
    </svg>`;
  }
  function airlineLogoHTML(code){
    const dataUri = typeof AIRLINE_LOGOS !== 'undefined' ? AIRLINE_LOGOS[code] : null;
    return dataUri
      ? `<img class="carrier-badge" src="${escapeHtml(dataUri)}" alt="${escapeHtml(code)}">`
      : airlineBadgeSVG(code);
  }
  function formatDuration(mins){
    return `${Math.floor(mins/60)}H ${String(mins%60).padStart(2,'0')}M`;
  }

  function renderItineraryDocumentHTML(doc){
    const e = escapeHtml;
    const issuedStr = `${doc.issued.getDate()} ${MONTHS[doc.issued.getMonth()]} ${doc.issued.getFullYear()}`;

    const passengersHtml = doc.passengers.map(p => {
      const infantsHtml = p.infants.map(inf => `<div class="pax-sub">+ INFANT ${e(inf.surname)}/${e(inf.given)} &nbsp; DOB ${e(inf.dob)}</div>`).join('');
      return `<div class="pax-row"><div class="pax-name">${e(p.name)}</div>${infantsHtml}</div>`;
    }).join('') || '<div class="dim">NO PASSENGERS ON FILE</div>';

    const seatsBySeg = {};
    for(const s of doc.seats){
      (seatsBySeg[s.segIdx] = seatsBySeg[s.segIdx] || []).push(s.seat);
    }
    const airportBlock = (code) => {
      const a = typeof AIRPORTS !== 'undefined' ? AIRPORTS[code] : null;
      return a
        ? `<div class="leg-airport">${e(a[0])} (${e(code)})</div><div class="leg-sub">${e(a[1])}, ${e(a[2])}</div>`
        : `<div class="leg-airport">${e(cityName(code))}</div>`;
    };
    const segmentsHtml = doc.segments.map((s, i) => {
      const statusLabel = SEGMENT_STATUS_LABELS[s.status] || s.status;
      const statusClass = s.status === 'HK' ? 'ok' : 'wait';
      const seatList = (seatsBySeg[i] || []).join(', ');
      const airlineFull = AIRLINE_NAMES[s.airline] || s.airline;
      return `
        <div class="flight-card">
          <div class="flight-card-head">
            <span>FLIGHT ${i+1} &mdash; ${e(s.dinfo.weekday)}, ${e(s.dinfo.day)} ${e(s.dinfo.mon)} ${e(s.dinfo.year)}</span>
            <span class="status-pill ${statusClass}">${e(statusLabel)}</span>
          </div>
          <div class="flight-card-route">${e(cityName(s.orig))} to ${e(cityName(s.dest))}</div>
          <div class="flight-card-body">
            <div class="carrier-col">
              ${airlineLogoHTML(s.airline)}
              <div class="carrier-name">${e(airlineFull)}</div>
              <div class="flight-num">${e(s.airline)}${e(s.flightNum)} &nbsp; CLASS ${e(s.cls)}</div>
            </div>
            <div class="leg-col">
              <div class="leg-label">DEPART</div>
              ${airportBlock(s.orig)}
              <div class="leg-time">${minutesToClock(s.dep)}</div>
            </div>
            <div class="leg-col">
              <div class="leg-label">ARRIVE</div>
              ${airportBlock(s.dest)}
              <div class="leg-time">${minutesToClock(s.arr)}</div>
            </div>
            <div class="info-col">
              <div>DURATION <strong>${formatDuration(s.arr - s.dep)}</strong></div>
              <div>AIRCRAFT <strong>${s.equip ? e(s.equip) : '&mdash;'}</strong></div>
              <div>SEAT(S) <strong>${e(seatList) || '&mdash;'}</strong></div>
            </div>
          </div>
        </div>`;
    }).join('');

    let ssrBlock = '';
    if(doc.ssrs && doc.ssrs.length){
      ssrBlock = `
        <div class="doc-card">
          <div class="doc-card-head">SPECIAL SERVICE REQUESTS</div>
          <div class="doc-card-body req-list">${doc.ssrs.map(r => `<div class="req-row">${e(r.text)}</div>`).join('')}</div>
        </div>`;
    }

    let osiBlock = '';
    if(doc.osis && doc.osis.length){
      osiBlock = `
        <div class="doc-card">
          <div class="doc-card-head">OTHER SERVICE INFORMATION</div>
          <div class="doc-card-body req-list">${doc.osis.map(o => `<div class="req-row">${e(o.text)}</div>`).join('')}</div>
        </div>`;
    }

    let pricingBlock = '';
    if(doc.pricing){
      const pr = doc.pricing;
      const taxRows = pr.taxes.map(t => `<tr><td>${e(t.code)} ${e(t.label)}</td><td class="amt">USD ${t.amount.toFixed(2)}</td></tr>`).join('');
      const rulesHtml = pr.rules ? `
        <div class="rules-line">CHANGE FEE USD ${pr.rules.changeFee.toFixed(2)} &nbsp; REFUNDABLE ${pr.rules.refundable ? 'YES' : 'NO'} &nbsp; ADVANCE PURCHASE ${pr.rules.advancePurchaseDays} DAYS</div>` : '';
      pricingBlock = `
        <div class="doc-card">
          <div class="doc-card-head">FARE SUMMARY</div>
          <table class="doc-table">
            <tbody>
              <tr><td>BASE FARE</td><td class="amt">USD ${pr.baseFare.toFixed(2)}</td></tr>
              ${taxRows}
              <tr><td>TAXES / FEES</td><td class="amt">USD ${pr.taxTotal.toFixed(2)}</td></tr>
              <tr class="total"><td>TOTAL</td><td class="amt">USD ${pr.total.toFixed(2)}</td></tr>
            </tbody>
          </table>
          ${rulesHtml}
        </div>`;
    }

    let paymentBlock = '';
    if(doc.formOfPayment){
      paymentBlock = `
        <div class="doc-card">
          <div class="doc-card-head">FORM OF PAYMENT</div>
          <div class="doc-card-body">${e(doc.formOfPayment.display)}</div>
        </div>`;
    }

    let ticketsBlock = '';
    if(doc.tickets !== null){
      ticketsBlock = `
        <div class="doc-card">
          <div class="doc-card-head">TICKETING INFORMATION</div>
          ${doc.tickets.length ? `
          <table class="doc-table">
            <thead><tr><th>ISSUE DATE</th><th>PASSENGER NAME</th><th>TRANSACTION TYPE</th><th>DOCUMENT NUMBER</th></tr></thead>
            <tbody>${doc.tickets.map(t => `<tr><td>${issuedStr}</td><td>${e(t.passenger)}${t.isInfant ? ' (INFANT)' : ''}</td><td>Electronic Ticket</td><td class="mono">${e(t.ticketNum)}</td></tr>`).join('')}</tbody>
          </table>` : `<div class="doc-card-body dim">NOT YET TICKETED${doc.mode === 'EMT' ? ' &mdash; RUN TKTT BEFORE THIS DOCUMENT REFLECTS ISSUED TICKETS' : ''}</div>`}
        </div>`;
    }

    return `<!doctype html>
<html><head><meta charset="utf-8"><title>${e(doc.label)} - ${e(doc.locator || 'GDS TRAINER')}</title>
<style>
  *{ box-sizing:border-box; -webkit-print-color-adjust:exact; print-color-adjust:exact; }
  body{ font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; color:#1c2430; background:#f4f6f8; margin:0; padding:28px 16px 60px; }
  .doc{ max-width:760px; margin:0 auto; background:#fff; border:1px solid #d7dee6; border-radius:10px; overflow:hidden; box-shadow:0 1px 3px rgba(0,0,0,.08); }
  .doc-head{ display:flex; align-items:center; justify-content:space-between; background:#0b5fae; color:#fff; padding:16px 22px; }
  .brand{ display:flex; align-items:center; gap:8px; font-weight:700; letter-spacing:.5px; font-size:15px; }
  .brand-mark{ width:20px; height:20px; }
  .doc-type{ font-size:11px; font-weight:700; letter-spacing:1.5px; background:rgba(255,255,255,.18); padding:5px 10px; border-radius:4px; }
  .doc-meta{ display:flex; flex-wrap:wrap; gap:22px; padding:14px 22px; background:#eaf3fc; border-bottom:1px solid #d7dee6; font-size:12px; }
  .meta-label{ display:block; color:#5b6472; font-size:10px; letter-spacing:.5px; margin-bottom:2px; }
  .meta-value{ font-weight:600; color:#1c2430; }
  .meta-value.mono{ font-family:'Courier New',monospace; letter-spacing:1px; }
  #printBtn{ margin:16px 22px 0; padding:8px 16px; font:inherit; font-weight:600; color:#0b5fae; background:#fff; border:1px solid #0b5fae; border-radius:5px; cursor:pointer; }
  #printBtn:hover{ background:#eaf3fc; }
  section{ padding:18px 22px 4px; }
  h2{ font-size:11px; letter-spacing:1px; color:#5b6472; margin:0 0 10px; text-transform:uppercase; }
  .pax-list{ display:flex; flex-direction:column; gap:6px; }
  .pax-row{ font-size:13px; }
  .pax-name{ font-weight:700; }
  .pax-sub{ color:#5b6472; font-size:11px; margin-left:12px; }
  .dim{ color:#8a93a1; font-size:12px; }
  .flight-card{ border:1px solid #d7dee6; border-radius:8px; margin-bottom:14px; overflow:hidden; }
  .flight-card-head{ display:flex; justify-content:space-between; align-items:center; background:#0b5fae; color:#fff; padding:9px 14px; font-size:12px; font-weight:600; letter-spacing:.4px; }
  .status-pill{ font-size:10px; font-weight:700; letter-spacing:.5px; padding:3px 9px; border-radius:20px; }
  .status-pill.ok{ background:#e6f4ea; color:#1e7e34; }
  .status-pill.wait{ background:#fff4e0; color:#946200; }
  .flight-card-route{ background:#eaf3fc; color:#33414f; font-size:11px; padding:7px 14px; border-bottom:1px solid #d7dee6; }
  .flight-card-body{ display:grid; grid-template-columns:110px 1fr 1fr 130px; gap:14px; padding:14px; }
  .carrier-col{ display:flex; flex-direction:column; align-items:flex-start; gap:6px; }
  .carrier-badge{ width:40px; height:40px; object-fit:contain; border-radius:6px; }
  .carrier-name{ font-size:10px; font-weight:600; color:#33414f; line-height:1.3; }
  .flight-num{ font-size:10px; color:#5b6472; }
  .leg-label{ font-size:9px; letter-spacing:1px; color:#8a93a1; margin-bottom:2px; }
  .leg-airport{ font-size:12px; font-weight:600; }
  .leg-sub{ font-size:10px; color:#5b6472; }
  .leg-time{ font-size:15px; font-weight:700; color:#0b5fae; margin-top:4px; }
  .info-col{ font-size:10px; color:#5b6472; display:flex; flex-direction:column; gap:5px; }
  .info-col strong{ color:#1c2430; }
  .doc-card{ margin:0 22px 18px; border:1px solid #d7dee6; border-radius:8px; overflow:hidden; }
  .doc-card-head{ background:#0b5fae; color:#fff; font-size:11px; font-weight:700; letter-spacing:1px; padding:8px 14px; }
  .doc-card-body{ padding:12px 14px; font-size:12px; }
  .req-list .req-row{ padding:6px 0; }
  .req-list .req-row + .req-row{ border-top:1px solid #e5e9ef; }
  table.doc-table{ width:100%; border-collapse:collapse; font-size:12px; }
  table.doc-table td, table.doc-table th{ padding:8px 14px; text-align:left; border-bottom:1px solid #e5e9ef; }
  table.doc-table th{ font-size:10px; letter-spacing:.5px; color:#5b6472; background:#f7f9fb; }
  table.doc-table .amt{ text-align:right; }
  table.doc-table .mono{ font-family:'Courier New',monospace; }
  table.doc-table tr.total td{ font-weight:700; border-top:2px solid #0b5fae; border-bottom:none; }
  .rules-line{ padding:0 14px 12px; font-size:10px; color:#5b6472; }
  .disclaimer{ margin:22px; padding-top:12px; border-top:1px solid #e5e9ef; color:#8a93a1; font-size:10px; }
  @media print{ body{ background:#fff; padding:0; } .doc{ border:none; box-shadow:none; max-width:100%; border-radius:0; } #printBtn{ display:none; } }
  @media (max-width:640px){ .flight-card-body{ grid-template-columns:1fr 1fr; } .info-col{ grid-column:1 / -1; flex-direction:row; flex-wrap:wrap; gap:14px; } }
</style></head>
<body>
  <div class="doc">
    <div class="doc-head">
      <div class="brand">
        <svg class="brand-mark" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M2 21l21-9L2 3v7l15 2-15 2z" fill="#fff"/></svg>
        <span>GDS TRAINER</span>
      </div>
      <div class="doc-type">${e(doc.label)}</div>
    </div>
    <div class="doc-meta">
      <div><span class="meta-label">RECORD LOCATOR</span><span class="meta-value mono">${e(doc.locator || 'NOT SAVED')}</span></div>
      <div><span class="meta-label">ISSUED</span><span class="meta-value">${issuedStr}</span></div>
      <div><span class="meta-label">AGENT / PCC</span><span class="meta-value">${e(doc.sine || '----')} / ${e(doc.pcc || '----')}</span></div>
    </div>
    <button id="printBtn" onclick="window.print()">PRINT / SAVE AS PDF</button>
    <section>
      <h2>Passenger(s)</h2>
      <div class="pax-list">${passengersHtml}</div>
    </section>
    <section>
      <h2>Itinerary</h2>
      ${segmentsHtml || '<div class="dim">NO ITINERARY SEGMENTS</div>'}
    </section>
    ${ssrBlock}
    ${osiBlock}
    ${pricingBlock}
    ${paymentBlock}
    ${ticketsBlock}
    <div class="disclaimer">This is an educational simulation, not connected to any real airline or GDS network - not a real travel document. Any carrier logos shown are for identification only and are not sponsored or endorsed by that airline.</div>
  </div>
</body></html>`;
  }

  function openItineraryDocument(doc){
    const html = renderItineraryDocumentHTML(doc);
    const w = window.open('', '_blank');
    if(!w){ printErr('POP-UP BLOCKED - ALLOW POP-UPS TO VIEW/PRINT THE ITINERARY DOCUMENT'); return; }
    w.document.open();
    w.document.write(html);
    w.document.close();
  }

  // ---------- special service requests / other service info ----------

  // ---------- seat maps ----------
  function getSeatLayout(equip){
    return SEAT_LAYOUTS[equip] || SEAT_LAYOUTS._default;
  }

  // Normalizes a layout into its deck list. Most aircraft are single-deck,
  // so they're wrapped as one unlabeled deck - everything downstream (map
  // generation, printing, the GUI grid, seat validation) only ever has to
  // handle the multi-deck shape. Double-deckers (747/A380) supply their own
  // `decks` array in spec/reference-data.json with non-overlapping row
  // ranges, so a seat's row number alone is enough to find its deck.
  function layoutDecks(layout){
    return layout.decks || [{ label:null, rowStart:1, rows:layout.rows, cols:layout.cols }];
  }

  // Shared 3-char cell template - used for both the header letters and the
  // row symbols so they can't drift out of alignment with each other.
  function seatCell(s){ return ` ${s} `; }

  function getSeatMap(seg){
    const layout = getSeatLayout(seg.equip);
    const decks = layoutDecks(layout);
    const seed = hashStr(`${seg.airline}${seg.flightNum}${seg.dinfo.day}${seg.dinfo.mon}${seg.orig}${seg.dest}SEATMAP`);
    const rng = mulberry32(seed);
    const rows = [];
    const occupied = new Set();
    for(const deck of decks){
      const cols = deck.cols.join('').split('');
      for(let i=0; i<deck.rows; i++){
        const r = deck.rowStart + i;
        const seats = cols.map(col => {
          const occ = rng() < 0.4;
          if(occ) occupied.add(`${r}${col}`);
          return occ;
        });
        rows.push({ num:r, seats, deck });
      }
    }
    return { rows, occupied, layout, decks };
  }

  function seatMapHeaderLine(deck){
    const groups = deck.cols.map(group => group.split('').map(seatCell).join(''));
    return '      ' + groups.join('   ');
  }

  function seatMapRowLine(row, mine){
    let pos = 0;
    const groups = row.deck.cols.map(group => {
      const line = group.split('').map((col, i) => {
        const seatId = `${row.num}${col}`;
        const occ = row.seats[pos + i];
        return seatCell(mine.has(seatId) ? '*' : (occ ? 'X' : '.'));
      }).join('');
      pos += group.length;
      return line;
    });
    return ` ${pad(row.num,3)}  ${groups.join('   ')}`;
  }

  function showSeatMap(n){
    const seg = state.pnr.segments[n-1];
    if(!seg){ printErr('INVALID SEGMENT NUMBER - CHECK ITINERARY'); return; }
    const map = getSeatMap(seg);
    const mine = new Set(state.pnr.seats.filter(s => s.segIdx === n-1).map(s => s.seat));
    print(`SEAT MAP - ${seg.airline}${seg.flightNum}  ${seg.equip || ''}  ${seg.dinfo.day}${seg.dinfo.mon}  ${seg.orig}-${seg.dest}`, 'hd');
    printBlank();
    for(const deck of map.decks){
      if(deck.label) print(deck.label, 'dim');
      print(seatMapHeaderLine(deck), 'dim');
      for(const row of map.rows){
        if(row.deck === deck) print(seatMapRowLine(row, mine));
      }
      printBlank();
    }
    print('. OPEN   X OCCUPIED   * YOUR ASSIGNMENT', 'dim');
    print(`ASSIGN WITH: 4${n}-{SEAT}   e.g. 4${n}-14A`, 'dim');
    renderSeatMapPanel(n, seg, map, mine);
    switchDockTab('seat');
  }

  function assignSeat(n, seatStr){
    const seg = state.pnr.segments[n-1];
    if(!seg){ printErr('INVALID SEGMENT NUMBER - CHECK ITINERARY'); return; }
    const rowMatch = seatStr.match(/^(\d{1,2})([A-HJK])$/);
    const row = parseInt(rowMatch[1],10);
    const letter = rowMatch[2];
    const map = getSeatMap(seg);
    const deck = map.decks.find(d => row >= d.rowStart && row < d.rowStart + d.rows);
    if(!deck){
      const maxRow = Math.max(...map.decks.map(d => d.rowStart + d.rows - 1));
      printErr(`INVALID SEAT ROW - VALID RANGE 1-${maxRow}`);
      return;
    }
    if(!deck.cols.join('').includes(letter)){ printErr(`INVALID SEAT LETTER ${letter} - VALID: ${deck.cols.join(' ')}`); return; }
    if(map.occupied.has(seatStr)){ printErr(`SEAT ${seatStr} NOT AVAILABLE - SELECT ANOTHER (SEE SEAT MAP: 4${n})`); return; }
    if(state.pnr.seats.some(s => s.segIdx === n-1 && s.seat === seatStr)){ printErr(`SEAT ${seatStr} ALREADY ASSIGNED ON THIS SEGMENT`); return; }
    state.pnr.seats.push({ segIdx: n-1, seat: seatStr });
    print(`SEAT ASSIGNED - SEG${n} ${seatStr}`);
    logActivity(`SEAT ASSIGNED - SEG${n} ${seatStr}`);
    refreshAndPrintPNR();
  }

  // ---------- seat map panel (GUI, browser-only) ----------
  // Supplementary to the ASCII map printed above - clicking an open seat types
  // the real 4{n}-{seat} command and submits it through submitCommand(), it
  // never mutates state directly. See notes/GUI Expansion Scope-Out.md.
  //
  // Re-renders the open seat-map panel (if any) against current PNR state -
  // called from refreshAndPrintPNR() so a seat cancelled via X{N} (or a segment
  // cancelled out from under it) stops showing as "mine"/occupied in the GUI,
  // the same way the ASCII map only ever reflected state at the moment 4{N} was run.
  function refreshSeatMapPanelIfOpen(){
    if(seatMapPanel.classList.contains('hidden')) return;
    const segIdx = parseInt(seatMapPanel.dataset.segIdx, 10);
    const seg = state.pnr.segments[segIdx];
    if(!seg){ switchDockTab('pnr'); return; }
    const map = getSeatMap(seg);
    const mine = new Set(state.pnr.seats.filter(s => s.segIdx === segIdx).map(s => s.seat));
    renderSeatMapPanel(segIdx + 1, seg, map, mine);
  }

  function renderSeatMapPanel(n, seg, map, mine){
    seatMapPanel.dataset.segIdx = String(n-1);
    seatMapTitle.textContent = `SEAT MAP - ${seg.airline}${seg.flightNum} ${seg.equip || ''} SEG${n}`;
    seatMapGrid.innerHTML = '';

    for(const deck of map.decks){
      if(deck.label){
        const label = document.createElement('div');
        label.className = 'seatmap-decklabel';
        label.textContent = deck.label;
        seatMapGrid.appendChild(label);
      }

      const header = document.createElement('div');
      header.className = 'seatmap-header';
      header.appendChild(Object.assign(document.createElement('div'), { className: 'seatmap-headnum' }));
      for(const group of deck.cols){
        const g = document.createElement('div');
        g.className = 'seatgroup';
        for(const letter of group){
          const l = document.createElement('div');
          l.className = 'seatmap-headletter';
          l.textContent = letter;
          g.appendChild(l);
        }
        header.appendChild(g);
      }
      seatMapGrid.appendChild(header);

      for(const row of map.rows){
        if(row.deck !== deck) continue;
        const rowEl = document.createElement('div');
        rowEl.className = 'seatrow';
        const numEl = document.createElement('div');
        numEl.className = 'seatmap-rownum';
        numEl.textContent = row.num;
        rowEl.appendChild(numEl);

        let idx = 0;
        for(const group of deck.cols){
          const g = document.createElement('div');
          g.className = 'seatgroup';
          for(const letter of group){
            const seatId = `${row.num}${letter}`;
            const occ = row.seats[idx];
            const isMine = mine.has(seatId);
            const btn = document.createElement('button');
            btn.className = 'seatcell ' + (isMine ? 'mine' : (occ ? 'occupied' : 'open'));
            btn.textContent = isMine ? '*' : letter;
            btn.title = seatId;
            if(occ){
              btn.disabled = true;
            } else if(isMine){
              btn.addEventListener('click', () => {
                const seatArrIdx = state.pnr.seats.findIndex(s => s.segIdx === n-1 && s.seat === seatId);
                const el = state.lastDisplay.find(e => e.kind === 'seat' && e.idx === seatArrIdx);
                if(el) submitCommand(`X${el.num}`);
              });
            } else {
              btn.addEventListener('click', () => submitCommand(`4${n}-${seatId}`));
            }
            g.appendChild(btn);
            idx++;
          }
          rowEl.appendChild(g);
        }
        seatMapGrid.appendChild(rowEl);
      }
    }

    seatMapLegend.textContent = 'CLICK AN OPEN SEAT TO ASSIGN IT, CLICK YOUR SEAT TO CANCEL IT   -   GREEN = OPEN   DIM = OCCUPIED   FILLED = YOUR ASSIGNMENT';
  }

  // ---------- form of payment ----------
  function maskCard(num){
    return 'X'.repeat(Math.max(0, num.length-4)) + num.slice(-4);
  }

  // ---------- PNR element display / cancel ----------
  // Resolves a DOCS entry's traveler to a Sabre-style "P1"/"P1.1" label + display
  // name - infants have no name-field entry of their own, so P{n}.{m} means the
  // m-th infant travelling with passenger n (see addDocs).
  function resolveDocTraveler(paxNum, infantNum){
    const adultName = state.pnr.names[paxNum-1];
    if(!infantNum) return { label: `${paxNum}`, name: adultName || '?' };
    const adultInfants = state.pnr.infants.filter(inf => inf.adult === adultName);
    const inf = adultInfants[infantNum-1];
    return { label: `${paxNum}.${infantNum}`, name: inf ? `${inf.surname}/${inf.given} (INFANT)` : '?' };
  }

  // Indices (into `segments`) of every OTHER segment sharing segments[idx]'s marriedGroup -
  // empty if that segment isn't married. Shared by buildElements' display text and
  // cancelElements' enforcement below.
  function marriedPartnerIndices(segments, idx){
    const group = segments[idx].marriedGroup;
    if(!group) return [];
    const partners = [];
    segments.forEach((s,i) => { if(i !== idx && s.marriedGroup === group) partners.push(i); });
    return partners;
  }

  function buildElements(){
    const els = [];
    state.pnr.names.forEach((n, i) => els.push({ kind:'name', idx:i, label:`NM${i+1}`, text:n }));
    state.pnr.infants.forEach((inf, i) => els.push({ kind:'infant', idx:i, label:'IN', text:`${inf.surname}/${inf.given}  DOB ${inf.dob}  (INFANT - TRAVELS WITH ${inf.adult})` }));
    state.pnr.docs.forEach((d, i) => { const t = resolveDocTraveler(d.pax, d.infantNum); els.push({ kind:'docs', idx:i, label:'DOC', text:`${d.desc} ${d.country} ${d.number}  NATIONALITY ${d.nationality}  DOB ${d.dob}  ${d.sex}  EXP ${d.expiry}  PAX ${t.label} (${t.name})` }); });
    state.pnr.segments.forEach((s, i) => {
      const partners = marriedPartnerIndices(state.pnr.segments, i).map(j => `SEG${j+1}`);
      const marriedNote = partners.length ? `  MARRIED TO ${partners.join(',')}` : '';
      els.push({ kind:'segment', idx:i, label:`SEG${i+1}`, text: formatSegmentShort(s) + `  ${s.dinfo.weekday}` + marriedNote });
    });
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

  // ---------- PNR dock panel (GUI, browser-only) ----------
  // Mirrors buildElements()/state.lastDisplay into the persistent side dock -
  // pure rendering, no state mutation. See notes/GUI Expansion Scope-Out.md.
  function renderPnrPanel(){
    dockStatus.textContent = state.signedIn
      ? `SIGNED IN - SINE ${state.sine}  PCC ${state.pcc}`
      : 'NOT SIGNED IN';
    dockRloc.textContent = `RLOC: ${state.pnr.locator || '(NOT SAVED)'}`;
    dockPnrBody.innerHTML = '';
    if(state.lastDisplay.length === 0){
      dockPnrBody.textContent = 'PNR IS EMPTY';
      return;
    }
    for(const e of state.lastDisplay){
      const row = document.createElement('div');
      row.className = 'docklinerow';
      row.textContent = `${pad(e.num,2)} ${pad(e.label,5)} ${e.text}`;
      dockPnrBody.appendChild(row);
    }
  }

  function refreshAndPrintPNR(){
    state.lastDisplay = buildElements();
    renderPnrPanel();
    refreshSeatMapPanelIfOpen();
    printBlank();
    print(`RLOC: ${state.pnr.locator || '(NOT SAVED - END TRANSACT TO STORE)'}`, 'hd');
    if(state.lastDisplay.length === 0){
      print('  ** PNR IS EMPTY **', 'dim');
      return;
    }
    for(const e of state.lastDisplay){
      print(` ${pad(e.num,2)}  ${pad(e.label,5)} ${e.text}`);
    }
    // Naturally stops once the agent re-prices (WP) - reuses the existing pricing-null-
    // means-stale convention rather than a separate acknowledgement flag.
    const changedSegs = state.pnr.segments.filter(s => s.scheduleChanged);
    if(!state.pnr.pricing && changedSegs.length){
      printBlank();
      print('** SCHEDULE CHANGE ON FILE - RE-PRICE (WP), THEN EXCHANGE (WFR) OR REISSUE (TKTT) **', 'err');
      for(const s of changedSegs){ print(`  ${formatSegmentShort(s)}`, 'dim'); }
    }
    // A fresh re-price already exists and there's still a prior ticket to apply toward it -
    // ready for WFR{TICKET#}.
    if(state.pnr.pricing && state.pnr.priorTickets.length){
      printBlank();
      print('** PRIOR TICKET ON FILE - EXCHANGE WITH WFR{TICKET#} OR REISSUE FRESH WITH TKTT **', 'dim');
      for(const t of state.pnr.priorTickets){ print(`  ${t.passenger}${t.isInfant ? ' (INF)' : ''}  ${t.ticketNum}`, 'dim'); }
    }
    // Show-once (not show-until-resolved like the schedule-change alert above): clearing a
    // waitlist needs no follow-up action, so this fires on the next redisplay after clearing
    // (most likely QN18 or *{LOCATOR}) and never again - waitlistClearAcked is set as part of
    // this same print pass.
    const clearedSegs = state.pnr.segments.filter(s => s.waitlistCleared && !s.waitlistClearAcked);
    if(clearedSegs.length){
      printBlank();
      print('** WAITLIST CLEARED - SEGMENT(S) NOW CONFIRMED **', 'hd');
      for(const s of clearedSegs){ print(`  ${formatSegmentShort(s)}`, 'dim'); s.waitlistClearAcked = true; }
    }
  }

  function removeElement(e){
    if(e.kind === 'name') state.pnr.names.splice(e.idx, 1);
    else if(e.kind === 'infant') state.pnr.infants.splice(e.idx, 1);
    else if(e.kind === 'docs') state.pnr.docs.splice(e.idx, 1);
    else if(e.kind === 'remark') state.pnr.remarks.splice(e.idx, 1);
    else if(e.kind === 'segment'){
      state.pnr.segments.splice(e.idx, 1);
      clearPricingAndTickets(state.pnr);
      state.pnr.seats = state.pnr.seats
        .filter(st => st.segIdx !== e.idx)
        .map(st => st.segIdx > e.idx ? { segIdx: st.segIdx - 1, seat: st.seat } : st);
    }
    else if(e.kind === 'seat') state.pnr.seats.splice(e.idx, 1);
    else if(e.kind === 'ssr') state.pnr.ssrs.splice(e.idx, 1);
    else if(e.kind === 'osi') state.pnr.osis.splice(e.idx, 1);
    else if(e.kind === 'fq') clearPricingAndTickets(state.pnr);
    else if(e.kind === 'phone') state.pnr.phones.splice(e.idx, 1);
    else if(e.kind === 'rf') state.pnr.receivedFrom = null;
    else if(e.kind === 'fp') state.pnr.formOfPayment = null;
    else if(e.kind === 'tk') state.pnr.ticketing = null;
    else if(e.kind === 'tkt') state.pnr.tickets.splice(e.idx, 1);
  }

  function cancelElements(nums){
    const uniqDesc = Array.from(new Set(nums)).sort((a,b) => b-a);

    // Married segments must be cancelled together - block the whole command (no partial
    // cancellation) if a request names only some of a married group's currently-displayed
    // element numbers.
    for(const n of uniqDesc){
      const e = state.lastDisplay.find(x => x.num === n);
      if(!e || e.kind !== 'segment') continue;
      for(const partnerIdx of marriedPartnerIndices(state.pnr.segments, e.idx)){
        const partnerEl = state.lastDisplay.find(x => x.kind === 'segment' && x.idx === partnerIdx);
        if(partnerEl && !uniqDesc.includes(partnerEl.num)){
          printErr(`UNABLE TO CANCEL - ELEMENT ${n} IS MARRIED TO ELEMENT ${partnerEl.num} - CANCEL BOTH TOGETHER (X${n},${partnerEl.num})`);
          return;
        }
      }
    }

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
    clearPricingAndTickets(state.pnr);
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
    prior_tickets: () => state.pnr.priorTickets,
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

  // Real airline schedule changes are airline-initiated, not something an agent types - the
  // honest equivalent in a single-user trainer is a one-time, deterministic seeded check per
  // segment. Seeded off flight+route+date identity only (NOT the PNR's locator, which is
  // genuinely random per genLocator()) so the same flight+route+date always gives the same
  // outcome regardless of which PNR it ends up on - matching real life (a schedule change
  // happens to a flight, affecting every booking on it, not to one lucky/unlucky PNR) and
  // keeping this reproducible for training/testing instead of varying every run. The
  // scheduleChanged flag (not the seed) is what stops it from re-firing on a later save of
  // the same segment. The mutation itself has no dedicated print (no "an airline changed
  // your flight" banner) - it's auto-queued to queue "1" (SCHEDULE CHANGE, spec/reference-
  // data.json's queueCategories) and only surfaces via the ordinary channels a real agent
  // already checks: QC/QN1, or the alert refreshAndPrintPNR prints below whenever a redisplay
  // (ER's own, *R, or after QN1) shows an unpriced, changed segment. ET's redisplay is skipped
  // (work area cleared instead), so ET alone doesn't reveal it - a later *{LOCATOR}/QN1 does.
  function applyScheduleChanges(p){
    let anyChanged = false;
    for(const seg of p.segments){
      if(seg.scheduleChanged) continue;
      const seed = hashStr(`SKEDCHG${seg.airline}${seg.flightNum}${seg.orig}${seg.dest}${seg.dinfo.day}${seg.dinfo.mon}${seg.dinfo.year}`);
      const rng = mulberry32(seed);
      if(rng() >= SCHEDULE_CHANGE.chance) continue;
      const magnitude = SCHEDULE_CHANGE.minShiftMinutes + Math.floor(rng()*(SCHEDULE_CHANGE.maxShiftMinutes - SCHEDULE_CHANGE.minShiftMinutes));
      const shift = (rng() < 0.5 ? -1 : 1) * magnitude;
      seg.dep += shift;
      seg.arr += shift;
      seg.scheduleChanged = true;
      logActivity(`SCHEDULE CHANGE - ${seg.airline}${seg.flightNum} ${seg.orig}${seg.dest} NOW ${minutesToClock(seg.dep)}-${minutesToClock(seg.arr)}`);
      anyChanged = true;
    }
    if(anyChanged){
      clearPricingAndTickets(p);
      if(!state.queues['1']) state.queues['1'] = [];
      if(!state.queues['1'].includes(p.locator)) state.queues['1'].push(p.locator);
    }
  }

  // Same deterministic-seeded-check-at-save-time pattern as applyScheduleChanges, for
  // queueCategories["18"] (WAITLIST CLEARED) - previously unused, same as "1" was. Deltas
  // from schedule change: (1) flips seg.status HL->HK instead of shifting dep/arr - same
  // flight/class/fare, not an itinerary change, so pricing/tickets are never touched here;
  // (2) the seed includes seg.cls (waitlist status is class-specific) and uses a distinct
  // hash prefix so it can never collide with schedule change's seed for the same flight;
  // (3) no idempotency flag is needed to gate the roll itself - only currently-HL segments
  // are considered, and a cleared segment becomes HK immediately, so it naturally drops out.
  // waitlistCleared/waitlistClearAcked exist only to drive the show-once notice in
  // refreshAndPrintPNR below, not to gate this function.
  function applyWaitlistClearing(p){
    for(const seg of p.segments){
      if(seg.status !== 'HL') continue;
      const seed = hashStr(`WLCLEAR${seg.airline}${seg.flightNum}${seg.orig}${seg.dest}${seg.cls}${seg.dinfo.day}${seg.dinfo.mon}${seg.dinfo.year}`);
      const rng = mulberry32(seed);
      if(rng() >= WAITLIST_CLEAR.chance) continue;
      seg.status = 'HK';
      seg.waitlistCleared = true;
      seg.waitlistClearAcked = false;
      logActivity(`WAITLIST CLEARED - ${seg.airline}${seg.flightNum} ${seg.orig}${seg.dest} ${seg.cls} NOW CONFIRMED (WAS WAITLISTED)`);
      if(!state.queues['18']) state.queues['18'] = [];
      if(!state.queues['18'].includes(p.locator)) state.queues['18'].push(p.locator);
    }
  }

  function endTransaction(mode){
    const p = state.pnr;
    const incomplete = firstIncompleteMessage('end_transaction');
    if(incomplete){ printErr(incomplete); return; }

    if(!p.locator) p.locator = genLocator();
    applyScheduleChanges(p);
    applyWaitlistClearing(p);
    logActivity(`PNR SAVED (${mode}) - RLOC ${p.locator}`);
    state.history[p.locator] = JSON.parse(JSON.stringify(p));

    const now = new Date();
    const ts = `${pad(now.getDate(),2).trim()}${MONTHS[now.getMonth()]}  ${minutesToClock(now.getHours()*60+now.getMinutes())}`;
    print('END OF TRANSACTION COMPLETE', 'hd');
    print(`  ${ts}   RLOC: ${p.locator}`);

    if(EMAIL_DOCUMENTS[mode]){
      const doc = buildItineraryDocument(mode);
      print(`${EMAIL_DOCUMENTS[mode].label} DOCUMENT GENERATED - OPENING PRINT VIEW`, 'dim');
      logActivity(`${EMAIL_DOCUMENTS[mode].label} DOCUMENT SENT (${mode})`);
      openItineraryDocument(doc);
    }

    if(mode === 'ET' || EMAIL_DOCUMENTS[mode]){
      state.pnr = freshPNR();
      state.lastDisplay = [];
      renderPnrPanel();
      refreshSeatMapPanelIfOpen();
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

  // ---------- divide (SP) ----------
  // Only `names` (by array index) and `docs` (an explicit pax index) are unambiguously
  // per-passenger in this PNR model - infants link only by matching adult name string,
  // seats link only to a segment (not a passenger) and aren't reliably attributable, and
  // SSRs bake any pax number into free text only. So: names/infants(by adult name)/docs
  // (reindexed, same pattern as seat.segIdx after a segment cancel) move to the new PNR;
  // segments/phones/receivedFrom/remarks/osis/ssrs/formOfPayment/ticketing are copied
  // (real Sabre divide keeps the itinerary in both resulting PNRs); seats are dropped from
  // the new PNR (no passenger attribution to decide which seat goes where).
  function dividePnr(numsStr){
    const p = state.pnr;
    const incomplete = firstIncompleteMessage('divide_pnr');
    if(incomplete){ printErr(incomplete); return; }

    const uniq = Array.from(new Set(numsStr.split(',').map(s => parseInt(s,10))));
    for(const n of uniq){
      if(!n || n < 1 || n > p.names.length){ printErr('INVALID PASSENGER NUMBER - CHECK ENTRY AND REENTER'); return; }
    }
    if(uniq.length >= p.names.length){ printErr('UNABLE TO DIVIDE - AT LEAST ONE PASSENGER MUST REMAIN'); return; }

    const uniqDesc = uniq.slice().sort((a,b) => b-a);
    const removed = [];
    for(const n of uniqDesc){
      const idx = n-1;
      removed.push({ idx, name: p.names[idx] });
      p.names.splice(idx, 1);
    }
    removed.reverse();
    const movedNames = removed.map(r => r.name);
    const removedIdxSet = new Set(removed.map(r => r.idx));
    const removedIdxAsc = Array.from(removedIdxSet).sort((a,b) => a-b);
    const idxToNewPax = {};
    removed.forEach((r,i) => { idxToNewPax[r.idx] = i+1; });

    const movedInfants = [];
    p.infants = p.infants.filter(inf => {
      if(movedNames.includes(inf.adult)){ movedInfants.push(inf); return false; }
      return true;
    });

    const movedDocs = [];
    const remainingDocs = [];
    for(const d of p.docs){
      const originalIdx = d.pax - 1;
      if(removedIdxSet.has(originalIdx)){
        movedDocs.push({ ...d, pax: idxToNewPax[originalIdx] });
      } else {
        const shift = removedIdxAsc.filter(ri => ri < originalIdx).length;
        remainingDocs.push({ ...d, pax: originalIdx - shift + 1 });
      }
    }
    p.docs = remainingDocs;

    const newPnr = freshPNR();
    newPnr.names = movedNames;
    newPnr.infants = movedInfants;
    newPnr.docs = movedDocs;
    newPnr.segments = JSON.parse(JSON.stringify(p.segments));
    newPnr.phones = JSON.parse(JSON.stringify(p.phones));
    newPnr.receivedFrom = p.receivedFrom;
    newPnr.remarks = JSON.parse(JSON.stringify(p.remarks));
    newPnr.osis = JSON.parse(JSON.stringify(p.osis));
    newPnr.ssrs = JSON.parse(JSON.stringify(p.ssrs));
    newPnr.formOfPayment = p.formOfPayment ? JSON.parse(JSON.stringify(p.formOfPayment)) : null;
    newPnr.ticketing = p.ticketing;
    newPnr.locator = genLocator();
    newPnr.activityLog = [{ stamp: nowStamp(), sine: state.sine || '----', text: `PNR CREATED - DIVIDED FROM RLOC ${p.locator}` }];
    state.history[newPnr.locator] = JSON.parse(JSON.stringify(newPnr));

    invalidatePricing();

    print('** PNR DIVIDED **', 'hd');
    print(`  NEW RLOC: ${newPnr.locator} - ${movedNames.join(', ')}`);
    print('  ORIGINAL RLOC RETAINED - RE-SAVE WITH ER TO UPDATE', 'dim');
    logActivity(`PNR DIVIDED - ${movedNames.join(', ')} TO NEW RLOC ${newPnr.locator}`);
    refreshAndPrintPNR();
  }

  // ---------- queues (QE/QN/QC) ----------
  function queueEnqueue(numStr){
    const p = state.pnr;
    const incomplete = firstIncompleteMessage('queue_place');
    if(incomplete){ printErr(incomplete); return; }

    const num = String(parseInt(numStr, 10));
    if(!state.queues[num]) state.queues[num] = [];
    if(!state.queues[num].includes(p.locator)) state.queues[num].push(p.locator);

    print(`PNR ${p.locator} QUEUED TO QUEUE ${num}`);
    logActivity(`QUEUED TO QUEUE ${num}`);

    state.pnr = freshPNR();
    state.lastDisplay = [];
    renderPnrPanel();
    refreshSeatMapPanelIfOpen();
    print('WORK AREA CLEARED - READY FOR NEXT ENTRY', 'dim');
  }

  function queueNext(numStr){
    const num = String(parseInt(numStr, 10));
    const q = state.queues[num] || [];
    if(q.length === 0){ print(`END OF QUEUE ${num} - NO PNRS REMAINING`, 'dim'); return; }

    const loc = q.shift();
    const rec = state.history[loc];
    if(!rec){ printErr(`QUEUE ${num} REFERENCED UNKNOWN RECORD ${loc}`); return; }

    state.pnr = JSON.parse(JSON.stringify(rec));
    print(`PNR ${loc} RETRIEVED FROM QUEUE ${num} - ${q.length} REMAINING`);
    logActivity(`RETRIEVED FROM QUEUE ${num}`);
    refreshAndPrintPNR();
  }

  function queueCount(numStr){
    const nums = numStr
      ? [String(parseInt(numStr, 10))]
      : Object.keys(state.queues).filter(n => state.queues[n].length > 0).sort((a, b) => Number(a) - Number(b));

    if(nums.length === 0){ print('NO QUEUES WITH PNRS ON FILE', 'dim'); return; }

    print(`QUEUE COUNT - PCC ${state.pcc || '----'}`, 'hd');
    for(const n of nums){
      const count = (state.queues[n] || []).length;
      const label = QUEUE_CATEGORIES[n] ? `  ${QUEUE_CATEGORIES[n]}` : '';
      print(`  Q${pad(n, 4)}${pad(String(count), 4)}${label}`);
    }
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
    // Reissuing fresh (rather than exchanging via WFR) means any pending exchange
    // opportunity is moot - don't leave it lingering.
    p.priorTickets = [];
    p.priorPricing = null;
    refreshAndPrintPNR();
  }

  function voidTickets(){
    const p = state.pnr;
    const incomplete = firstIncompleteMessage('void_tickets');
    if(incomplete){ printErr(incomplete); return; }

    print('** TICKET(S) VOIDED **', 'hd');
    for(const t of p.tickets){
      print(`  ${pad(t.passenger + (t.isInfant ? ' (INF)' : ''), 28)} ${t.ticketNum}`);
    }
    const count = p.tickets.length;
    p.tickets = [];
    logActivity(`TICKET(S) VOIDED - ${count} TICKET(S)`);
    refreshAndPrintPNR();
  }

  function refundTickets(){
    const p = state.pnr;
    const incomplete = firstIncompleteMessage('refund_tickets');
    if(incomplete){ printErr(incomplete); return; }

    const rules = FARE_RULES[p.segments[0].cls] || null;
    if(rules && !rules.refundable){ printErr('UNABLE TO REFUND - NONREFUNDABLE FARE BASIS'); return; }

    const amount = p.pricing ? p.pricing.total : 0;
    print('** TICKET(S) REFUNDED **', 'hd');
    for(const t of p.tickets){
      print(`  ${pad(t.passenger + (t.isInfant ? ' (INF)' : ''), 28)} ${t.ticketNum}`);
    }
    print(`REFUND AMOUNT: USD ${amount.toFixed(2)}`, 'dim');
    const count = p.tickets.length;
    p.tickets = [];
    p.pricing = null;
    logActivity(`TICKET(S) REFUNDED - ${count} TICKET(S), USD ${amount.toFixed(2)}`);
    refreshAndPrintPNR();
  }

  // Real Sabre's "WFR{TICKET#}" starts an exchange against an already-issued ticket, applies
  // its value toward the newly re-priced itinerary, and either collects a difference
  // (ADCOLL) or leaves a residual, before reissuing. Real Sabre's full process is a heavier
  // multi-step workflow (WFR -> an auto-priced price-quote record -> a separate reissue
  // commit entry); this is a deliberately simplified single-entry version that keeps the
  // real training value (apply old value, show ADCOLL/residual, reissue) without simulating
  // that machinery.
  function exchangeTicket(ticketNum){
    const p = state.pnr;
    const incomplete = firstIncompleteMessage('exchange_ticket');
    if(incomplete){ printErr(incomplete); return; }

    const oldTicket = p.priorTickets.find(t => t.ticketNum === ticketNum);
    if(!oldTicket){ printErr('INVALID TICKET NUMBER - CHECK ENTRY AND REENTER'); return; }

    const diff = Math.round((p.pricing.total - p.priorPricing.total) * 100) / 100;

    const validatingCarrier = p.segments[0].airline;
    const numericCode = AIRLINE_NUMERIC_CODES[validatingCarrier] || '000';
    const newTickets = [];
    for(const name of p.names){
      // Distinct seed input (the old ticket number) so the reissue gets a fresh number -
      // genTicketNumber(locator, name) alone would regenerate the same one as before.
      const serial = genTicketNumber(p.locator, `${name}EXCH${oldTicket.ticketNum}`);
      newTickets.push({ passenger: name, ticketNum: `${numericCode}-${serial}`, isInfant:false });
    }
    for(const inf of p.infants){
      const identifier = `${inf.surname}/${inf.given}`;
      const serial = genTicketNumber(p.locator, `${identifier}EXCH${oldTicket.ticketNum}`);
      newTickets.push({ passenger: identifier, ticketNum: `${numericCode}-${serial}`, isInfant:true });
    }
    p.tickets = newTickets;
    p.priorTickets = [];
    p.priorPricing = null;

    print('** EXCHANGE PROCESSED **', 'hd');
    print(`  ORIGINAL TICKET: ${oldTicket.ticketNum}   NEW FARE BASIS: ${p.pricing.fareBasis}`, 'dim');
    if(diff > 0) print(`  ADDITIONAL COLLECTION (ADCOLL): USD ${diff.toFixed(2)}`);
    else if(diff < 0) print(`  RESIDUAL VALUE: USD ${(-diff).toFixed(2)} (NON-REFUNDABLE PER FARE RULES)`, 'dim');
    else print('  EVEN EXCHANGE - NO ADDITIONAL COLLECTION');
    for(const t of p.tickets){
      print(`  ${pad(t.passenger + (t.isInfant ? ' (INF)' : ''), 28)} ${t.ticketNum}`);
    }
    logActivity(`TICKET EXCHANGED - ${oldTicket.ticketNum} -> ${p.tickets.map(t=>t.ticketNum).join(', ')}, ${diff>=0?'ADCOLL':'RESIDUAL'} USD ${Math.abs(diff).toFixed(2)}`);
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
    print('SCHEDULE', 'hd');
    print('  S{DD}{MMM}{ORG}{DST}   Flight schedule, 7-day window from the given date -');
    print('                         times/equipment only, no booking classes or seats   e.g. S15AUGDFWORD');
    printBlank();
    print('FARES', 'hd');
    print('  FQ{ORG}{DST}   Fare quote shop by city pair - indicative only, no PNR needed   e.g. FQDFWORD');
    printBlank();
    print('SELL', 'hd');
    print('  0{LN}{CLASS}{SEATS}                        Sell from avail line   e.g. 04Y1');
    print('  0{SEATS}{CLASS}{LN}{CLASS}{LN}             Sell a connection (two avail lines)   e.g. 02Y1M2');
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
    print('  TKTV     Void issued ticket(s) - same-day reversal, no penalty. Fare quote');
    print('           and ticketing arrangement stay on file, so TKTT can reissue right away.');
    print('  TKTR     Refund issued ticket(s) - clears the fare quote too (re-price with WP');
    print('           before reissuing). Blocked for a nonrefundable fare basis.');
    print('  WFR{TICKET#}   Exchange a previously issued ticket after a fare/itinerary');
    print('                 change - applies the old ticket\'s value toward the freshly');
    print('                 re-priced total (WP first), shows ADCOLL/residual, reissues.');
    printBlank();
    print('SPECIAL SERVICE / OTHER SERVICE INFO', 'hd');
    print('  3{SSRCODE}[-{PAX#}][/{TEXT}]   Special service request   e.g. 3VGML  or  3WCHR-1/AISLE SEAT');
    print('  3OSI{AL}{TEXT}                 Other service info   e.g. 3OSIAA VIP PASSENGER');
    print('  3FQTV{AL}{NUMBER}[/{TIER}]     Frequent flyer number, optional tier   e.g. 3FQTVAA1234567 or 3FQTVAA1234567/GLD');
    print('                                  Tiers: SLV GLD PLT DIA', 'dim');
    print('  SSR codes: WCHR WCHS WCHC VGML BBML CHML KSML MOML DBML BLND DEAF UMNR PETC BSCT SPML XBAG', 'dim');
    printBlank();
    print('PASSENGER DOCUMENTS (APIS)', 'hd');
    print('  3DOCS{TYPE}/{COUNTRY}/{NUMBER}/{NATIONALITY}/{DOB}/{SEX}/{EXPIRY}-{PAX#}[.{INFANT#}]');
    print('    e.g. 3DOCSP/US/123456789/US/12JAN90/M/25DEC30-1', 'dim');
    print('    infant e.g. 3DOCSP/US/123456789/US/12JAN26/M/25DEC30-1.1  (1st infant travelling with PAX 1)', 'dim');
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
    print('  SP{N}  or  SP{N},{M}   Divide passenger(s) into a new PNR   e.g. SP2 or SP2,3');
    print('                         Itinerary/contact/ticketing fields are copied to the new');
    print('                         PNR; both PNRs then need a fresh fare quote (WP).');
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
    renderPnrPanel();
  }

  function signOut(){
    print('SIGNED OFF', 'hd');
    state.signedIn = false;
    state.sine = null;
    state.pcc = null;
    renderPnrPanel();
    switchDockTab('pnr');
  }

  // ---------- boot ----------
  function boot(){
    print('G*D*S*  T*R*A*I*N*E*R*  -----------------------------------------------', 'hd');
    print('                        GLOBAL DISTRIBUTION SYSTEM - TERMINAL EMULATION');
    print('                        -----------------------------------------------');
    printBlank();
    print('NOT SIGNED IN', 'dim');
    print('TYPE SI TO SIGN IN   ·   HELP FOR COMMAND REFERENCE', 'dim');
    renderPnrPanel();
    refreshSeatMapPanelIfOpen();
  }
  // called at the bottom of this file, once the dock DOM refs below are
  // declared - boot() touches them via renderPnrPanel()/refreshSeatMapPanelIfOpen().

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

  function addDocs(type, country, number, nationality, dob, sex, expiry, paxStr, infantStr){
    const desc = DOCUMENT_TYPES[type];
    if(!desc){ printErr(`UNKNOWN DOCUMENT TYPE ${type} - VALID: ${Object.keys(DOCUMENT_TYPES).join(' ')}`); return; }
    const paxNum = parseInt(paxStr,10);
    if(!paxNum || paxNum < 1 || paxNum > state.pnr.names.length){ printErr('INVALID PASSENGER NUMBER - CHECK NAME FIELD'); return; }
    let infantNum = null;
    if(infantStr){
      infantNum = parseInt(infantStr,10);
      const adultInfants = state.pnr.infants.filter(inf => inf.adult === state.pnr.names[paxNum-1]);
      if(!infantNum || infantNum < 1 || infantNum > adultInfants.length){
        printErr(`INVALID INFANT NUMBER - PASSENGER ${paxNum} (${state.pnr.names[paxNum-1]}) HAS ${adultInfants.length} INFANT(S) ON FILE`); return;
      }
    }
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
    const entry = { type, desc, country, number, nationality, dob, sex, expiry, pax: paxNum, infantNum };
    state.pnr.docs.push(entry);
    const t = resolveDocTraveler(paxNum, infantNum);
    const text = `${desc} ${country} ${number}  NATIONALITY ${nationality}  DOB ${dob}  ${sex}  EXP ${expiry}  PAX ${t.label} (${t.name})`;
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
    renderPnrPanel();
    refreshSeatMapPanelIfOpen();
    print('IGNORED - PNR NOT SAVED');
  }

  // handler token (from COMMAND_GRAMMAR, shared with the CLI edition) -> local function.
  // Every handler is called as handler(rawMatchedString, ...captureGroups) so the dispatch
  // loop below stays fully generic - see spec/README.md.
  const HANDLERS = {
    SIGN_OUT: () => signOut(),
    HELP: () => showHelp(),
    AVAILABILITY: (raw, day, mon, orig, dest) => genAvailability(day, mon, orig, dest),
    SCHEDULE_DISPLAY: (raw, day, mon, orig, dest) => genSchedule(day, mon, orig, dest),
    SELL_FROM_AVAIL: (raw, line, cls, seats) => sellFromAvail(parseInt(line,10), cls, parseInt(seats,10)),
    SELL_CONNECTION: (raw, seats, cls1, line1, cls2, line2) => sellConnection(parseInt(seats,10), cls1, parseInt(line1,10), cls2, parseInt(line2,10)),
    LONG_SELL: (raw, al, flt, cls, day, mon, orig, dest, status, seats) => directSell(al, flt, cls, day, mon, orig, dest, status, parseInt(seats,10)),
    NAME_FIELD: (raw) => handleName(raw),
    PHONE: (raw) => handlePhone(raw),
    RECEIVED_FROM: (raw) => handleReceivedFrom(raw),
    GENERAL_REMARK: (raw) => handleGeneralRemark(raw),
    PRICE_ITINERARY: (raw, mode, corpCode) => priceItinerary(mode, corpCode),
    FARE_QUOTE_SHOP: (raw, orig, dest) => fareQuoteShop(orig, dest),
    TICKETING_AT_WILL: () => addTicketingAtWill(),
    TICKETING_AT_WILL_DATED: (raw, day, mon, time) => addTicketingAtWillDated(day, mon, time),
    TICKETING_TIME_LIMIT: (raw, day, mon, time) => addTicketingTimeLimit(day, mon, time),
    FOP_CASH: () => addFopCash(),
    FOP_CHECK: () => addFopCheck(),
    FOP_CREDIT_CARD: (raw, type, num, mm, yy) => addFopCreditCard(type, num, mm, yy),
    ISSUE_TICKETS: () => issueTickets(),
    VOID_TICKETS: () => voidTickets(),
    REFUND_TICKETS: () => refundTickets(),
    EXCHANGE_TICKET: (raw, ticketNum) => exchangeTicket(ticketNum),
    DOCS: (raw, type, country, number, nationality, dob, sex, expiry, pax, infant) => addDocs(type, country, number, nationality, dob, sex, expiry, pax, infant),
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
    DIVIDE_PNR: (raw, nums) => dividePnr(nums),
    QUEUE_ENQUEUE: (raw, n) => queueEnqueue(n),
    QUEUE_NEXT: (raw, n) => queueNext(n),
    QUEUE_COUNT: (raw, n) => queueCount(n),
    CANCEL_ITINERARY: () => cancelItinerary(),
    CANCEL_ELEMENTS: (raw, rangeStr) => handleCancel(rangeStr),
    IGNORE: () => ignorePnr(),
    END_TRANSACT_ER: () => endTransaction('ER'),
    END_TRANSACT_ET: () => endTransaction('ET'),
    END_TRANSACT_EM: () => endTransaction('EM'),
    END_TRANSACT_EMI: () => endTransaction('EMI'),
    END_TRANSACT_EMT: () => endTransaction('EMT'),
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
  // Shared by the Enter-key handler and any GUI affordance (e.g. clicking a seat
  // in the seat map panel) that wants to submit a command through the real
  // dispatcher, rather than mutating state directly - see notes/GUI Expansion
  // Scope-Out.md's guiding constraint.
  function submitCommand(raw){
    print('> ' + raw.toUpperCase(), 'echo');
    if(raw.trim().length){
      state.cmdHistory.push(raw);
      state.cmdHistoryIdx = state.cmdHistory.length;
    }
    inputEl.value = '';
    try{ processCommand(raw); } catch(err){ printErr('SYSTEM ERROR - ' + err.message); }
    screenEl.scrollTop = screenEl.scrollHeight;
  }

  inputEl.addEventListener('keydown', (e) => {
    if(e.key === 'Enter'){
      submitCommand(inputEl.value);
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
    state.history = {}; state.queues = {}; state.cmdHistory = []; state.cmdHistoryIdx = -1;
    boot();
    inputEl.focus();
  });

  // ---------- settings panel ----------
  const shellEl = document.getElementById('shell');
  const settingsPanel = document.getElementById('settingsPanel');
  const btnSettings = document.getElementById('btnSettings');
  const btnToggleDock = document.getElementById('btnToggleDock');
  const SETTINGS_KEY = 'gdsTrainerSettings';
  const DEFAULT_SETTINGS = { theme:'green', scanlines:true, glow:'med', vignette:true, fontSize:'md', dockVisible:true };

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
    shellEl.classList.toggle('dock-hidden', !settings.dockVisible);
    btnToggleDock.classList.toggle('active', settings.dockVisible);
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
  btnToggleDock.addEventListener('click', () => {
    settings.dockVisible = !settings.dockVisible;
    applySettings(); saveSettings();
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

  // ---------- dock wiring (PNR / seat map / lookup / format finder tabs) ----------
  const dockPnrTab = document.getElementById('dockPnrTab');
  const dockStatus = document.getElementById('dockStatus');
  const dockRloc = document.getElementById('dockRloc');
  const dockPnrBody = document.getElementById('dockPnrBody');
  const seatMapPanel = document.getElementById('seatMapPanel');
  const seatMapTitle = document.getElementById('seatMapTitle');
  const seatMapGrid = document.getElementById('seatMapGrid');
  const seatMapLegend = document.getElementById('seatMapLegend');
  const lookupPanel = document.getElementById('lookupPanel');
  const lookupInput = document.getElementById('lookupInput');
  const lookupResults = document.getElementById('lookupResults');
  const formatsPanel = document.getElementById('formatsPanel');
  const formatsInput = document.getElementById('formatsInput');
  const formatsResults = document.getElementById('formatsResults');

  // Data-driven so adding another dock tab is a one-line addition here rather
  // than another parallel if/else + classList.toggle pair.
  const DOCK_TABS = {
    pnr:     { btn: document.getElementById('dockTabPnr'),     panel: dockPnrTab },
    seat:    { btn: document.getElementById('dockTabSeat'),    panel: seatMapPanel },
    lookup:  { btn: document.getElementById('dockTabLookup'),  panel: lookupPanel },
    formats: { btn: document.getElementById('dockTabFormats'), panel: formatsPanel },
  };

  // Guards the 'seat' tab against showing stale content - a click on the tab
  // button itself (unlike showSeatMap/refreshSeatMapPanelIfOpen) never re-checks
  // whether a PNR/segment is actually behind whatever was last rendered there,
  // so without this a signed-out or freshly-cleared session could still flip
  // the panel back open showing a previous PNR's seat map.
  function switchDockTab(tab){
    if(tab === 'seat'){
      const segIdx = parseInt(seatMapPanel.dataset.segIdx, 10);
      if(!state.signedIn || !state.pnr.segments[segIdx]) tab = 'pnr';
    }
    for(const key in DOCK_TABS){
      DOCK_TABS[key].panel.classList.toggle('hidden', key !== tab);
      DOCK_TABS[key].btn.classList.toggle('active', key === tab);
    }
  }
  for(const key in DOCK_TABS){
    DOCK_TABS[key].btn.addEventListener('click', () => switchDockTab(key));
  }
  switchDockTab('pnr');

  function dockSectionHead(text){
    const h = document.createElement('div');
    h.className = 'dock-section-head';
    h.textContent = text;
    return h;
  }

  // ---------- encode/decode lookup panel (GUI, browser-only) ----------
  // Live search over the same AIRPORTS/AIRLINES data DC/DAN already use -
  // mirrors real Sabre's "Encode/Decode" sidebar tool. Airport rows run the
  // real DC{code} command via submitCommand() when clicked - safe to do
  // without violating the "GUI must not offer a point-and-click alternative
  // to typing the entry" rule in notes/GUI Expansion Scope-Out.md, since DC
  // is read-only and mutates no state, unlike PNR-building commands. Airline
  // rows have no backing decode command, so they're display-only.
  // Ranks a code/name/city match so an exact or prefix code match (what
  // someone decoding a known 3-letter code is almost always after) always
  // surfaces above an incidental substring hit elsewhere - e.g. searching
  // "ORD" should rank Chicago O'Hare first, not bury it past the result cap
  // behind unrelated cities that merely contain "ord" (Alamogordo, Oxford...).
  function lookupMatchRank(code, term, ...names){
    if(code === term) return 0;
    if(code.startsWith(term)) return 1;
    if(names.some(n => n.startsWith(term))) return 2;
    if(code.includes(term)) return 3;
    if(names.some(n => n.includes(term))) return 4;
    return null;
  }

  function renderLookupResults(rawTerm){
    const term = rawTerm.trim().toUpperCase();
    lookupResults.innerHTML = '';
    if(term.length < 2){
      lookupResults.innerHTML = '<div class="dim lookup-hint">TYPE AT LEAST 2 CHARACTERS - A 3-LETTER CODE OR A CITY/AIRPORT/AIRLINE NAME</div>';
      return;
    }
    let airportMatches = [];
    if(typeof AIRPORTS !== 'undefined'){
      for(const code in AIRPORTS){
        const a = AIRPORTS[code];
        const rank = lookupMatchRank(code, term, a[0].toUpperCase(), a[1].toUpperCase());
        if(rank !== null) airportMatches.push({ code, name:a[0], city:a[1], country:a[2], rank });
      }
      airportMatches.sort((x,y) => x.rank - y.rank);
      airportMatches = airportMatches.slice(0, 20);
    }
    let airlineMatches = [];
    if(typeof AIRLINES !== 'undefined'){
      for(const code of AIRLINES){
        const name = AIRLINE_NAMES[code] || '';
        const rank = lookupMatchRank(code, term, name.toUpperCase());
        if(rank !== null) airlineMatches.push({ code, name, numeric: AIRLINE_NUMERIC_CODES[code], rank });
      }
      airlineMatches.sort((x,y) => x.rank - y.rank);
      airlineMatches = airlineMatches.slice(0, 20);
    }
    if(airportMatches.length === 0 && airlineMatches.length === 0){
      lookupResults.innerHTML = `<div class="dim lookup-hint">NO MATCH FOUND FOR "${escapeHtml(term)}"</div>`;
      return;
    }
    if(airportMatches.length){
      lookupResults.appendChild(dockSectionHead(`AIRPORTS/CITIES (${airportMatches.length}${airportMatches.length===20?'+':''})`));
      for(const r of airportMatches){
        const row = document.createElement('button');
        row.type = 'button';
        row.className = 'lookup-row';
        row.title = `Run DC${r.code}`;
        row.innerHTML = `<span class="lookup-code">${escapeHtml(r.code)}</span><span class="lookup-main"><span class="lookup-name">${escapeHtml(r.name.toUpperCase())}</span><span class="lookup-sub">${escapeHtml(r.city.toUpperCase())}, ${escapeHtml(r.country.toUpperCase())}</span></span>`;
        row.addEventListener('click', () => submitCommand(`DC${r.code}`));
        lookupResults.appendChild(row);
      }
    }
    if(airlineMatches.length){
      lookupResults.appendChild(dockSectionHead(`AIRLINES (${airlineMatches.length}${airlineMatches.length===20?'+':''})`));
      for(const r of airlineMatches){
        const row = document.createElement('div');
        row.className = 'lookup-row lookup-row-static';
        row.innerHTML = `<span class="lookup-code">${escapeHtml(r.code)}</span><span class="lookup-main"><span class="lookup-name">${escapeHtml(r.name.toUpperCase())}</span><span class="lookup-sub">NUMERIC CODE ${escapeHtml(r.numeric)}</span></span>`;
        lookupResults.appendChild(row);
      }
    }
  }
  lookupInput.addEventListener('input', () => renderLookupResults(lookupInput.value));
  renderLookupResults('');

  // ---------- format finder panel (GUI, browser-only) ----------
  // Filterable reference over COMMAND_GRAMMAR (spec/command-grammar.json),
  // mirroring real Sabre's "Format Finder" tool. Clicking an entry only
  // inserts its example into #cmdline and focuses it - it never submits.
  // Per notes/GUI Expansion Scope-Out.md, GUI affordances must not become a
  // point-and-click alternative to typing the entry (most of these mutate
  // PNR state); this only saves the trip to HELP - the user still reviews
  // and presses Enter themselves, same as real Sabre's Format Finder dropping
  // the format into the entry line for the agent to fill in blanks.
  function renderFormatsResults(rawTerm){
    const term = rawTerm.trim().toUpperCase();
    formatsResults.innerHTML = '';
    const matches = COMMAND_GRAMMAR.filter(entry => {
      if(!term) return true;
      return (entry.category||'').toUpperCase().includes(term)
        || (entry.desc||'').toUpperCase().includes(term)
        || (entry.example||'').toUpperCase().includes(term)
        || entry.name.toUpperCase().includes(term);
    });
    if(matches.length === 0){
      formatsResults.innerHTML = `<div class="dim lookup-hint">NO COMMANDS MATCH "${escapeHtml(term)}"</div>`;
      return;
    }
    const byCategory = new Map();
    for(const entry of matches){
      const cat = entry.category || 'OTHER';
      if(!byCategory.has(cat)) byCategory.set(cat, []);
      byCategory.get(cat).push(entry);
    }
    for(const [cat, entries] of byCategory){
      formatsResults.appendChild(dockSectionHead(cat));
      for(const entry of entries){
        const row = document.createElement('button');
        row.type = 'button';
        row.className = 'format-row';
        row.title = `Insert "${entry.example||''}" into the command line`;
        row.innerHTML = `<span class="format-example">${escapeHtml(entry.example||'')}</span><span class="format-desc">${escapeHtml(entry.desc||'')}</span>`;
        row.addEventListener('click', () => {
          inputEl.value = entry.example || '';
          inputEl.focus();
          inputEl.setSelectionRange(inputEl.value.length, inputEl.value.length);
        });
        formatsResults.appendChild(row);
      }
    }
  }
  formatsInput.addEventListener('input', () => renderFormatsResults(formatsInput.value));
  renderFormatsResults('');

  applySettings();
  boot();

})();
