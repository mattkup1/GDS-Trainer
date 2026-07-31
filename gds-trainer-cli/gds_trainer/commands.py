"""Command handlers, ported 1:1 from script.js's function bodies.

Business rules preserved from the JS app (see CLAUDE.md): pricing/tickets
invalidate on itinerary change, ER vs ET differ (redisplay vs clear work
area), TKTT requires a prior ER/ET + fare quote + ticketing arrangement +
form of payment and refuses to double-ticket, seat-to-segment links are
reindexed on segment cancel, and X{n} operates only against the most
recently displayed element numbering (highest-numbered element removed
first so earlier splices don't shift pending indices).
"""

from __future__ import annotations

import copy
import random
import re
from datetime import datetime

from .airports import AIRPORTS, city_name
from .data import (
    AIRLINE_NUMERIC_CODES,
    AIRLINES,
    CLASS_FARE_MULT,
    CLASSES,
    EQUIP,
    MONTHS,
    TAX_POOL,
)
from .dates import minutes_to_clock, parse_date
from .printer import print_blank, print_err, print_line
from .rng import hash_str, mulberry32
from .state import STATE, fresh_pnr, log_activity
from .util import pad


# ---------- availability ----------

def gen_availability(day_str: str, mon_str: str, orig: str, dest: str) -> None:
    if orig == dest:
        print_err("FORMAT - ORIGIN AND DESTINATION CANNOT BE THE SAME")
        return
    dinfo = parse_date(day_str, mon_str)
    if dinfo is None:
        print_err("INVALID DATE - CHECK ENTRY AND REENTER")
        return

    seed = hash_str(f"{orig}{dest}{dinfo.day}{dinfo.mon}{dinfo.year}")
    rng = mulberry32(seed)
    num_flights = 5 + int(rng() * 4)
    flights = []
    dep = 300 + int(rng() * 90)
    for i in range(num_flights):
        airline = AIRLINES[int(rng() * len(AIRLINES))]
        flight_num = 100 + int(rng() * 2899)
        duration = 65 + int(rng() * 220)
        arr = dep + duration
        equip = EQUIP[int(rng() * len(EQUIP))]
        class_avail = [{"cls": c, "seats": int(rng() * 10)} for c in CLASSES]
        flights.append(
            {
                "line": i + 1,
                "airline": airline,
                "flight_num": flight_num,
                "dep": dep,
                "arr": arr,
                "duration": duration,
                "equip": equip,
                "class_avail": class_avail,
            }
        )
        dep += 55 + int(rng() * 95)
        if dep > 1380:
            dep = 300 + int(rng() * 60)
    STATE.last_avail = {"orig": orig, "dest": dest, "dinfo": dinfo, "flights": flights}

    print_line(
        f"** AIR AVAILABILITY **  {orig}-{dest}  {dinfo.day}{dinfo.mon}{dinfo.year}  {dinfo.weekday}",
        "hd",
    )
    print_line(f"  {city_name(orig)}  TO  {city_name(dest)}", "dim")
    print_blank()
    print_line(f"LN  FLT       {''.join(pad(c, 3) for c in CLASSES)} DEP    ARR    EQP", "dim")
    for f in flights:
        class_str = "".join(pad(c["cls"] + str(c["seats"]), 3) for c in f["class_avail"])
        print_line(
            f" {pad(f['line'], 2)} {f['airline']} {pad(f['flight_num'], 4)}  {class_str} "
            f"{pad(minutes_to_clock(f['dep']), 6)} {pad(minutes_to_clock(f['arr']), 6)} {f['equip']}"
        )
    print_blank()
    print_line(f"SELL WITH: 0{{LINE}}{{CLASS}}{{SEATS}}   e.g. 0{flights[0]['line']}Y1", "dim")


def sell_from_avail(line_num: int, cls: str, seats: int) -> None:
    if not STATE.last_avail:
        print_err("NO AVAILABILITY DISPLAY IN CONTEXT - ENTER AVAIL FIRST")
        return
    f = next((fl for fl in STATE.last_avail["flights"] if fl["line"] == line_num), None)
    if not f:
        print_err("INVALID LINE NUMBER - CHECK ENTRY AND REENTER")
        return
    cinfo = next((c for c in f["class_avail"] if c["cls"] == cls.upper()), None)
    if not cinfo:
        print_err(f"CLASS {cls.upper()} NOT OFFERED ON THIS FLIGHT")
        return
    if cinfo["seats"] == 0:
        print_err(f"CLASS {cls.upper()} SOLD OUT - CLOSED")
        return
    if seats > cinfo["seats"]:
        print_err(f"UNABLE - ONLY {cinfo['seats']} SEAT(S) AVAILABLE IN CLASS {cls.upper()}")
        return

    seg = {
        "airline": f["airline"],
        "flight_num": f["flight_num"],
        "cls": cls.upper(),
        "seats": seats,
        "dinfo": STATE.last_avail["dinfo"],
        "orig": STATE.last_avail["orig"],
        "dest": STATE.last_avail["dest"],
        "dep": f["dep"],
        "arr": f["arr"],
        "status": "HK",
        "equip": f["equip"],
    }
    STATE.pnr["segments"].append(seg)
    print_line(f"SEGMENT SOLD - {format_segment_short(seg)}")
    log_activity(STATE, f"SEGMENT SOLD - {format_segment_short(seg)}")
    invalidate_pricing()
    refresh_and_print_pnr()


def direct_sell(
    airline: str,
    flight_num: str,
    cls: str,
    day_str: str,
    mon_str: str,
    orig: str,
    dest: str,
    status_code: str | None,
    seats: int,
) -> None:
    if orig == dest:
        print_err("FORMAT - ORIGIN AND DESTINATION CANNOT BE THE SAME")
        return
    dinfo = parse_date(day_str, mon_str)
    if dinfo is None:
        print_err("INVALID DATE - CHECK ENTRY AND REENTER")
        return
    seed = hash_str(f"{airline}{flight_num}{orig}{dest}{dinfo.day}{dinfo.mon}")
    rng = mulberry32(seed)
    dep = 300 + int(rng() * 900)
    arr = dep + 65 + int(rng() * 220)
    equip = EQUIP[int(rng() * len(EQUIP))]
    seg = {
        "airline": airline.upper(),
        "flight_num": int(flight_num),
        "cls": cls.upper(),
        "seats": seats,
        "dinfo": dinfo,
        "orig": orig,
        "dest": dest,
        "dep": dep,
        "arr": arr,
        "status": (status_code or "HK").upper(),
        "equip": equip,
    }
    STATE.pnr["segments"].append(seg)
    print_line(f"SEGMENT SOLD - {format_segment_short(seg)}")
    log_activity(STATE, f"SEGMENT SOLD - {format_segment_short(seg)}")
    invalidate_pricing()
    refresh_and_print_pnr()


def invalidate_pricing() -> None:
    p = STATE.pnr
    if p["pricing"]:
        p["pricing"] = None
        print_line("FARE QUOTE INVALIDATED - ITINERARY CHANGED, RE-PRICE WITH WP", "dim")
        log_activity(STATE, "FARE QUOTE INVALIDATED - ITINERARY CHANGED")
    if p["tickets"]:
        p["tickets"] = []
        print_line("TICKETS VOIDED - ITINERARY CHANGED, REISSUE WITH TKTT AFTER RE-PRICING", "dim")
        log_activity(STATE, "TICKETS VOIDED - ITINERARY CHANGED")


def format_segment_short(seg: dict) -> str:
    dinfo = seg["dinfo"]
    return (
        f"{seg['airline']}{seg['flight_num']} {seg['cls']} {dinfo.day}{dinfo.mon} "
        f"{seg['orig']}{seg['dest']} {seg['status']}{seg['seats']}  "
        f"{minutes_to_clock(seg['dep'])} {minutes_to_clock(seg['arr'])}"
    )


# ---------- pricing (WP / WPNCS) ----------

def _trip_type(segments: list[dict]) -> str:
    if len(segments) == 1:
        return "OW"
    first, last = segments[0], segments[-1]
    if len(segments) == 2 and first["orig"] == last["dest"] and first["dest"] == last["orig"]:
        return "RT"
    if first["orig"] == last["dest"]:
        return "CT"
    return "OJ"


def _shuffled(items: list, rng) -> list:
    arr = list(items)
    for i in range(len(arr) - 1, 0, -1):
        j = int(rng() * (i + 1))
        arr[i], arr[j] = arr[j], arr[i]
    return arr


def price_itinerary(mode: str) -> None:
    p = STATE.pnr
    if len(p["segments"]) == 0:
        print_err("UNABLE TO PRICE - NO ITINERARY SEGMENTS")
        return
    if len(p["names"]) == 0:
        print_err("UNABLE TO PRICE - NAME FIELD REQUIRED PRIOR TO PRICING")
        return

    seed_key = (
        "|".join(
            f"{s['airline']}{s['flight_num']}{s['cls']}{s['dinfo'].day}{s['dinfo'].mon}"
            f"{s['orig']}{s['dest']}{s['seats']}"
            for s in p["segments"]
        )
        + mode
    )
    rng = mulberry32(hash_str(seed_key))

    base_fare = 0
    for s in p["segments"]:
        mult = CLASS_FARE_MULT.get(s["cls"], 1.4)
        dist = 60 + int(rng() * 400)
        base_fare += round((45 + dist * 0.35) * mult * s["seats"])

    num_taxes = 2 + int(rng() * 3)
    pool = _shuffled(TAX_POOL, rng)[:num_taxes]
    taxes = []
    tax_total = 0.0
    for t in pool:
        amt = round((3 + rng() * 22) * 100) / 100
        taxes.append({"code": t["code"], "label": t["label"], "amount": amt})
        tax_total += amt
    tax_total = round(tax_total * 100) / 100
    total = round((base_fare + tax_total) * 100) / 100
    fare_basis = f"{p['segments'][0]['cls']}{_trip_type(p['segments'])}"

    p["pricing"] = {
        "mode": mode,
        "base_fare": base_fare,
        "taxes": taxes,
        "tax_total": tax_total,
        "total": total,
        "fare_basis": fare_basis,
        "currency": "USD",
    }

    print_line(
        "** LOWEST FARE - WPNCS (SUBJECT TO AVAILABILITY) **"
        if mode == "WPNCS"
        else "** ITINERARY PRICING - WP **",
        "hd",
    )
    for i, s in enumerate(p["segments"]):
        print_line(f"  {i + 1}  {format_segment_short(s)}", "dim")
    print_blank()
    print_line(f"FARE BASIS: {fare_basis}")
    print_line(f"BASE FARE      USD {base_fare:.2f}")
    for t in taxes:
        print_line(f"  {t['code']}   USD {t['amount']:.2f}   {t['label']}", "dim")
    print_line(f"TAXES/FEES     USD {tax_total:.2f}")
    print_line(f"TOTAL          USD {total:.2f}", "hd")
    print_blank()
    print_line("FARE QUOTE STORED - REQUIRED PRIOR TO TICKETING", "dim")
    log_activity(STATE, f"PRICED - {format_pricing_short(p['pricing'])}")
    refresh_and_print_pnr()


def format_pricing_short(pr: dict) -> str:
    return (
        f"{pr['mode']}  {pr['fare_basis']}  BASE USD{pr['base_fare']:.2f}  "
        f"TAX USD{pr['tax_total']:.2f}  TTL USD{pr['total']:.2f}"
    )


# ---------- seat maps ----------

def get_seat_map(seg: dict) -> dict:
    dinfo = seg["dinfo"]
    seed = hash_str(
        f"{seg['airline']}{seg['flight_num']}{dinfo.day}{dinfo.mon}{seg['orig']}{seg['dest']}SEATMAP"
    )
    rng = mulberry32(seed)
    rows = []
    occupied: set[str] = set()
    for r in range(1, 31):
        seats = []
        for col in "ABCDEF":
            occ = rng() < 0.4
            if occ:
                occupied.add(f"{r}{col}")
            seats.append(occ)
        rows.append({"num": r, "seats": seats})
    return {"rows": rows, "occupied": occupied}


def show_seat_map(n: int) -> None:
    segments = STATE.pnr["segments"]
    if n < 1 or n > len(segments):
        print_err("INVALID SEGMENT NUMBER - CHECK ITINERARY")
        return
    seg = segments[n - 1]
    smap = get_seat_map(seg)
    mine = {s["seat"] for s in STATE.pnr["seats"] if s["seg_idx"] == n - 1}
    print_line(
        f"SEAT MAP - {seg['airline']}{seg['flight_num']}  {seg.get('equip') or ''}  "
        f"{seg['dinfo'].day}{seg['dinfo'].mon}  {seg['orig']}-{seg['dest']}",
        "hd",
    )
    print_blank()
    print_line("      A  B  C     D  E  F", "dim")
    for row in smap["rows"]:
        cols = []
        for i, occ in enumerate(row["seats"]):
            seat_id = f"{row['num']}{'ABCDEF'[i]}"
            cols.append(" * " if seat_id in mine else (" X " if occ else " . "))
        print_line(f" {pad(row['num'], 3)}  {''.join(cols[:3])}   {''.join(cols[3:])}")
    print_blank()
    print_line(". OPEN   X OCCUPIED   * YOUR ASSIGNMENT", "dim")
    print_line(f"ASSIGN WITH: 4{n}-{{SEAT}}   e.g. 4{n}-14A", "dim")


def assign_seat(n: int, seat_str: str) -> None:
    segments = STATE.pnr["segments"]
    if n < 1 or n > len(segments):
        print_err("INVALID SEGMENT NUMBER - CHECK ITINERARY")
        return
    seg = segments[n - 1]
    row_match = re.match(r"^(\d{1,2})([A-F])$", seat_str)
    row = int(row_match.group(1))
    if row < 1 or row > 30:
        print_err("INVALID SEAT ROW - VALID RANGE 1-30")
        return
    smap = get_seat_map(seg)
    if seat_str in smap["occupied"]:
        print_err(f"SEAT {seat_str} NOT AVAILABLE - SELECT ANOTHER (SEE SEAT MAP: 4{n})")
        return
    if any(s["seg_idx"] == n - 1 and s["seat"] == seat_str for s in STATE.pnr["seats"]):
        print_err(f"SEAT {seat_str} ALREADY ASSIGNED ON THIS SEGMENT")
        return
    STATE.pnr["seats"].append({"seg_idx": n - 1, "seat": seat_str})
    print_line(f"SEAT ASSIGNED - SEG{n} {seat_str}")
    log_activity(STATE, f"SEAT ASSIGNED - SEG{n} {seat_str}")
    refresh_and_print_pnr()


# ---------- form of payment ----------

def mask_card(num: str) -> str:
    return "X" * max(0, len(num) - 4) + num[-4:]


# ---------- encode/decode ----------

def decode_airport(code: str) -> None:
    a = AIRPORTS.get(code)
    if not a:
        print_err(f"UNABLE TO DECODE - {code} NOT FOUND")
        return
    print_line(f"{code}  {a[0].upper()}", "hd")
    print_line(f"  {a[1].upper()}, {a[2].upper()}", "dim")


def search_airports(term: str) -> None:
    term = term.strip()
    if len(term) < 2:
        print_err("FORMAT - ENTER AT LEAST 2 CHARACTERS TO SEARCH")
        return
    results = []
    for code, a in AIRPORTS.items():
        if term in a[0].upper() or term in a[1].upper():
            results.append({"code": code, "name": a[0], "city": a[1], "country": a[2]})
            if len(results) >= 25:
                break
    if not results:
        print_err(f'NO MATCH FOUND FOR "{term}"')
        return
    plus = "+" if len(results) == 25 else ""
    es = "ES" if len(results) != 1 else ""
    print_line(f'CITY/AIRPORT NAME SEARCH - "{term}"  ({len(results)}{plus} MATCH{es})', "hd")
    print_blank()
    for r in results:
        print_line(
            f" {pad(r['code'], 4)} {pad(r['name'].upper(), 34)} "
            f"{pad(r['city'].upper(), 20)} {r['country'].upper()}"
        )


# ---------- PNR element display / cancel ----------

def build_elements() -> list[dict]:
    p = STATE.pnr
    els: list[dict] = []
    for i, n in enumerate(p["names"]):
        els.append({"kind": "name", "idx": i, "label": f"NM{i + 1}", "text": n})
    for i, inf in enumerate(p["infants"]):
        els.append(
            {
                "kind": "infant",
                "idx": i,
                "label": "IN",
                "text": f"{inf['surname']}/{inf['given']}  DOB {inf['dob']}  "
                f"(INFANT - TRAVELS WITH {inf['adult']})",
            }
        )
    for i, s in enumerate(p["segments"]):
        els.append(
            {
                "kind": "segment",
                "idx": i,
                "label": f"SEG{i + 1}",
                "text": format_segment_short(s) + f"  {s['dinfo'].weekday}",
            }
        )
    for i, st in enumerate(p["seats"]):
        els.append(
            {
                "kind": "seat",
                "idx": i,
                "label": "SEAT",
                "text": f"SEG{st['seg_idx'] + 1} - SEAT {st['seat']}",
            }
        )
    for i, r in enumerate(p["ssrs"]):
        els.append({"kind": "ssr", "idx": i, "label": "SSR", "text": r["text"]})
    for i, o in enumerate(p["osis"]):
        els.append({"kind": "osi", "idx": i, "label": "OSI", "text": o["text"]})
    if p["pricing"]:
        els.append({"kind": "fq", "idx": 0, "label": "FQ", "text": format_pricing_short(p["pricing"])})
    for i, ph in enumerate(p["phones"]):
        els.append({"kind": "phone", "idx": i, "label": "CTC", "text": ph})
    if p["received_from"]:
        els.append({"kind": "rf", "idx": 0, "label": "RF", "text": p["received_from"]})
    if p["form_of_payment"]:
        els.append({"kind": "fp", "idx": 0, "label": "FP", "text": p["form_of_payment"]["display"]})
    if p["ticketing"]:
        els.append({"kind": "tk", "idx": 0, "label": "TK", "text": p["ticketing"]})
    for i, t in enumerate(p["tickets"]):
        suffix = " (INF)" if t["is_infant"] else ""
        els.append({"kind": "tkt", "idx": i, "label": "TKT", "text": f"{t['passenger']}{suffix}  {t['ticket_num']}"})
    for i, e in enumerate(els):
        e["num"] = i + 1
    return els


def refresh_and_print_pnr() -> None:
    STATE.last_display = build_elements()
    print_blank()
    print_line(f"RLOC: {STATE.pnr['locator'] or '(NOT SAVED - END TRANSACT TO STORE)'}", "hd")
    if not STATE.last_display:
        print_line("  ** PNR IS EMPTY **", "dim")
        return
    for e in STATE.last_display:
        print_line(f" {pad(e['num'], 2)}  {pad(e['label'], 5)} {e['text']}")


def remove_element(e: dict) -> None:
    p = STATE.pnr
    kind, idx = e["kind"], e["idx"]
    if kind == "name":
        del p["names"][idx]
    elif kind == "infant":
        del p["infants"][idx]
    elif kind == "segment":
        del p["segments"][idx]
        p["pricing"] = None
        p["tickets"] = []
        new_seats = []
        for st in p["seats"]:
            if st["seg_idx"] == idx:
                continue
            if st["seg_idx"] > idx:
                new_seats.append({"seg_idx": st["seg_idx"] - 1, "seat": st["seat"]})
            else:
                new_seats.append(st)
        p["seats"] = new_seats
    elif kind == "seat":
        del p["seats"][idx]
    elif kind == "ssr":
        del p["ssrs"][idx]
    elif kind == "osi":
        del p["osis"][idx]
    elif kind == "fq":
        p["pricing"] = None
        p["tickets"] = []
    elif kind == "phone":
        del p["phones"][idx]
    elif kind == "rf":
        p["received_from"] = None
    elif kind == "fp":
        p["form_of_payment"] = None
    elif kind == "tk":
        p["ticketing"] = None
    elif kind == "tkt":
        del p["tickets"][idx]


def cancel_elements(nums: list[int]) -> None:
    uniq_desc = sorted(set(nums), reverse=True)
    cancelled = []
    for n in uniq_desc:
        e = next((x for x in STATE.last_display if x["num"] == n), None)
        if not e:
            continue
        remove_element(e)
        cancelled.append(n)
    if not cancelled:
        print_err("INVALID ELEMENT NUMBER - REDISPLAY WITH *R")
        return
    cancelled.sort()
    suffix = "S" if len(cancelled) > 1 else ""
    nums_str = ",".join(str(c) for c in cancelled)
    print_line(f"ELEMENT{suffix} {nums_str} CANCELLED")
    log_activity(STATE, f"ELEMENT{suffix} {nums_str} CANCELLED")
    refresh_and_print_pnr()


def cancel_itinerary() -> None:
    p = STATE.pnr
    if len(p["segments"]) == 0:
        print_err("NO ITINERARY SEGMENTS TO CANCEL")
        return
    p["segments"] = []
    p["pricing"] = None
    p["tickets"] = []
    p["seats"] = []
    print_line("ITINERARY CANCELLED")
    log_activity(STATE, "ITINERARY CANCELLED")
    refresh_and_print_pnr()


# ---------- end transaction ----------

def gen_locator() -> str:
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        s = "".join(random.choice(chars) for _ in range(6))
        if s not in STATE.history:
            return s


def end_transaction(mode: str) -> None:
    p = STATE.pnr
    if len(p["segments"]) == 0:
        print_err("PNR INCOMPLETE - NO ITINERARY SEGMENTS")
        return
    if len(p["names"]) == 0:
        print_err("PNR INCOMPLETE - NEED NAME FIELD (ENTRY: -SURNAME/GIVEN)")
        return
    if not p["pricing"]:
        print_err("PNR INCOMPLETE - NEED FARE QUOTE (ENTRY: WP)")
        return
    if len(p["phones"]) == 0:
        print_err("PNR INCOMPLETE - NEED PHONE FIELD (ENTRY: 9...)")
        return
    if not p["received_from"]:
        print_err("PNR INCOMPLETE - NEED RECEIVED FROM (ENTRY: 6...)")
        return
    if not p["form_of_payment"]:
        print_err("PNR INCOMPLETE - NEED FORM OF PAYMENT (ENTRY: FPCASH, FPCHECK, OR FPCC...)")
        return
    if not p["ticketing"]:
        print_err("PNR INCOMPLETE - NEED TICKETING ARRANGEMENT (ENTRY: 7TAW/)")
        return

    if not p["locator"]:
        p["locator"] = gen_locator()
    log_activity(STATE, f"PNR SAVED ({mode}) - RLOC {p['locator']}")
    STATE.history[p["locator"]] = copy.deepcopy(p)

    now = datetime.now()
    ts = f"{now.day}{MONTHS[now.month - 1]}  {minutes_to_clock(now.hour * 60 + now.minute)}"
    print_line("END OF TRANSACTION COMPLETE", "hd")
    print_line(f"  {ts}   RLOC: {p['locator']}")

    if mode == "ET":
        STATE.pnr = fresh_pnr()
        STATE.last_display = []
        print_line("WORK AREA CLEARED - READY FOR NEXT ENTRY", "dim")
    else:
        refresh_and_print_pnr()


def retrieve_by_locator(loc: str) -> None:
    rec = STATE.history.get(loc)
    if not rec:
        print_err("RECORD LOCATOR NOT FOUND")
        return
    STATE.pnr = copy.deepcopy(rec)
    print_line(f"PNR {loc} RETRIEVED")
    log_activity(STATE, f"PNR RETRIEVED - RLOC {loc}")
    refresh_and_print_pnr()


# ---------- ticketing (TKTT) ----------

def gen_ticket_number(locator: str, identifier: str) -> str:
    seed = hash_str(f"{locator}{identifier}TKT")
    rng = mulberry32(seed)
    return str(int(rng() * 10000000000)).zfill(10)


def issue_tickets() -> None:
    p = STATE.pnr
    if not p["locator"]:
        print_err("UNABLE TO TICKET - END TRANSACT (ER OR ET) BEFORE TICKETING")
        return
    if not p["pricing"]:
        print_err("UNABLE TO TICKET - NO FARE QUOTE ON FILE (ENTRY: WP)")
        return
    if not p["ticketing"]:
        print_err("UNABLE TO TICKET - NO TICKETING ARRANGEMENT ON FILE")
        return
    if not p["form_of_payment"]:
        print_err("UNABLE TO TICKET - NO FORM OF PAYMENT ON FILE")
        return
    if p["tickets"]:
        print_err("PNR ALREADY TICKETED - TICKET NUMBERS ON FILE (SEE *R)")
        return

    validating_carrier = p["segments"][0]["airline"]
    numeric_code = AIRLINE_NUMERIC_CODES.get(validating_carrier, "000")

    for name in p["names"]:
        serial = gen_ticket_number(p["locator"], name)
        p["tickets"].append({"passenger": name, "ticket_num": f"{numeric_code}-{serial}", "is_infant": False})
    for inf in p["infants"]:
        identifier = f"{inf['surname']}/{inf['given']}"
        serial = gen_ticket_number(p["locator"], identifier)
        p["tickets"].append({"passenger": identifier, "ticket_num": f"{numeric_code}-{serial}", "is_infant": True})

    print_line("** ELECTRONIC TICKET ISSUED **", "hd")
    for t in p["tickets"]:
        label = t["passenger"] + (" (INF)" if t["is_infant"] else "")
        print_line(f"  {pad(label, 28)} {t['ticket_num']}")
    print_line(
        f"VALIDATING CARRIER: {validating_carrier}   FORM OF PAYMENT: {p['form_of_payment']['display']}",
        "dim",
    )
    log_activity(
        STATE,
        f"TICKETED - {len(p['tickets'])} TICKET(S) ISSUED, VALIDATING CARRIER {validating_carrier}",
    )
    refresh_and_print_pnr()


def show_history() -> None:
    log = STATE.pnr.get("activity_log") or []
    if not log:
        print_line("NO HISTORY AVAILABLE FOR THIS PNR", "dim")
        return
    loc_suffix = f"  RLOC: {STATE.pnr['locator']}" if STATE.pnr["locator"] else ""
    print_line(f"PNR ACTIVITY HISTORY{loc_suffix}", "hd")
    print_blank()
    for entry in log:
        print_line(f" {entry['stamp']}  {pad(entry['sine'], 6)} {entry['text']}")


# ---------- help ----------

def show_help() -> None:
    print_line("GDS TRAINER ENTRY REFERENCE", "hd")
    print_blank()
    print_line("SIGN ON/OFF", "hd")
    print_line("  SI[sine/pcc]        Sign in           e.g. SI  or  SI1234AA/DFW1")
    print_line("  SO                  Sign out")
    print_blank()
    print_line("AVAILABILITY", "hd")
    print_line("  A{DD}{MMM}{ORG}{DST}   Air availability   e.g. A15AUGDFWORD")
    print_line("  1{DD}{MMM}{ORG}{DST}   Air availability (alternate entry)  e.g. 115AUGDFWORD")
    print_blank()
    print_line("SELL", "hd")
    print_line("  0{LN}{CLASS}{SEATS}                        Sell from avail line   e.g. 04Y1")
    print_line("  0{AL}{FLT}{CLASS}{DD}{MMM}{ORG}{DST}{STATUS}{SEATS}")
    print_line("                                              Direct/long sell   e.g. 0AA100Y15AUGDFWORDNN1")
    print_blank()
    print_line("PNR BUILD", "hd")
    print_line("  -{SURNAME}/{GIVEN} {TITLE}          Name field   e.g. -SMITH/JOHN MR")
    print_line("  -{N}{SURNAME}/{G1} {T1}/{G2} {T2}   Multiple passengers, same surname")
    print_line("                                       e.g. -2SMITH/JOHN MR/JANE MRS")
    print_line("  -{SURNAME}/{GIVEN} {TITLE}(INF{ISURNAME}/{IGIVEN}/{DOB})")
    print_line("                                       Name with an associated lap infant")
    print_line("                                       e.g. -SMITH/JOHN MR(INFSMITH/BABY/12JAN26)")
    print_line("  9{NUMBER}-{LOC}                     Phone field   e.g. 9214555-1234-A")
    print_line("  9/{CTY}{NUMBER}-{LOC}               Phone field, out-of-area   e.g. 9/BOS617-555-1234-A")
    print_line("  6{TEXT}                             Received from   e.g. 6JSMITH")
    print_line("  WP                                  Price itinerary (required before ticketing)")
    print_line("  WPNCS                               Price - lowest fare regardless of availability")
    print_line("  7TAW/                               Ticketing: at will (ticket on/before departure)")
    print_line("  7TAW{DD}{MMM}/{HHMM}                Ticketing at will, queued to date/time")
    print_line("  7TAX{DD}{MMM}/{HHMM}                Ticketing time limit   e.g. 7TAX16AUG/1800")
    print_line("  FPCASH  /  FPCHECK                  Form of payment - cash / check")
    print_line("  FPCC{TYPE}{CARDNUM}/{MMYY}          Form of payment - credit card   e.g. FPCCVI4111111111111111/1225")
    print_line("                                       Card types: VI CA AX DC DS JC")
    print_blank()
    print_line("TICKETING", "hd")
    print_line("  TKTT     Issue ticket(s) - requires a saved PNR (ER/ET) with fare quote,")
    print_line("           ticketing arrangement, and form of payment already on file.")
    print_line("           Distinct from the ticketing ARRANGEMENT above: TAW/TAX just sets")
    print_line("           a deadline, TKTT actually issues ticket numbers. Changing the")
    print_line("           itinerary after ticketing voids the ticket(s) - reissue with WP then TKTT.")
    print_blank()
    print_line("SPECIAL SERVICE / OTHER SERVICE INFO", "hd")
    print_line("  3{SSRCODE}[-{PAX#}][/{TEXT}]   Special service request   e.g. 3VGML  or  3WCHR-1/AISLE SEAT")
    print_line("  3OSI{AL}{TEXT}                 Other service info   e.g. 3OSIAA VIP PASSENGER")
    print_line("  3FQTV{AL}{NUMBER}              Frequent flyer number   e.g. 3FQTVAA1234567")
    print_line(
        "  SSR codes: WCHR WCHS WCHC VGML BBML CHML KSML MOML DBML BLND DEAF UMNR PETC BSCT SPML XBAG",
        "dim",
    )
    print_blank()
    print_line("SEATS", "hd")
    print_line("  4{N}            Display seat map for itinerary segment N   e.g. 41")
    print_line("  4{N}-{SEAT}     Assign a seat on segment N   e.g. 41-14A")
    print_blank()
    print_line("ENCODE / DECODE", "hd")
    print_line("  DC{CODE}        Decode a 3-letter airport/city code   e.g. DCORD")
    print_line("  DAN{TEXT}       Search airports/cities by name   e.g. DANCHICAGO")
    print_blank()
    print_line("PNR MANAGEMENT", "hd")
    print_line("  *R  or  *              Display current PNR")
    print_line("  *H                     Display PNR activity history (chronological log)")
    print_line("  *{LOCATOR}             Retrieve PNR by record locator")
    print_line("  X{N}                   Cancel numbered element N")
    print_line("  X{N}-{M}, X{N},{M}     Cancel a range or list of elements")
    print_line("  XI                     Cancel entire itinerary (all segments)")
    print_line("  IG                     Ignore PNR (discard unsaved work)")
    print_line("  ER                     End transaction, redisplay")
    print_line("  ET                     End transaction, clear work area")
    print_blank()
    print_line("Everything above is entered on the command line and submitted with Enter.", "dim")


# ---------- sign in/out ----------

def sign_in(rest: str) -> None:
    rest = (rest or "").strip()
    sine, pcc = "9TAA", "DFW1"
    if rest:
        parts = rest.split("/")
        if parts[0]:
            sine = parts[0].upper()
        if len(parts) > 1 and parts[1]:
            pcc = parts[1].upper()
    STATE.signed_in = True
    STATE.sine = sine
    STATE.pcc = pcc
    now = datetime.now()
    print_line("GDS TRAINER - SIGN IN COMPLETE", "hd")
    print_line(f"  AGENT SINE: {sine}   PCC: {pcc}   {MONTHS[now.month - 1]}{now.day} {now.year}")
    print_blank()
    print_line("TYPE HELP FOR COMMAND REFERENCE", "dim")


def sign_out() -> None:
    print_line("SIGNED OFF", "hd")
    STATE.signed_in = False
    STATE.sine = None
    STATE.pcc = None


# ---------- boot ----------

def boot() -> None:
    print_line("G*D*S*  T*R*A*I*N*E*R*  -----------------------------------------------", "hd")
    print_line("                        GLOBAL DISTRIBUTION SYSTEM - TERMINAL EMULATION")
    print_line("                        -----------------------------------------------")
    print_blank()
    print_line("NOT SIGNED IN", "dim")
    print_line("TYPE SI TO SIGN IN   ·   HELP FOR COMMAND REFERENCE", "dim")
