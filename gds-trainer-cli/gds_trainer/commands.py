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
import json
import random
import re
from datetime import datetime, timedelta
from pathlib import Path

from .airports import AIRPORTS, city_name
from .data import (
    AIRLINE_NUMERIC_CODES,
    AIRLINES,
    CARD_TYPES,
    CLASS_FARE_MULT,
    CLASSES,
    CORPORATE_CODES,
    DOCUMENT_TYPES,
    EMAIL_DOCUMENTS,
    EQUIP,
    FARE_FORMULA,
    FARE_RULES,
    FLIGHT_CANCELLATION,
    LOYALTY_TIERS,
    MONTHS,
    PHONE_LOC_CODES,
    QUEUE_CATEGORIES,
    SCHEDULE_CHANGE,
    SEAT_LAYOUTS,
    SEGMENT_STATUS_LABELS,
    SSR_CODES,
    TAX_POOL,
    WAITLIST_CLEAR,
    WEEKDAYS,
)
from .dates import minutes_to_clock, parse_date
from .printer import print_blank, print_err, print_line
from .rng import hash_str, mulberry32
from .state import STATE, fresh_pnr, log_activity, now_stamp
from .util import pad

_SPEC_DIR = Path(__file__).resolve().parents[2] / "spec"
_PNR_COMPLETENESS = json.loads((_SPEC_DIR / "pnr-completeness.json").read_text(encoding="utf-8"))


def _completeness_check_passes(kind: str, value) -> bool:
    if kind == "non_empty":
        return isinstance(value, list) and len(value) > 0
    if kind == "present":
        return value is not None
    if kind == "empty":
        return isinstance(value, list) and len(value) == 0
    return True


def _first_incomplete_message(rule_key: str) -> str | None:
    for rule in _PNR_COMPLETENESS.get(rule_key, []):
        value = STATE.pnr[rule["field"]]
        if not _completeness_check_passes(rule["check"], value):
            return rule["message"]
    return None


# ---------- availability ----------
# Matches real Sabre: every line is one ordinary flight, shown with its own origin/
# destination (a connection candidate leg's city pair differs from the overall search)
# - there is no "grouped" multi-leg line. Connections are built by the agent recognizing
# two lines whose cities/times line up and selling both together (see sell_connection
# below), never a single system-bundled line.

def _gen_flight(rng, dep: int, orig: str, dest: str) -> dict:
    airline = AIRLINES[int(rng() * len(AIRLINES))]
    flight_num = 100 + int(rng() * 2899)
    duration = 65 + int(rng() * 220)
    arr = dep + duration
    equip = EQUIP[int(rng() * len(EQUIP))]
    class_avail = [{"cls": c, "seats": int(rng() * 10)} for c in CLASSES]
    return {
        "airline": airline,
        "flight_num": flight_num,
        "dep": dep,
        "arr": arr,
        "duration": duration,
        "equip": equip,
        "class_avail": class_avail,
        "orig": orig,
        "dest": dest,
    }


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
        flights.append({"line": i + 1, **_gen_flight(rng, dep, orig, dest)})
        dep += 55 + int(rng() * 95)
        if dep > 1380:
            dep = 300 + int(rng() * 60)

    # Always append exactly 2 workable connections (4 more lines: 2 legs each) after the
    # nonstops, continuing to draw from the same RNG stream (search stays one deterministic
    # sequence per orig/dest/date). Keeping them last means line 1 is always a nonstop for
    # every route/date. Each pair of lines is a real, separately-numbered flight - nothing
    # marks them as "connectable"; the agent reads the city pairs/times like on real Sabre.
    airport_codes = list(AIRPORTS.keys())
    next_line = num_flights + 1
    for _ in range(2):
        via = orig
        if airport_codes:
            for _ in range(10):
                if via != orig and via != dest:
                    break
                via = airport_codes[int(rng() * len(airport_codes))]
        dep1 = 300 + int(rng() * 600)
        leg1 = _gen_flight(rng, dep1, orig, via)
        layover = 45 + int(rng() * 135)
        leg2 = _gen_flight(rng, leg1["arr"] + layover, via, dest)
        flights.append({"line": next_line, **leg1})
        next_line += 1
        flights.append({"line": next_line, **leg2})
        next_line += 1
    STATE.last_avail = {"orig": orig, "dest": dest, "dinfo": dinfo, "flights": flights}

    print_line(
        f"** AIR AVAILABILITY **  {orig}-{dest}  {dinfo.day}{dinfo.mon}{dinfo.year}  {dinfo.weekday}",
        "hd",
    )
    print_line(f"  {city_name(orig)}  TO  {city_name(dest)}", "dim")
    print_blank()
    # Built from the same field widths as the data rows below (not hand-counted spaces)
    # so the header can't drift out of alignment with them - see the seat map header's
    # identical rationale.
    print_line(
        f" {pad('LN', 2)} {pad('FLT', 7)}  {pad('RTE', 6)}  "
        f"{''.join(pad(c, 3) for c in CLASSES)} {pad('DEP', 6)} {pad('ARR', 6)} EQP",
        "dim",
    )
    for f in flights:
        class_str = "".join(pad(c["cls"] + str(c["seats"]), 3) for c in f["class_avail"])
        print_line(
            f" {pad(f['line'], 2)} {f['airline']} {pad(f['flight_num'], 4)}  {f['orig']}{f['dest']}  {class_str} "
            f"{pad(minutes_to_clock(f['dep']), 6)} {pad(minutes_to_clock(f['arr']), 6)} {f['equip']}"
        )
    print_blank()
    print_line(f"SELL WITH: 0{{LINE}}{{CLASS}}{{SEATS}}   e.g. 0{flights[0]['line']}Y1", "dim")
    print_line(
        "SELL CONNECTION: 0{SEATS}{CLASS}{LINE}{CLASS}{LINE}   e.g. "
        f"02Y{flights[0]['line']}Y{flights[-1]['line']}",
        "dim",
    )


# Real Sabre's schedule display: identical entry shape to availability ("S" instead of
# "A"/"1"), but shows what flies across a several-day window - no booking classes/seat
# counts, since it's not tied to sellable inventory. Reuses gen_availability's exact
# per-date seeding/generation (same hash_str/mulberry32/_gen_flight calls) once per date in
# the window rather than a second, disconnected formula - so a date also covered by an
# availability search on the same route shows the literal same flights here, just without
# the booking columns. Nonstop only - connections are an availability/booking-time concept,
# not a schedule-lookup one.
def gen_schedule(day_str: str, mon_str: str, orig: str, dest: str) -> None:
    if orig == dest:
        print_err("FORMAT - ORIGIN AND DESTINATION CANNOT BE THE SAME")
        return
    start_info = parse_date(day_str, mon_str)
    if start_info is None:
        print_err("INVALID DATE - CHECK ENTRY AND REENTER")
        return

    days = []
    for i in range(7):
        d = start_info.date + timedelta(days=i)
        weekday = WEEKDAYS[(d.weekday() + 1) % 7]
        days.append({"day": d.day, "mon": MONTHS[d.month - 1], "year": d.year, "weekday": weekday})

    print_line(
        f"** SCHEDULE **  {orig}-{dest}  {days[0]['day']}{days[0]['mon']}{days[0]['year']} - "
        f"{days[6]['day']}{days[6]['mon']}{days[6]['year']}",
        "hd",
    )
    print_line(f"  {city_name(orig)}  TO  {city_name(dest)}", "dim")
    for day in days:
        seed = hash_str(f"{orig}{dest}{day['day']}{day['mon']}{day['year']}")
        rng = mulberry32(seed)
        num_flights = 5 + int(rng() * 4)
        dep = 300 + int(rng() * 90)
        print_blank()
        print_line(f"{pad(day['day'], 2)}{day['mon']} {day['weekday']}", "hd")
        print_line("  FLT       DEP    ARR    ELAPSED EQP", "dim")
        for _ in range(num_flights):
            f = _gen_flight(rng, dep, orig, dest)
            elapsed = f"{f['duration'] // 60}:{f['duration'] % 60:02d}"
            print_line(
                f"  {f['airline']} {pad(f['flight_num'], 4)}  {pad(minutes_to_clock(f['dep']), 6)} "
                f"{pad(minutes_to_clock(f['arr']), 6)} {pad(elapsed, 7)} {f['equip']}"
            )
            dep += 55 + int(rng() * 95)
            if dep > 1380:
                dep = 300 + int(rng() * 60)


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

    # A class at exactly 0 remaining sells as a waitlist request (HL) instead of being
    # blocked outright - matches how a real GDS lets you request a closed class. Partial
    # shortfalls (some seats left, just not enough for this request) still hard-block below,
    # to keep the "how many can I actually get right now" signal meaningful.
    if cinfo["seats"] == 0:
        seg = {
            "airline": f["airline"],
            "flight_num": f["flight_num"],
            "cls": cls.upper(),
            "seats": seats,
            "dinfo": STATE.last_avail["dinfo"],
            "orig": f["orig"],
            "dest": f["dest"],
            "dep": f["dep"],
            "arr": f["arr"],
            "status": "HL",
            "equip": f["equip"],
        }
        STATE.pnr["segments"].append(seg)
        print_line(f"SEGMENT WAITLISTED - {format_segment_short(seg)}")
        log_activity(STATE, f"SEGMENT WAITLISTED - {format_segment_short(seg)}")
        invalidate_pricing()
        refresh_and_print_pnr()
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
        "orig": f["orig"],
        "dest": f["dest"],
        "dep": f["dep"],
        "arr": f["arr"],
        "status": "HK",
        "equip": f["equip"],
    }
    STATE.pnr["segments"].append(seg)
    cinfo["seats"] -= seats
    print_line(f"SEGMENT SOLD - {format_segment_short(seg)}")
    log_activity(STATE, f"SEGMENT SOLD - {format_segment_short(seg)}")
    invalidate_pricing()
    refresh_and_print_pnr()


def sell_connection(seats: int, cls1: str, line1_num: int, cls2: str, line2_num: int) -> None:
    """Real Sabre connection sell: "0{SEATS}{CLASS1}{LINE1}{CLASS2}{LINE2}" - the agent
    picks two lines from the display whose cities/times work as a connection (nothing in
    the display marks them as connectable) and sells both in one entry.
    """
    if not STATE.last_avail:
        print_err("NO AVAILABILITY DISPLAY IN CONTEXT - ENTER AVAIL FIRST")
        return
    flights = STATE.last_avail["flights"]
    f1 = next((fl for fl in flights if fl["line"] == line1_num), None)
    f2 = next((fl for fl in flights if fl["line"] == line2_num), None)
    if not f1 or not f2:
        print_err("INVALID LINE NUMBER - CHECK ENTRY AND REENTER")
        return
    if f1["dest"] != f2["orig"]:
        print_err(f"INVALID CONNECTION - {f1['dest']} DOES NOT MATCH {f2['orig']}")
        return
    if f2["dep"] < f1["arr"] + 30:
        print_err("UNABLE - INSUFFICIENT CONNECTION TIME")
        return

    legs = [(f1, cls1.upper()), (f2, cls2.upper())]
    # Validate both legs before mutating anything, so a shortfall on the second leg
    # never leaves the PNR half-sold.
    cinfos = []
    for flight, cls in legs:
        cinfo = next((c for c in flight["class_avail"] if c["cls"] == cls), None)
        if not cinfo:
            print_err(f"CLASS {cls} NOT OFFERED ON THIS FLIGHT")
            return
        if cinfo["seats"] > 0 and seats > cinfo["seats"]:
            print_err(f"UNABLE - ONLY {cinfo['seats']} SEAT(S) AVAILABLE IN CLASS {cls}")
            return
        cinfos.append(cinfo)

    # Married segments: the two legs are tagged with a shared group id so cancel_elements
    # can later require both be cancelled together, matching real Sabre. Marriage is only
    # ever created here - the one place two segments are known to belong to one itinerary.
    married_group = STATE.next_married_group_id
    STATE.next_married_group_id += 1
    for (flight, cls), cinfo in zip(legs, cinfos):
        waitlisted = cinfo["seats"] == 0
        seg = {
            "airline": flight["airline"],
            "flight_num": flight["flight_num"],
            "cls": cls,
            "seats": seats,
            "dinfo": STATE.last_avail["dinfo"],
            "orig": flight["orig"],
            "dest": flight["dest"],
            "dep": flight["dep"],
            "arr": flight["arr"],
            "status": "HL" if waitlisted else "HK",
            "equip": flight["equip"],
            "marriedGroup": married_group,
        }
        STATE.pnr["segments"].append(seg)
        if not waitlisted:
            cinfo["seats"] -= seats
        label = "SEGMENT WAITLISTED" if waitlisted else "SEGMENT SOLD"
        print_line(f"{label} - {format_segment_short(seg)}")
        log_activity(STATE, f"{label} - {format_segment_short(seg)}")
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


# Shared by every path that stales out a fare quote/ticket (sell, cancel, schedule change):
# snapshots the outgoing pricing/tickets into prior_pricing/prior_tickets - but only when the
# PNR was actually ticketed (both set), since there's nothing meaningful to exchange from a
# merely-priced-but-not-ticketed PNR - before clearing them, so a later WFR{TICKET#} exchange
# can still reference what the passenger already paid.
def _clear_pricing_and_tickets(p: dict) -> None:
    if p["pricing"] and p["tickets"]:
        p["prior_tickets"] = p["tickets"]
        p["prior_pricing"] = p["pricing"]
    p["pricing"] = None
    p["tickets"] = []


def invalidate_pricing() -> None:
    p = STATE.pnr
    had_pricing = bool(p["pricing"])
    had_tickets = bool(p["tickets"])
    _clear_pricing_and_tickets(p)
    if had_pricing:
        print_line("FARE QUOTE INVALIDATED - ITINERARY CHANGED, RE-PRICE WITH WP", "dim")
        log_activity(STATE, "FARE QUOTE INVALIDATED - ITINERARY CHANGED")
    if had_tickets:
        print_line("TICKETS VOIDED - ITINERARY CHANGED, REISSUE WITH TKTT OR EXCHANGE WITH WFR AFTER RE-PRICING", "dim")
        log_activity(STATE, "TICKETS VOIDED - ITINERARY CHANGED")


def format_segment_short(seg: dict) -> str:
    dinfo = seg["dinfo"]
    return (
        f"{seg['airline']}{seg['flight_num']} {seg['cls']} {dinfo.day}{dinfo.mon} "
        f"{seg['orig']}{seg['dest']} {seg['status']}{seg['seats']}  "
        f"{minutes_to_clock(seg['dep'])} {minutes_to_clock(seg['arr'])}"
    )


# ---------- name / phone / received-from ----------

_INF_RE = re.compile(r"\(INF([A-Z][A-Z\-' ]*)/([A-Z][A-Z\-' ]*)/(\d{1,2}[A-Z]{3}\d{2})\)\s*$")
_HEAD_RE = re.compile(r"^(\d{1,2})?([A-Z][A-Z\-' ]*)$")
_DOB_RE = re.compile(r"^(\d{1,2})([A-Z]{3})(\d{2})$")
_PHONE_RE = re.compile(r"^(?:/([A-Z]{3}))?(\d[\d\-]{4,14})-([A-Z]{1,3})$")


def handle_name(u: str) -> None:
    working_text = u[1:].strip()
    inf_match = _INF_RE.search(working_text)
    infant_data = None
    if inf_match:
        infant_data = {
            "surname": inf_match.group(1).strip(),
            "given": inf_match.group(2).strip(),
            "dob": inf_match.group(3),
        }
        working_text = working_text[: inf_match.start()].strip()
    if "/" not in working_text:
        print_err("FORMAT - NAME MUST BE SURNAME/GIVEN NAME")
        return
    parts = [s.strip() for s in working_text.split("/") if s.strip()]
    head_match = _HEAD_RE.match(parts[0]) if len(parts) >= 2 else None
    if not head_match:
        print_err("FORMAT - NAME MUST BE SURNAME/GIVEN NAME")
        return
    surname = head_match.group(2)
    group_count = int(head_match.group(1)) if head_match.group(1) else None
    incoming = parts[1:]
    segments = STATE.pnr["segments"]
    max_party = min(s["seats"] for s in segments) if segments else None

    # Group placeholder shorthand: -{N}TBA/TBA creates N identical "TBA/TBA" placeholder
    # passengers in one entry (real Sabre group convention - unnamed pax held with
    # identical placeholder names, distinguished only by position in the name list, not
    # synthesized unique strings) rather than spelling out N individual TBA/TBA entries.
    # Real names replace a placeholder later via X{n} (cancel that NM element) then an
    # ordinary name entry - no separate "replace" command needed.
    if group_count and group_count > 1 and len(incoming) == 1 and surname == "TBA" and incoming[0] == "TBA":
        if max_party is not None and len(STATE.pnr["names"]) + group_count > max_party:
            print_err(
                f"UNABLE TO ADD NAME - PARTY SIZE EXCEEDS SEATS SOLD ({max_party}) - "
                "SELL ADDITIONAL SEATS OR CANCEL A NAME"
            )
            return
        for _ in range(group_count):
            STATE.pnr["names"].append("TBA/TBA")
        print_line(f"NAMES ADDED - {group_count} TBA/TBA PLACEHOLDER(S) (GROUP - REPLACE WITH REAL NAMES BEFORE TICKETING)")
        log_activity(STATE, f"NAMES ADDED - {group_count} TBA/TBA PLACEHOLDER(S)")
        refresh_and_print_pnr()
        return

    if max_party is not None and len(STATE.pnr["names"]) + len(incoming) > max_party:
        print_err(
            f"UNABLE TO ADD NAME - PARTY SIZE EXCEEDS SEATS SOLD ({max_party}) - "
            "SELL ADDITIONAL SEATS OR CANCEL A NAME"
        )
        return
    added = []
    for g in incoming:
        full = f"{surname}/{g}"
        STATE.pnr["names"].append(full)
        added.append(full)
    suffix = "S" if len(added) > 1 else ""
    print_line(f"NAME{suffix} ADDED - {'  '.join(added)}")
    log_activity(STATE, f"NAME{suffix} ADDED - {'  '.join(added)}")
    if infant_data:
        dv = _DOB_RE.match(infant_data["dob"])
        day = int(dv.group(1)) if dv else 0
        if not dv or dv.group(2) not in MONTHS or day < 1 or day > 31:
            print_err("FORMAT - INVALID INFANT DOB, USE DDMONYY e.g. 12JAN26")
        else:
            adult_ref = added[-1]
            STATE.pnr["infants"].append(
                {
                    "adult": adult_ref,
                    "surname": infant_data["surname"],
                    "given": infant_data["given"],
                    "dob": infant_data["dob"],
                }
            )
            print_line(
                f"INFANT ADDED - {infant_data['surname']}/{infant_data['given']}  "
                f"DOB {infant_data['dob']}  (TRAVELS WITH {adult_ref})"
            )
            log_activity(
                STATE,
                f"INFANT ADDED - {infant_data['surname']}/{infant_data['given']}  DOB {infant_data['dob']}",
            )
    refresh_and_print_pnr()


def handle_phone(u: str) -> None:
    text = u[1:].strip()
    pm = _PHONE_RE.match(text)
    if not pm or pm.group(3).upper() not in PHONE_LOC_CODES:
        print_err(
            "FORMAT - PHONE MUST BE 9NUMBER-LOC or 9/CTYNUMBER-LOC  "
            "e.g. 9214555-1234-A or 9/DFW555-1234-A"
        )
        return
    city = pm.group(1)
    formatted = f"{'/' + city.upper() if city else ''}{pm.group(2)}-{pm.group(3).upper()}"
    STATE.pnr["phones"].append(formatted)
    print_line(f"PHONE ADDED - 9{formatted}")
    log_activity(STATE, f"PHONE ADDED - 9{formatted}")
    refresh_and_print_pnr()


def handle_received_from(u: str) -> None:
    text = u[1:].strip()
    if not text:
        print_err("FORMAT - RECEIVED FROM TEXT REQUIRED")
        return
    STATE.pnr["received_from"] = text
    print_line(f"RECEIVED FROM ADDED - {text}")
    log_activity(STATE, f"RECEIVED FROM ADDED - {text}")
    refresh_and_print_pnr()


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


TRIP_TYPE_LABELS = {"OW": "ONE WAY", "RT": "ROUND TRIP", "CT": "CIRCLE TRIP", "OJ": "OPEN JAW"}


def _shuffled(items: list, rng) -> list:
    arr = list(items)
    for i in range(len(arr) - 1, 0, -1):
        j = int(rng() * (i + 1))
        arr[i], arr[j] = arr[j], arr[i]
    return arr


def fare_quote_shop(orig: str, dest: str, booking_cls: str | None = None) -> None:
    """Real Sabre's "FQ" entry: a bare fare quote by city pair, independent of any PNR/
    itinerary - unlike price_itinerary below, there's no segment to derive a fare from, so
    this seeds off the route only and reuses the same shared spec constants (FARE_FORMULA/
    CLASS_FARE_MULT/TAX_POOL) via its own parallel calculation, one indicative total per
    booking class. Purely informational - no PNR mutation, no activity log entry, matching
    decode_airport/search_airports' existing precedent as pure lookups with no PNR side effects.
    An optional /{CLASS} suffix switches to showing that class's fare rules instead.
    """
    if orig == dest:
        print_err("FORMAT - ORIGIN AND DESTINATION CANNOT BE THE SAME")
        return
    if booking_cls and booking_cls not in CLASSES:
        print_err(f"UNKNOWN BOOKING CLASS {booking_cls} - VALID: {' '.join(CLASSES)}")
        return

    if booking_cls:
        rules = FARE_RULES.get(booking_cls)
        print_line(f"** FARE RULES **  {orig}-{dest}  CLASS {booking_cls}", "hd")
        print_line(f"  {city_name(orig)}  TO  {city_name(dest)}", "dim")
        print_blank()
        if rules:
            print_line(f"  CHANGE FEE                  USD {rules['changeFee']:.2f}")
            print_line(f"  REFUNDABLE                  {'YES' if rules['refundable'] else 'NO'}")
            print_line(f"  ADVANCE PURCHASE REQUIRED   {rules['advancePurchaseDays']} DAYS")
        else:
            print_line("  NO FARE RULE DATA ON FILE FOR THIS CLASS", "dim")
        print_blank()
        print_line("INDICATIVE ONLY - ACTUAL RULES APPLY AFTER WP", "dim")
        return

    rng = mulberry32(hash_str(f"FQ{orig}{dest}"))
    dist = FARE_FORMULA["distanceMin"] + int(rng() * FARE_FORMULA["distanceRange"])

    print_line(f"** FARE QUOTE SHOP **  {orig}-{dest}", "hd")
    print_line(f"  {city_name(orig)}  TO  {city_name(dest)}", "dim")
    print_blank()
    print_line("CLS  BASE FARE    TAXES/FEES    TOTAL", "dim")
    for cls in CLASSES:
        mult = CLASS_FARE_MULT.get(cls, 1.4)
        base_fare = round((FARE_FORMULA["baseFareCoefficient"] + dist * FARE_FORMULA["baseFarePerMile"]) * mult)

        num_taxes = FARE_FORMULA["minTaxes"] + int(rng() * FARE_FORMULA["additionalTaxesRange"])
        pool = _shuffled(TAX_POOL, rng)[:num_taxes]
        tax_total = 0.0
        for _t in pool:
            tax_total += round((FARE_FORMULA["taxAmountMin"] + rng() * FARE_FORMULA["taxAmountRange"]) * 100) / 100
        tax_total = round(tax_total * 100) / 100
        total = round((base_fare + tax_total) * 100) / 100
        print_line(f" {cls}    USD {pad(f'{base_fare:.2f}', 9)}  USD {pad(f'{tax_total:.2f}', 9)}  USD {total:.2f}")
    print_blank()
    print_line("INDICATIVE ONLY - PRICE THE ACTUAL ITINERARY WITH WP AFTER BOOKING", "dim")


def price_itinerary(mode: str, corp_code: str | None = None) -> None:
    p = STATE.pnr
    if len(p["segments"]) == 0:
        print_err("UNABLE TO PRICE - NO ITINERARY SEGMENTS")
        return
    if len(p["names"]) == 0:
        print_err("UNABLE TO PRICE - NAME FIELD REQUIRED PRIOR TO PRICING")
        return
    cancelled_seg = next((s for s in p["segments"] if s.get("cancelledByCarrier")), None)
    if cancelled_seg:
        print_err(
            f"UNABLE TO PRICE - {format_segment_short(cancelled_seg)} CANCELLED BY CARRIER - "
            "CANCEL THE SEGMENT (X{n}) AND SELL A REPLACEMENT FIRST"
        )
        return
    corporate = None
    if corp_code:
        corporate = CORPORATE_CODES.get(corp_code)
        if not corporate:
            print_err(f"UNKNOWN CORPORATE CODE {corp_code} - VALID: {' '.join(CORPORATE_CODES.keys())}")
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
        dist = FARE_FORMULA["distanceMin"] + int(rng() * FARE_FORMULA["distanceRange"])
        base_fare += round((FARE_FORMULA["baseFareCoefficient"] + dist * FARE_FORMULA["baseFarePerMile"]) * mult * s["seats"])
    if corporate:
        base_fare = round(base_fare * (1 - corporate["discount"]))

    num_taxes = FARE_FORMULA["minTaxes"] + int(rng() * FARE_FORMULA["additionalTaxesRange"])
    pool = _shuffled(TAX_POOL, rng)[:num_taxes]
    taxes = []
    tax_total = 0.0
    for t in pool:
        amt = round((FARE_FORMULA["taxAmountMin"] + rng() * FARE_FORMULA["taxAmountRange"]) * 100) / 100
        taxes.append({"code": t["code"], "label": t["label"], "amount": amt})
        tax_total += amt
    tax_total = round(tax_total * 100) / 100
    total = round((base_fare + tax_total) * 100) / 100
    fare_basis = f"{p['segments'][0]['cls']}{_trip_type(p['segments'])}"
    rules = FARE_RULES.get(p["segments"][0]["cls"])

    p["pricing"] = {
        "mode": mode,
        "base_fare": base_fare,
        "taxes": taxes,
        "tax_total": tax_total,
        "total": total,
        "fare_basis": fare_basis,
        "currency": "USD",
        "rules": rules,
        "corporate_code": {"code": corp_code, "label": corporate["label"], "discount": corporate["discount"]}
        if corporate
        else None,
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
    print_line(f"TRIP TYPE: {TRIP_TYPE_LABELS[_trip_type(p['segments'])]}", "dim")
    if corporate:
        print_line(
            f"CORPORATE CODE APPLIED - {corporate['label']} ({round(corporate['discount'] * 100)}% DISCOUNT)",
            "dim",
        )
    print_line(f"BASE FARE      USD {base_fare:.2f}")
    for t in taxes:
        print_line(f"  {t['code']}   USD {t['amount']:.2f}   {t['label']}", "dim")
    print_line(f"TAXES/FEES     USD {tax_total:.2f}")
    print_line(f"TOTAL          USD {total:.2f}", "hd")
    if rules:
        print_blank()
        print_line("FARE RULES", "dim")
        print_line(f"  CHANGE FEE                  USD {rules['changeFee']:.2f}", "dim")
        print_line(f"  REFUNDABLE                  {'YES' if rules['refundable'] else 'NO'}", "dim")
        print_line(f"  ADVANCE PURCHASE REQUIRED   {rules['advancePurchaseDays']} DAYS", "dim")
    print_blank()
    print_line("FARE QUOTE STORED - REQUIRED PRIOR TO TICKETING", "dim")
    log_activity(STATE, f"PRICED - {format_pricing_short(p['pricing'])}")
    refresh_and_print_pnr()


def format_pricing_short(pr: dict) -> str:
    return (
        f"{pr['mode']}  {pr['fare_basis']}  BASE USD{pr['base_fare']:.2f}  "
        f"TAX USD{pr['tax_total']:.2f}  TTL USD{pr['total']:.2f}"
    )


# ---------- itinerary/invoice document (EM/EMI/EMT) ----------
# Real Sabre's EM/EMI/EMT end-transaction variants mail the passenger an
# itinerary/invoice/e-ticket document. This offline simulator has no real
# email or PDF renderer in the CLI edition (that's the browser edition's
# job, see script.js's renderItineraryDocumentHTML), so the CLI equivalent
# prints the same underlying content as a formatted terminal block.

def build_itinerary_document(mode: str) -> dict:
    p = STATE.pnr
    cfg = EMAIL_DOCUMENTS[mode]
    sections = set(cfg["sections"])

    def has(name: str) -> bool:
        return name in sections

    passengers = [
        {"name": name, "infants": [inf for inf in p["infants"] if inf["adult"] == name]}
        for name in p["names"]
    ]

    return {
        "mode": mode,
        "label": cfg["label"],
        "pcc": STATE.pcc,
        "sine": STATE.sine,
        "issued": datetime.now(),
        "locator": p["locator"],
        "passengers": passengers,
        "trip_type": TRIP_TYPE_LABELS[_trip_type(p["segments"])] if p["segments"] else None,
        "segments": p["segments"] if has("segments") else [],
        "seats": p["seats"] if has("seats") else [],
        "ssrs": p["ssrs"] if has("ssrs") else [],
        "osis": p["osis"] if has("osis") else [],
        "pricing": p["pricing"] if has("pricing") else None,
        "form_of_payment": p["form_of_payment"] if has("form_of_payment") else None,
        "tickets": p["tickets"] if has("tickets") else None,
    }


def print_itinerary_document(doc: dict) -> None:
    issued = doc["issued"]
    issued_str = f"{issued.day} {MONTHS[issued.month - 1]} {issued.year}"
    sep = "-" * 60

    print_blank()
    print_line(sep, "dim")
    print_line(f"GDS TRAINER - {doc['label']}", "hd")
    print_line(
        f"ISSUED {issued_str}   AGENT {doc['sine'] or '----'}   PCC {doc['pcc'] or '----'}   "
        f"RLOC {doc['locator'] or '(NOT SAVED)'}",
        "dim",
    )
    print_line(sep, "dim")

    print_line("PASSENGER(S)", "hd")
    if doc["passengers"]:
        for pax in doc["passengers"]:
            print_line(f"  {pax['name']}")
            for inf in pax["infants"]:
                print_line(f"    + INFANT: {inf['surname']}/{inf['given']}  DOB {inf['dob']}", "dim")
    else:
        print_line("  NO PASSENGERS ON FILE", "dim")

    if doc["segments"]:
        seats_by_seg: dict[int, list[str]] = {}
        for s in doc["seats"]:
            seats_by_seg.setdefault(s["seg_idx"], []).append(s["seat"])
        print_blank()
        print_line(f"ITINERARY - {doc['trip_type']}" if doc["trip_type"] else "ITINERARY", "hd")
        for i, s in enumerate(doc["segments"]):
            status_label = SEGMENT_STATUS_LABELS.get(s["status"], s["status"])
            seat_list = ", ".join(seats_by_seg.get(i, [])) or "-"
            print_line(
                f"  {s['airline']}{s['flight_num']} {s['cls']}  {s['dinfo'].day}{s['dinfo'].mon} {s['dinfo'].weekday}  "
                f"{city_name(s['orig'])} ({s['orig']}) {minutes_to_clock(s['dep'])} -> "
                f"{city_name(s['dest'])} ({s['dest']}) {minutes_to_clock(s['arr'])}  {status_label}  SEAT {seat_list}"
            )

    if doc["ssrs"]:
        print_blank()
        print_line("SPECIAL SERVICE REQUESTS", "hd")
        for r in doc["ssrs"]:
            print_line(f"  {r['text']}")

    if doc["osis"]:
        print_blank()
        print_line("OTHER SERVICE INFORMATION", "hd")
        for o in doc["osis"]:
            print_line(f"  {o['text']}")

    if doc["pricing"]:
        pr = doc["pricing"]
        print_blank()
        print_line("FARE SUMMARY", "hd")
        print_line(f"  BASE FARE      USD {pr['base_fare']:.2f}")
        for t in pr["taxes"]:
            print_line(f"    {t['code']}   USD {t['amount']:.2f}   {t['label']}", "dim")
        print_line(f"  TAXES/FEES     USD {pr['tax_total']:.2f}")
        print_line(f"  TOTAL          USD {pr['total']:.2f}", "hd")
        if pr["rules"]:
            print_line(
                f"  CHANGE FEE USD {pr['rules']['changeFee']:.2f}   "
                f"REFUNDABLE {'YES' if pr['rules']['refundable'] else 'NO'}   "
                f"ADVANCE PURCHASE {pr['rules']['advancePurchaseDays']} DAYS",
                "dim",
            )

    if doc["form_of_payment"]:
        print_blank()
        print_line("FORM OF PAYMENT", "hd")
        print_line(f"  {doc['form_of_payment']['display']}")

    if doc["tickets"] is not None:
        print_blank()
        print_line("TICKET NUMBERS", "hd")
        if doc["tickets"]:
            for t in doc["tickets"]:
                label = t["passenger"] + (" (INFANT)" if t["is_infant"] else "")
                print_line(f"  {pad(label, 28)} {t['ticket_num']}")
        else:
            print_line("  NOT YET TICKETED", "dim")

    print_blank()
    print_line(
        "This is an educational simulation, not connected to any real airline or GDS "
        "network - not a real travel document.",
        "dim",
    )
    print_line(sep, "dim")


# ---------- ticketing arrangement ----------

def add_ticketing_at_will() -> None:
    STATE.pnr["ticketing"] = "7TAW/ (TICKETING AT WILL - TICKET ON OR BEFORE DEPARTURE)"
    print_line("TICKETING ARRANGEMENT ADDED - 7TAW/")
    log_activity(STATE, "TICKETING ARRANGEMENT ADDED - 7TAW/")
    refresh_and_print_pnr()


def add_ticketing_at_will_dated(day: str, mon: str, time: str | None) -> None:
    dinfo = parse_date(day, mon)
    if dinfo is None:
        print_err("INVALID DATE - CHECK ENTRY AND REENTER")
        return
    time_suffix = f"/{time}" if time else "/"
    queued = f" {time}" if time else ""
    STATE.pnr["ticketing"] = (
        f"7TAW{dinfo.day}{dinfo.mon}{time_suffix} "
        f"(TICKETING AT WILL - QUEUED {dinfo.day}{dinfo.mon}{queued})"
    )
    print_line(f"TICKETING ARRANGEMENT ADDED - 7TAW{dinfo.day}{dinfo.mon}{time_suffix}")
    log_activity(STATE, f"TICKETING ARRANGEMENT ADDED - 7TAW{dinfo.day}{dinfo.mon}{time_suffix}")
    refresh_and_print_pnr()


def add_ticketing_time_limit(day: str, mon: str, time: str) -> None:
    dinfo = parse_date(day, mon)
    if dinfo is None:
        print_err("INVALID DATE - CHECK ENTRY AND REENTER")
        return
    STATE.pnr["ticketing"] = (
        f"7TAX{dinfo.day}{dinfo.mon}/{time} (TIME LIMIT - TICKET BY {dinfo.day}{dinfo.mon} {time})"
    )
    print_line(f"TICKETING ARRANGEMENT ADDED - 7TAX{dinfo.day}{dinfo.mon}/{time}")
    log_activity(STATE, f"TICKETING ARRANGEMENT ADDED - 7TAX{dinfo.day}{dinfo.mon}/{time}")
    refresh_and_print_pnr()


# ---------- seat maps ----------

def get_seat_layout(equip: str | None) -> dict:
    return SEAT_LAYOUTS.get(equip, SEAT_LAYOUTS["_default"])


def layout_decks(layout: dict) -> list[dict]:
    """Normalizes a layout into its deck list. Most aircraft are single-deck,
    so they're wrapped as one unlabeled deck - everything downstream (map
    generation, printing, seat validation) only ever has to handle the
    multi-deck shape. Double-deckers (747/A380) supply their own `decks`
    list in spec/reference-data.json with non-overlapping row ranges, so a
    seat's row number alone is enough to find its deck."""
    return layout.get("decks") or [
        {"label": None, "rowStart": 1, "rows": layout["rows"], "cols": layout["cols"]}
    ]


def _seat_cell(s: str) -> str:
    return f" {s} "


def get_seat_map(seg: dict) -> dict:
    layout = get_seat_layout(seg.get("equip"))
    decks = layout_decks(layout)
    dinfo = seg["dinfo"]
    seed = hash_str(
        f"{seg['airline']}{seg['flight_num']}{dinfo.day}{dinfo.mon}{seg['orig']}{seg['dest']}SEATMAP"
    )
    rng = mulberry32(seed)
    rows = []
    occupied: set[str] = set()
    for deck in decks:
        cols = list("".join(deck["cols"]))
        for i in range(deck["rows"]):
            r = deck["rowStart"] + i
            seats = []
            for col in cols:
                occ = rng() < 0.4
                if occ:
                    occupied.add(f"{r}{col}")
                seats.append(occ)
            rows.append({"num": r, "seats": seats, "deck": deck})
    return {"rows": rows, "occupied": occupied, "layout": layout, "decks": decks}


def _seat_map_header_line(deck: dict) -> str:
    groups = ["".join(_seat_cell(letter) for letter in group) for group in deck["cols"]]
    return "      " + "   ".join(groups)


def _seat_map_row_line(row: dict, mine: set[str]) -> str:
    pos = 0
    groups = []
    for group in row["deck"]["cols"]:
        cells = []
        for i, col in enumerate(group):
            seat_id = f"{row['num']}{col}"
            occ = row["seats"][pos + i]
            cells.append(_seat_cell("*" if seat_id in mine else ("X" if occ else ".")))
        groups.append("".join(cells))
        pos += len(group)
    return f" {pad(row['num'], 3)}  " + "   ".join(groups)


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
    for deck in smap["decks"]:
        if deck["label"]:
            print_line(deck["label"], "dim")
        print_line(_seat_map_header_line(deck), "dim")
        for row in smap["rows"]:
            if row["deck"] is deck:
                print_line(_seat_map_row_line(row, mine))
        print_blank()
    print_line(". OPEN   X OCCUPIED   * YOUR ASSIGNMENT", "dim")
    if len(STATE.pnr["names"]) > 1:
        print_line(f"ASSIGN WITH: 4{n}-{{SEAT}}/{{PAX#}}   e.g. 4{n}-14A/1 (multiple passengers on file - required)", "dim")
    else:
        print_line(f"ASSIGN WITH: 4{n}-{{SEAT}}   e.g. 4{n}-14A", "dim")


def assign_seat(n: int, seat_str: str, pax_str: str | None = None) -> None:
    segments = STATE.pnr["segments"]
    if n < 1 or n > len(segments):
        print_err("INVALID SEGMENT NUMBER - CHECK ITINERARY")
        return
    seg = segments[n - 1]
    row_match = re.match(r"^(\d{1,2})([A-HJK])$", seat_str)
    row = int(row_match.group(1))
    letter = row_match.group(2)
    smap = get_seat_map(seg)
    deck = next(
        (d for d in smap["decks"] if row >= d["rowStart"] and row < d["rowStart"] + d["rows"]),
        None,
    )
    if deck is None:
        max_row = max(d["rowStart"] + d["rows"] - 1 for d in smap["decks"])
        print_err(f"INVALID SEAT ROW - VALID RANGE 1-{max_row}")
        return
    if letter not in "".join(deck["cols"]):
        print_err(f"INVALID SEAT LETTER {letter} - VALID: {' '.join(deck['cols'])}")
        return
    if seat_str in smap["occupied"]:
        print_err(f"SEAT {seat_str} NOT AVAILABLE - SELECT ANOTHER (SEE SEAT MAP: 4{n})")
        return
    if any(s["seg_idx"] == n - 1 and s["seat"] == seat_str for s in STATE.pnr["seats"]):
        print_err(f"SEAT {seat_str} ALREADY ASSIGNED ON THIS SEGMENT")
        return

    names = STATE.pnr["names"]
    if pax_str:
        pax_num = int(pax_str)
        if pax_num < 1 or pax_num > len(names):
            print_err("INVALID PASSENGER NUMBER - CHECK NAME FIELD")
            return
    elif len(names) > 1:
        # More than one passenger on file - which of them gets this seat is no longer
        # unambiguous (unlike the solo case below), so this must be explicit rather than
        # silently leaving the assignment unattributed (which would make it impossible to
        # know which side of a later divide it belongs to - see divide_pnr).
        print_err(f"MULTIPLE PASSENGERS ON FILE - SPECIFY PASSENGER NUMBER (ENTRY: 4{n}-{seat_str}/{{PAX#}})")
        return
    else:
        # Exactly one passenger (or none yet) - unambiguous, so default rather than force
        # every solo booking to type a passenger number it couldn't possibly need.
        pax_num = 1 if len(names) == 1 else None

    STATE.pnr["seats"].append({"seg_idx": n - 1, "seat": seat_str, "pax": pax_num})
    pax_suffix = f"  PAX {pax_num} ({names[pax_num - 1]})" if pax_num else ""
    print_line(f"SEAT ASSIGNED - SEG{n} {seat_str}{pax_suffix}")
    log_activity(STATE, f"SEAT ASSIGNED - SEG{n} {seat_str}{pax_suffix}")
    refresh_and_print_pnr()


# ---------- form of payment ----------

def mask_card(num: str) -> str:
    return "X" * max(0, len(num) - 4) + num[-4:]


def add_fop_cash() -> None:
    STATE.pnr["form_of_payment"] = {"type": "CASH", "display": "CASH"}
    print_line("FORM OF PAYMENT ADDED - CASH")
    log_activity(STATE, "FORM OF PAYMENT ADDED - CASH")
    refresh_and_print_pnr()


def add_fop_check() -> None:
    STATE.pnr["form_of_payment"] = {"type": "CHECK", "display": "CHECK"}
    print_line("FORM OF PAYMENT ADDED - CHECK")
    log_activity(STATE, "FORM OF PAYMENT ADDED - CHECK")
    refresh_and_print_pnr()


def add_fop_credit_card(card_type: str, num: str, mm_str: str, yy: str) -> None:
    if card_type not in CARD_TYPES:
        print_err(f"UNKNOWN CARD TYPE {card_type} - VALID: {' '.join(CARD_TYPES.keys())}")
        return
    mm = int(mm_str)
    if mm < 1 or mm > 12:
        print_err("INVALID EXPIRY MONTH - USE MMYY")
        return
    display = f"CC {card_type} {mask_card(num)}  EXP {mm_str}/{yy}  ({CARD_TYPES[card_type]})"
    STATE.pnr["form_of_payment"] = {"type": "CC", "display": display}
    print_line(f"FORM OF PAYMENT ADDED - {display}")
    log_activity(STATE, f"FORM OF PAYMENT ADDED - {display}")
    refresh_and_print_pnr()


# ---------- special service requests / other service info ----------

def add_fqtv(airline: str, num: str, pax_str: str | None = None, tier_code: str | None = None) -> None:
    pax_num = int(pax_str) if pax_str else None
    if pax_num and (pax_num < 1 or pax_num > len(STATE.pnr["names"])):
        print_err("INVALID PASSENGER NUMBER - CHECK NAME FIELD")
        return
    text = f"FQTV {airline} FREQUENT FLYER NUMBER  {airline}{num}"
    if pax_num:
        text += f"  PAX {pax_num} ({STATE.pnr['names'][pax_num - 1]})"
    if tier_code:
        tier_name = LOYALTY_TIERS.get(tier_code)
        if not tier_name:
            print_err(f"UNKNOWN LOYALTY TIER {tier_code} - VALID: {' '.join(LOYALTY_TIERS.keys())}")
            return
        text += f"  TIER: {tier_name}"
    STATE.pnr["ssrs"].append({"code": "FQTV", "text": text})
    print_line(f"SSR ADDED - {text}")
    log_activity(STATE, f"SSR ADDED - {text}")
    refresh_and_print_pnr()


def _resolve_doc_traveler(pax_num: int, infant_num: int | None) -> tuple[str, str]:
    """Resolves a DOCS entry's traveler to a Sabre-style "1"/"1.1" label + display
    name - infants have no name-field entry of their own, so P{n}.{m} means the
    m-th infant travelling with passenger n (see add_docs)."""
    names = STATE.pnr["names"]
    adult_name = names[pax_num - 1] if pax_num - 1 < len(names) else "?"
    if not infant_num:
        return str(pax_num), adult_name
    adult_infants = [inf for inf in STATE.pnr["infants"] if inf["adult"] == adult_name]
    if infant_num - 1 < len(adult_infants):
        inf = adult_infants[infant_num - 1]
        name = f"{inf['surname']}/{inf['given']} (INFANT)"
    else:
        name = "?"
    return f"{pax_num}.{infant_num}", name


def add_docs(
    doc_type: str,
    country: str,
    number: str,
    nationality: str,
    dob: str,
    sex: str,
    expiry: str,
    pax_str: str,
    infant_str: str | None = None,
) -> None:
    desc = DOCUMENT_TYPES.get(doc_type)
    if not desc:
        print_err(f"UNKNOWN DOCUMENT TYPE {doc_type} - VALID: {' '.join(DOCUMENT_TYPES.keys())}")
        return
    pax_num = int(pax_str) if pax_str.isdigit() else 0
    if not pax_num or pax_num < 1 or pax_num > len(STATE.pnr["names"]):
        print_err("INVALID PASSENGER NUMBER - CHECK NAME FIELD")
        return
    infant_num: int | None = None
    if infant_str:
        infant_num = int(infant_str) if infant_str.isdigit() else 0
        adult_name = STATE.pnr["names"][pax_num - 1]
        adult_infants = [inf for inf in STATE.pnr["infants"] if inf["adult"] == adult_name]
        if not infant_num or infant_num < 1 or infant_num > len(adult_infants):
            print_err(
                f"INVALID INFANT NUMBER - PASSENGER {pax_num} ({adult_name}) HAS "
                f"{len(adult_infants)} INFANT(S) ON FILE"
            )
            return
    dob_match = _DOB_RE.match(dob)
    dob_day = int(dob_match.group(1)) if dob_match else 0
    if not dob_match or dob_match.group(2) not in MONTHS or dob_day < 1 or dob_day > 31:
        print_err("FORMAT - INVALID DOB, USE DDMONYY e.g. 12JAN90")
        return
    exp_match = _DOB_RE.match(expiry)
    exp_day = int(exp_match.group(1)) if exp_match else 0
    if not exp_match or exp_match.group(2) not in MONTHS or exp_day < 1 or exp_day > 31:
        print_err("FORMAT - INVALID EXPIRY DATE, USE DDMONYY e.g. 25DEC30")
        return
    entry = {
        "type": doc_type, "desc": desc, "country": country, "number": number,
        "nationality": nationality, "dob": dob, "sex": sex, "expiry": expiry,
        "pax": pax_num, "infant_num": infant_num,
    }
    STATE.pnr["docs"].append(entry)
    label, name = _resolve_doc_traveler(pax_num, infant_num)
    text = (
        f"{desc} {country} {number}  NATIONALITY {nationality}  DOB {dob}  {sex}  "
        f"EXP {expiry}  PAX {label} ({name})"
    )
    print_line(f"DOCUMENT ADDED - {text}")
    log_activity(STATE, f"DOCUMENT ADDED - {text}")
    refresh_and_print_pnr()


def handle_general_remark(u: str) -> None:
    text = u[1:].strip()
    if not text:
        print_err("FORMAT - REMARK TEXT REQUIRED")
        return
    STATE.pnr["remarks"].append(text)
    print_line(f"GENERAL REMARK ADDED - {text}")
    log_activity(STATE, f"GENERAL REMARK ADDED - {text}")
    refresh_and_print_pnr()


def add_osi(airline: str, raw_text: str) -> None:
    text = raw_text.strip()
    if not text:
        print_err("FORMAT - OSI REQUIRES FREE TEXT, e.g. 3OSIAA VIP PASSENGER")
        return
    full_text = f"{airline} {text}"
    STATE.pnr["osis"].append({"airline": airline, "text": full_text})
    print_line(f"OSI ADDED - {full_text}")
    log_activity(STATE, f"OSI ADDED - {full_text}")
    refresh_and_print_pnr()


def add_ssr(code: str, pax_str: str | None, free_text_raw: str | None) -> None:
    desc = SSR_CODES.get(code)
    if not desc:
        print_err(f"UNKNOWN SSR CODE {code} - TYPE HELP FOR LIST")
        return
    pax_num = int(pax_str) if pax_str else None
    if pax_num and (pax_num < 1 or pax_num > len(STATE.pnr["names"])):
        print_err("INVALID PASSENGER NUMBER - CHECK NAME FIELD")
        return
    free_text = free_text_raw.strip() if free_text_raw else ""
    text = f"{code} {desc}"
    if pax_num:
        text += f"  PAX {pax_num} ({STATE.pnr['names'][pax_num - 1]})"
    if free_text:
        text += f"  /{free_text}"
    STATE.pnr["ssrs"].append({"code": code, "text": text})
    print_line(f"SSR ADDED - {text}")
    log_activity(STATE, f"SSR ADDED - {text}")
    refresh_and_print_pnr()


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

# Indices (into `segments`) of every OTHER segment sharing segments[idx]'s marriedGroup -
# empty if that segment isn't married. Shared by build_elements' display text and
# cancel_elements' enforcement below.
def married_partner_indices(segments: list[dict], idx: int) -> list[int]:
    group = segments[idx].get("marriedGroup")
    if not group:
        return []
    return [i for i, s in enumerate(segments) if i != idx and s.get("marriedGroup") == group]


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
    for i, d in enumerate(p["docs"]):
        label, name = _resolve_doc_traveler(d["pax"], d.get("infant_num"))
        els.append(
            {
                "kind": "docs",
                "idx": i,
                "label": "DOC",
                "text": f"{d['desc']} {d['country']} {d['number']}  NATIONALITY {d['nationality']}  "
                f"DOB {d['dob']}  {d['sex']}  EXP {d['expiry']}  PAX {label} ({name})",
            }
        )
    for i, s in enumerate(p["segments"]):
        partners = married_partner_indices(p["segments"], i)
        married_note = f"  MARRIED TO {','.join(f'SEG{j + 1}' for j in partners)}" if partners else ""
        els.append(
            {
                "kind": "segment",
                "idx": i,
                "label": f"SEG{i + 1}",
                "text": format_segment_short(s) + f"  {s['dinfo'].weekday}" + married_note,
            }
        )
    for i, st in enumerate(p["seats"]):
        pax_num = st.get("pax")
        if pax_num and pax_num - 1 < len(p["names"]):
            pax_suffix = f"  PAX {pax_num} ({p['names'][pax_num - 1]})"
        elif pax_num:
            pax_suffix = f"  PAX {pax_num} (?)"
        else:
            pax_suffix = ""
        els.append(
            {
                "kind": "seat",
                "idx": i,
                "label": "SEAT",
                "text": f"SEG{st['seg_idx'] + 1} - SEAT {st['seat']}{pax_suffix}",
            }
        )
    for i, r in enumerate(p["ssrs"]):
        els.append({"kind": "ssr", "idx": i, "label": "SSR", "text": r["text"]})
    for i, o in enumerate(p["osis"]):
        els.append({"kind": "osi", "idx": i, "label": "OSI", "text": o["text"]})
    for i, r in enumerate(p["remarks"]):
        els.append({"kind": "remark", "idx": i, "label": "RM", "text": r})
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
    if STATE.pnr["segments"]:
        print_line(f"  TRIP TYPE: {TRIP_TYPE_LABELS[_trip_type(STATE.pnr['segments'])]}", "dim")
    for e in STATE.last_display:
        print_line(f" {pad(e['num'], 2)}  {pad(e['label'], 5)} {e['text']}")

    # Persistent (not show-once): the only real fix is removing the dead segment, so this
    # keeps firing on every redisplay until X{n} actually splices it out of p["segments"] -
    # there's no separate acknowledgement flag to set, unlike the show-once waitlist notice
    # below, because re-pricing alone (which resolves the schedule-change alert) can't
    # resolve this one - price_itinerary refuses outright while the flag is still on file.
    cancelled_segs = [s for s in STATE.pnr["segments"] if s.get("cancelledByCarrier")]
    if cancelled_segs:
        print_blank()
        print_line("** FLIGHT CANCELLED BY CARRIER - CANCEL THE SEGMENT(S) AND SELL A REPLACEMENT **", "err")
        for s in cancelled_segs:
            print_line(f"  {format_segment_short(s)}", "dim")

    # Naturally stops once the agent re-prices (WP) - reuses the existing pricing-null-
    # means-stale convention rather than a separate acknowledgement flag.
    changed_segs = [s for s in STATE.pnr["segments"] if s.get("scheduleChanged")]
    if not STATE.pnr["pricing"] and changed_segs:
        print_blank()
        print_line("** SCHEDULE CHANGE ON FILE - RE-PRICE (WP), THEN EXCHANGE (WFR) OR REISSUE (TKTT) **", "err")
        for s in changed_segs:
            print_line(f"  {format_segment_short(s)}", "dim")

    # A fresh re-price already exists and there's still a prior ticket to apply toward it -
    # ready for WFR{TICKET#}.
    if STATE.pnr["pricing"] and STATE.pnr["prior_tickets"]:
        print_blank()
        print_line("** PRIOR TICKET ON FILE - EXCHANGE WITH WFR{TICKET#} OR REISSUE FRESH WITH TKTT **", "dim")
        for t in STATE.pnr["prior_tickets"]:
            label = t["passenger"] + (" (INF)" if t["is_infant"] else "")
            print_line(f"  {label}  {t['ticket_num']}", "dim")

    # Show-once (not show-until-resolved like the schedule-change alert above): clearing a
    # waitlist needs no follow-up action, so this fires on the next redisplay after clearing
    # (most likely QN18 or *{LOCATOR}) and never again - waitlistClearAcked is set as part of
    # this same print pass.
    cleared_segs = [s for s in STATE.pnr["segments"] if s.get("waitlistCleared") and not s.get("waitlistClearAcked")]
    if cleared_segs:
        print_blank()
        print_line("** WAITLIST CLEARED - SEGMENT(S) NOW CONFIRMED **", "hd")
        for s in cleared_segs:
            print_line(f"  {format_segment_short(s)}", "dim")
            s["waitlistClearAcked"] = True


def remove_element(e: dict) -> None:
    p = STATE.pnr
    kind, idx = e["kind"], e["idx"]
    if kind == "name":
        del p["names"][idx]
    elif kind == "infant":
        del p["infants"][idx]
    elif kind == "docs":
        del p["docs"][idx]
    elif kind == "remark":
        del p["remarks"][idx]
    elif kind == "segment":
        del p["segments"][idx]
        _clear_pricing_and_tickets(p)
        new_seats = []
        for st in p["seats"]:
            if st["seg_idx"] == idx:
                continue
            if st["seg_idx"] > idx:
                new_seats.append({**st, "seg_idx": st["seg_idx"] - 1})
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
        _clear_pricing_and_tickets(p)
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

    # Married segments must be cancelled together - block the whole command (no partial
    # cancellation) if a request names only some of a married group's currently-displayed
    # element numbers.
    for n in uniq_desc:
        e = next((x for x in STATE.last_display if x["num"] == n), None)
        if not e or e["kind"] != "segment":
            continue
        for partner_idx in married_partner_indices(STATE.pnr["segments"], e["idx"]):
            partner_el = next(
                (x for x in STATE.last_display if x["kind"] == "segment" and x["idx"] == partner_idx), None
            )
            if partner_el and partner_el["num"] not in uniq_desc:
                print_err(
                    f"UNABLE TO CANCEL - ELEMENT {n} IS MARRIED TO ELEMENT {partner_el['num']} "
                    f"- CANCEL BOTH TOGETHER (X{n},{partner_el['num']})"
                )
                return

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
    _clear_pricing_and_tickets(p)
    p["seats"] = []
    print_line("ITINERARY CANCELLED")
    log_activity(STATE, "ITINERARY CANCELLED")
    refresh_and_print_pnr()


def handle_cancel(range_str: str) -> None:
    nums: list[int] = []
    valid = True
    for part in range_str.split(","):
        if "-" in part:
            bounds = part.split("-")
            if len(bounds) != 2:
                valid = False
                break
            a = int(bounds[0]) if bounds[0].isdigit() else 0
            b = int(bounds[1]) if bounds[1].isdigit() else 0
            if not a or not b or a > b:
                valid = False
                break
            nums.extend(range(a, b + 1))
        else:
            v = int(part) if part.isdigit() else 0
            if not v:
                valid = False
                break
            nums.append(v)
    if not valid or not nums:
        print_err("INVALID ELEMENT RANGE - CHECK ENTRY AND REENTER")
        return
    cancel_elements(nums)


def ignore_pnr() -> None:
    STATE.pnr = fresh_pnr()
    STATE.last_display = []
    print_line("IGNORED - PNR NOT SAVED")


# ---------- end transaction ----------

def gen_locator() -> str:
    chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    while True:
        s = "".join(random.choice(chars) for _ in range(6))
        if s not in STATE.history:
            return s


# Real airline schedule changes are airline-initiated, not something an agent types - the
# honest equivalent in a single-user trainer is a one-time, deterministic seeded check per
# segment. Seeded off flight+route+date identity only (NOT the PNR's locator, which is
# genuinely random per gen_locator()) so the same flight+route+date always gives the same
# outcome regardless of which PNR it ends up on - matching real life (a schedule change
# happens to a flight, affecting every booking on it, not to one lucky/unlucky PNR) and
# keeping this reproducible for training/testing instead of varying every run. The
# scheduleChanged flag (not the seed) is what stops it from re-firing on a later save of the
# same segment. The mutation itself has no dedicated print (no "an airline changed your
# flight" banner) - it's auto-queued to queue "1" (SCHEDULE CHANGE, spec/reference-data.json's
# queueCategories) and only surfaces via the ordinary channels a real agent already checks:
# QC/QN1, or the alert refresh_and_print_pnr prints below whenever a redisplay (ER's own, *R,
# or after QN1) shows an unpriced, changed segment. ET's redisplay is skipped (work area
# cleared instead), so ET alone doesn't reveal it - a later *{LOCATOR}/QN1 does.
# Same seeded-check-at-save-time pattern, for the third real IROP outcome besides a time
# shift or a waitlist clearing: the carrier drops the flight entirely. Distinct hash prefix
# (FLTCXL) so it can never collide with schedule change's (SKEDCHG) or waitlist clearing's
# (WLCLEAR) seed for the same flight. Only ever rolled against currently-HK segments - an
# HL segment was never confirmed, so "cancelled" doesn't apply to it (waitlist clearing owns
# that lane), and this function's own cancelledByCarrier flag both gates re-rolling on a
# later save (like scheduleChanged) and, via the guard added to _apply_schedule_changes below,
# keeps the two outcomes mutually exclusive - a flight can't be both time-shifted and
# cancelled in the same pass. Deliberately doesn't remove the segment or auto-rebook: real
# life leaves the dead segment on the PNR for the agent to see and act on, same as this does
# (status flips to UN, a real Sabre action code) - price_itinerary refuses to price while one
# is on file, forcing the correct workflow (cancel it with X{n}, sell a replacement, WP
# again) rather than silently pricing around a flight that no longer exists.
def _apply_flight_cancellation(p: dict) -> None:
    any_cancelled = False
    for seg in p["segments"]:
        if seg["status"] != "HK" or seg.get("cancelledByCarrier"):
            continue
        seed = hash_str(
            f"FLTCXL{seg['airline']}{seg['flight_num']}{seg['orig']}{seg['dest']}"
            f"{seg['dinfo'].day}{seg['dinfo'].mon}{seg['dinfo'].year}"
        )
        rng = mulberry32(seed)
        if rng() >= FLIGHT_CANCELLATION["chance"]:
            continue
        seg["status"] = "UN"
        seg["cancelledByCarrier"] = True
        log_activity(
            STATE,
            f"FLIGHT CANCELLED BY CARRIER - {seg['airline']}{seg['flight_num']} "
            f"{seg['orig']}{seg['dest']} {seg['dinfo'].day}{seg['dinfo'].mon} - REBOOKING REQUIRED",
        )
        any_cancelled = True
    if any_cancelled:
        _clear_pricing_and_tickets(p)
        STATE.queues.setdefault("2", [])
        if p["locator"] not in STATE.queues["2"]:
            STATE.queues["2"].append(p["locator"])


def _apply_schedule_changes(p: dict) -> None:
    any_changed = False
    for seg in p["segments"]:
        if seg.get("scheduleChanged") or seg.get("cancelledByCarrier"):
            continue
        seed = hash_str(
            f"SKEDCHG{seg['airline']}{seg['flight_num']}{seg['orig']}{seg['dest']}"
            f"{seg['dinfo'].day}{seg['dinfo'].mon}{seg['dinfo'].year}"
        )
        rng = mulberry32(seed)
        if rng() >= SCHEDULE_CHANGE["chance"]:
            continue
        magnitude = SCHEDULE_CHANGE["minShiftMinutes"] + int(
            rng() * (SCHEDULE_CHANGE["maxShiftMinutes"] - SCHEDULE_CHANGE["minShiftMinutes"])
        )
        shift = magnitude * (-1 if rng() < 0.5 else 1)
        seg["dep"] += shift
        seg["arr"] += shift
        seg["scheduleChanged"] = True
        log_activity(
            STATE,
            f"SCHEDULE CHANGE - {seg['airline']}{seg['flight_num']} {seg['orig']}{seg['dest']} "
            f"NOW {minutes_to_clock(seg['dep'])}-{minutes_to_clock(seg['arr'])}",
        )
        any_changed = True
    if any_changed:
        _clear_pricing_and_tickets(p)
        STATE.queues.setdefault("1", [])
        if p["locator"] not in STATE.queues["1"]:
            STATE.queues["1"].append(p["locator"])


# Same deterministic-seeded-check-at-save-time pattern as _apply_schedule_changes, for
# queue_categories["18"] (WAITLIST CLEARED) - previously unused, same as "1" was. Deltas
# from schedule change: (1) flips seg["status"] HL->HK instead of shifting dep/arr - same
# flight/class/fare, not an itinerary change, so pricing/tickets are never touched here;
# (2) the seed includes seg["cls"] (waitlist status is class-specific) and uses a distinct
# hash prefix so it can never collide with schedule change's seed for the same flight;
# (3) no idempotency flag is needed to gate the roll itself - only currently-HL segments are
# considered, and a cleared segment becomes HK immediately, so it naturally drops out.
# waitlistCleared/waitlistClearAcked exist only to drive the show-once notice in
# refresh_and_print_pnr above, not to gate this function.
def _apply_waitlist_clearing(p: dict) -> None:
    for seg in p["segments"]:
        if seg["status"] != "HL":
            continue
        seed = hash_str(
            f"WLCLEAR{seg['airline']}{seg['flight_num']}{seg['orig']}{seg['dest']}{seg['cls']}"
            f"{seg['dinfo'].day}{seg['dinfo'].mon}{seg['dinfo'].year}"
        )
        rng = mulberry32(seed)
        if rng() >= WAITLIST_CLEAR["chance"]:
            continue
        seg["status"] = "HK"
        seg["waitlistCleared"] = True
        seg["waitlistClearAcked"] = False
        log_activity(
            STATE,
            f"WAITLIST CLEARED - {seg['airline']}{seg['flight_num']} {seg['orig']}{seg['dest']} "
            f"{seg['cls']} NOW CONFIRMED (WAS WAITLISTED)",
        )
        STATE.queues.setdefault("18", [])
        if p["locator"] not in STATE.queues["18"]:
            STATE.queues["18"].append(p["locator"])


def end_transaction(mode: str) -> None:
    p = STATE.pnr

    # Cancelling a previously-saved PNR down to zero segments (XI, or X{n} against every
    # segment) and then ER/ET is a real, supported GDS workflow distinct from creating a
    # new PNR - none of the standard completeness fields (name, fare quote, phone, RF,
    # FOP, ticketing) are meaningful for an itinerary that no longer exists. Without this,
    # the "segments" completeness rule would permanently trap the cancellation in the work
    # area - it could never be committed, since a brand-new PNR still correctly requires a
    # segment. Restricted to ER/ET; EM/EMI/EMT generate a customer document, which makes
    # no sense for a cancelled itinerary, so those still go through the normal gate below.
    cancelling = bool(p["locator"]) and not p["segments"] and mode in ("ER", "ET")

    if not cancelling:
        incomplete = _first_incomplete_message("end_transaction")
        if incomplete:
            print_err(incomplete)
            return

        # Real groups (10+ passengers) need a deposit on file before the PNR can be saved -
        # conditional on party size, so it's bespoke rather than a spec/pnr-completeness.json
        # rule (same precedent as divide_pnr's "at least one passenger must remain" check).
        if len(p["names"]) >= 10 and not any(r["code"] == "DEPS" for r in p["ssrs"]):
            print_err("PNR INCOMPLETE - GROUP DEPOSIT REQUIRED FOR 10+ PASSENGERS (ENTRY: 3DEPS)")
            return

    if not p["locator"]:
        p["locator"] = gen_locator()

    if cancelling:
        log_activity(STATE, f"PNR CANCELLED ({mode}) - ALL SEGMENTS REMOVED - RLOC {p['locator']}")
        STATE.history[p["locator"]] = copy.deepcopy(p)
        print_line("PNR CANCELLED - ALL ITINERARY SEGMENTS REMOVED", "hd")
        print_line(f"  RLOC: {p['locator']}")
    else:
        _apply_flight_cancellation(p)
        _apply_schedule_changes(p)
        _apply_waitlist_clearing(p)
        log_activity(STATE, f"PNR SAVED ({mode}) - RLOC {p['locator']}")
        STATE.history[p["locator"]] = copy.deepcopy(p)

        now = datetime.now()
        ts = f"{now.day}{MONTHS[now.month - 1]}  {minutes_to_clock(now.hour * 60 + now.minute)}"
        print_line("END OF TRANSACTION COMPLETE", "hd")
        print_line(f"  {ts}   RLOC: {p['locator']}")

        if mode in EMAIL_DOCUMENTS:
            doc = build_itinerary_document(mode)
            print_line(f"{EMAIL_DOCUMENTS[mode]['label']} DOCUMENT GENERATED", "dim")
            log_activity(STATE, f"{EMAIL_DOCUMENTS[mode]['label']} DOCUMENT SENT ({mode})")
            print_itinerary_document(doc)

    if mode == "ET" or mode in EMAIL_DOCUMENTS:
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


# ---------- divide (SP) ----------
# Only `names` (by array index) and `docs` (an explicit pax index) are unambiguously
# per-passenger in this PNR model - infants link only by matching adult name string,
# seats link only to a segment (not a passenger) and aren't reliably attributable, and
# SSRs bake any pax number into free text only. So: names/infants(by adult name)/docs
# (reindexed, same pattern as seat_idx after a segment cancel) move to the new PNR;
# segments/phones/received_from/remarks/osis/ssrs/form_of_payment/ticketing are copied
# (real Sabre divide keeps the itinerary in both resulting PNRs); seats are dropped from
# the new PNR (no passenger attribution to decide which seat goes where).

def divide_pnr(nums_str: str) -> None:
    p = STATE.pnr
    incomplete = _first_incomplete_message("divide_pnr")
    if incomplete:
        print_err(incomplete)
        return

    uniq = sorted(set(int(s) for s in nums_str.split(",")))
    for n in uniq:
        if n < 1 or n > len(p["names"]):
            print_err("INVALID PASSENGER NUMBER - CHECK ENTRY AND REENTER")
            return
    if len(uniq) >= len(p["names"]):
        print_err("UNABLE TO DIVIDE - AT LEAST ONE PASSENGER MUST REMAIN")
        return

    uniq_desc = sorted(uniq, reverse=True)
    removed: list[dict] = []
    for n in uniq_desc:
        idx = n - 1
        removed.append({"idx": idx, "name": p["names"][idx]})
        del p["names"][idx]
    removed.reverse()
    moved_names = [r["name"] for r in removed]
    removed_idx_set = {r["idx"] for r in removed}
    removed_idx_asc = sorted(removed_idx_set)
    idx_to_new_pax = {r["idx"]: i + 1 for i, r in enumerate(removed)}

    moved_infants = [inf for inf in p["infants"] if inf["adult"] in moved_names]
    p["infants"] = [inf for inf in p["infants"] if inf["adult"] not in moved_names]

    moved_docs = []
    remaining_docs = []
    for d in p["docs"]:
        original_idx = d["pax"] - 1
        if original_idx in removed_idx_set:
            moved_docs.append({**d, "pax": idx_to_new_pax[original_idx]})
        else:
            shift = sum(1 for ri in removed_idx_asc if ri < original_idx)
            remaining_docs.append({**d, "pax": original_idx - shift + 1})
    p["docs"] = remaining_docs

    # Same pax-attribution/reindex pattern as docs above. A seat with no pax on file
    # (assigned before this feature existed, or left unattributed on a multi-pax PNR) has
    # no way to know which side of the divide it belongs to, so it's dropped from both -
    # same fate as before pax attribution existed at all.
    moved_seats = []
    remaining_seats = []
    for st in p["seats"]:
        pax_num = st.get("pax")
        if not pax_num:
            continue
        original_idx = pax_num - 1
        if original_idx in removed_idx_set:
            moved_seats.append({**st, "pax": idx_to_new_pax[original_idx]})
        else:
            shift = sum(1 for ri in removed_idx_asc if ri < original_idx)
            remaining_seats.append({**st, "pax": original_idx - shift + 1})
    p["seats"] = remaining_seats

    new_pnr = fresh_pnr()
    new_pnr["names"] = moved_names
    new_pnr["infants"] = moved_infants
    new_pnr["docs"] = moved_docs
    new_pnr["seats"] = moved_seats
    new_pnr["segments"] = copy.deepcopy(p["segments"])
    # Each segment's `seats` count is what price_itinerary multiplies the per-seat fare by
    # (see there) - left at the pre-divide party size on both sides, a WP after dividing
    # would silently price every resulting PNR for the *original* combined party instead of
    # its own, now-smaller one. Scale both copies to their own side's headcount (infants
    # don't count against seats here, matching how they never did at sell time either).
    for seg in new_pnr["segments"]:
        seg["seats"] = len(moved_names)
    for seg in p["segments"]:
        seg["seats"] = len(p["names"])
    new_pnr["phones"] = copy.deepcopy(p["phones"])
    new_pnr["received_from"] = p["received_from"]
    new_pnr["remarks"] = copy.deepcopy(p["remarks"])
    new_pnr["osis"] = copy.deepcopy(p["osis"])
    new_pnr["ssrs"] = copy.deepcopy(p["ssrs"])
    new_pnr["form_of_payment"] = copy.deepcopy(p["form_of_payment"]) if p["form_of_payment"] else None
    new_pnr["ticketing"] = p["ticketing"]
    new_pnr["locator"] = gen_locator()
    new_pnr["activity_log"] = [
        {"stamp": now_stamp(), "sine": STATE.sine or "----", "text": f"PNR CREATED - DIVIDED FROM RLOC {p['locator']}"}
    ]
    STATE.history[new_pnr["locator"]] = copy.deepcopy(new_pnr)

    invalidate_pricing()

    print_line("** PNR DIVIDED **", "hd")
    print_line(f"  NEW RLOC: {new_pnr['locator']} - {', '.join(moved_names)}")
    print_line("  ORIGINAL RLOC RETAINED - RE-SAVE WITH ER TO UPDATE", "dim")
    log_activity(STATE, f"PNR DIVIDED - {', '.join(moved_names)} TO NEW RLOC {new_pnr['locator']}")
    refresh_and_print_pnr()


# ---------- queues (QE/QN/QC) ----------

def queue_enqueue(num_str: str) -> None:
    p = STATE.pnr
    incomplete = _first_incomplete_message("queue_place")
    if incomplete:
        print_err(incomplete)
        return

    num = str(int(num_str))
    STATE.queues.setdefault(num, [])
    if p["locator"] not in STATE.queues[num]:
        STATE.queues[num].append(p["locator"])

    print_line(f"PNR {p['locator']} QUEUED TO QUEUE {num}")
    log_activity(STATE, f"QUEUED TO QUEUE {num}")

    STATE.pnr = fresh_pnr()
    STATE.last_display = []
    print_line("WORK AREA CLEARED - READY FOR NEXT ENTRY", "dim")


def queue_next(num_str: str) -> None:
    num = str(int(num_str))
    q = STATE.queues.get(num, [])
    if not q:
        print_line(f"END OF QUEUE {num} - NO PNRS REMAINING", "dim")
        return

    loc = q.pop(0)
    rec = STATE.history.get(loc)
    if not rec:
        print_err(f"QUEUE {num} REFERENCED UNKNOWN RECORD {loc}")
        return

    STATE.pnr = copy.deepcopy(rec)
    print_line(f"PNR {loc} RETRIEVED FROM QUEUE {num} - {len(q)} REMAINING")
    log_activity(STATE, f"RETRIEVED FROM QUEUE {num}")
    refresh_and_print_pnr()


def queue_count(num_str: str | None) -> None:
    if num_str:
        nums = [str(int(num_str))]
    else:
        nums = sorted((n for n in STATE.queues if STATE.queues[n]), key=int)

    if not nums:
        print_line("NO QUEUES WITH PNRS ON FILE", "dim")
        return

    print_line(f"QUEUE COUNT - PCC {STATE.pcc or '----'}", "hd")
    for n in nums:
        count = len(STATE.queues.get(n, []))
        label = f"  {QUEUE_CATEGORIES[n]}" if QUEUE_CATEGORIES.get(n) else ""
        print_line(f"  Q{pad(n, 4)}{pad(str(count), 4)}{label}")


# ---------- ticketing (TKTT) ----------

def gen_ticket_number(locator: str, identifier: str) -> str:
    seed = hash_str(f"{locator}{identifier}TKT")
    rng = mulberry32(seed)
    return str(int(rng() * 10000000000)).zfill(10)


def issue_tickets() -> None:
    p = STATE.pnr
    incomplete = _first_incomplete_message("issue_tickets")
    if incomplete:
        print_err(incomplete)
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
    # Reissuing fresh (rather than exchanging via WFR) means any pending exchange
    # opportunity is moot - don't leave it lingering.
    p["prior_tickets"] = []
    p["prior_pricing"] = None
    refresh_and_print_pnr()


def void_tickets() -> None:
    p = STATE.pnr
    incomplete = _first_incomplete_message("void_tickets")
    if incomplete:
        print_err(incomplete)
        return

    print_line("** TICKET(S) VOIDED **", "hd")
    for t in p["tickets"]:
        label = t["passenger"] + (" (INF)" if t["is_infant"] else "")
        print_line(f"  {pad(label, 28)} {t['ticket_num']}")
    count = len(p["tickets"])
    p["tickets"] = []
    log_activity(STATE, f"TICKET(S) VOIDED - {count} TICKET(S)")
    refresh_and_print_pnr()


def refund_tickets() -> None:
    p = STATE.pnr
    incomplete = _first_incomplete_message("refund_tickets")
    if incomplete:
        print_err(incomplete)
        return

    rules = FARE_RULES.get(p["segments"][0]["cls"])
    if rules and not rules["refundable"]:
        print_err("UNABLE TO REFUND - NONREFUNDABLE FARE BASIS")
        return

    amount = p["pricing"]["total"] if p["pricing"] else 0
    print_line("** TICKET(S) REFUNDED **", "hd")
    for t in p["tickets"]:
        label = t["passenger"] + (" (INF)" if t["is_infant"] else "")
        print_line(f"  {pad(label, 28)} {t['ticket_num']}")
    print_line(f"REFUND AMOUNT: USD {amount:.2f}", "dim")
    count = len(p["tickets"])
    p["tickets"] = []
    p["pricing"] = None
    log_activity(STATE, f"TICKET(S) REFUNDED - {count} TICKET(S), USD {amount:.2f}")
    refresh_and_print_pnr()


# Real Sabre's "WFR{TICKET#}" starts an exchange against an already-issued ticket, applies
# its value toward the newly re-priced itinerary, and either collects a difference (ADCOLL)
# or leaves a residual, before reissuing. Real Sabre's full process is a heavier multi-step
# workflow (WFR -> an auto-priced price-quote record -> a separate reissue commit entry);
# this is a deliberately simplified single-entry version that keeps the real training value
# (apply old value, show ADCOLL/residual, reissue) without simulating that machinery.
def exchange_ticket(ticket_num: str) -> None:
    p = STATE.pnr
    incomplete = _first_incomplete_message("exchange_ticket")
    if incomplete:
        print_err(incomplete)
        return

    old_ticket = next((t for t in p["prior_tickets"] if t["ticket_num"] == ticket_num), None)
    if not old_ticket:
        print_err("INVALID TICKET NUMBER - CHECK ENTRY AND REENTER")
        return

    diff = round((p["pricing"]["total"] - p["prior_pricing"]["total"]) * 100) / 100

    validating_carrier = p["segments"][0]["airline"]
    numeric_code = AIRLINE_NUMERIC_CODES.get(validating_carrier, "000")
    new_tickets = []
    for name in p["names"]:
        # Distinct seed input (the old ticket number) so the reissue gets a fresh number -
        # gen_ticket_number(locator, name) alone would regenerate the same one as before.
        serial = gen_ticket_number(p["locator"], f"{name}EXCH{old_ticket['ticket_num']}")
        new_tickets.append({"passenger": name, "ticket_num": f"{numeric_code}-{serial}", "is_infant": False})
    for inf in p["infants"]:
        identifier = f"{inf['surname']}/{inf['given']}"
        serial = gen_ticket_number(p["locator"], f"{identifier}EXCH{old_ticket['ticket_num']}")
        new_tickets.append({"passenger": identifier, "ticket_num": f"{numeric_code}-{serial}", "is_infant": True})
    p["tickets"] = new_tickets
    p["prior_tickets"] = []
    p["prior_pricing"] = None

    print_line("** EXCHANGE PROCESSED **", "hd")
    print_line(f"  ORIGINAL TICKET: {old_ticket['ticket_num']}   NEW FARE BASIS: {p['pricing']['fare_basis']}", "dim")
    if diff > 0:
        print_line(f"  ADDITIONAL COLLECTION (ADCOLL): USD {diff:.2f}")
    elif diff < 0:
        print_line(f"  RESIDUAL VALUE: USD {-diff:.2f} (NON-REFUNDABLE PER FARE RULES)", "dim")
    else:
        print_line("  EVEN EXCHANGE - NO ADDITIONAL COLLECTION")
    for t in p["tickets"]:
        label = t["passenger"] + (" (INF)" if t["is_infant"] else "")
        print_line(f"  {pad(label, 28)} {t['ticket_num']}")
    new_nums = ", ".join(t["ticket_num"] for t in p["tickets"])
    log_activity(
        STATE,
        f"TICKET EXCHANGED - {old_ticket['ticket_num']} -> {new_nums}, "
        f"{'ADCOLL' if diff >= 0 else 'RESIDUAL'} USD {abs(diff):.2f}",
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
    print_line("SCHEDULE", "hd")
    print_line("  S{DD}{MMM}{ORG}{DST}   Flight schedule, 7-day window from the given date -")
    print_line("                         times/equipment only, no booking classes or seats   e.g. S15AUGDFWORD")
    print_blank()
    print_line("FARES", "hd")
    print_line("  FQ{ORG}{DST}   Fare quote shop by city pair - indicative only, no PNR needed   e.g. FQDFWORD")
    print_blank()
    print_line("SELL", "hd")
    print_line("  0{LN}{CLASS}{SEATS}                        Sell from avail line   e.g. 04Y1")
    print_line("  0{SEATS}{CLASS}{LN}{CLASS}{LN}             Sell a connection (two avail lines)   e.g. 02Y1M2")
    print_line("  0{AL}{FLT}{CLASS}{DD}{MMM}{ORG}{DST}{STATUS}{SEATS}")
    print_line("                                              Direct/long sell   e.g. 0AA100Y15AUGDFWORDNN1")
    print_line("  A class at 0 remaining sells as a waitlist request (status HL) instead of", "dim")
    print_line("  being blocked - a real seat count still short-blocks as before.", "dim")
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
    print_line("  5{TEXT}                             General remark (agency-internal, not sent to the carrier)   e.g. 5VIP - HANDLE WITH CARE")
    print_line("  WP[/{CORPCODE}]                     Price itinerary (required before ticketing)   e.g. WP or WP/ACME01")
    print_line("  WPNCS[/{CORPCODE}]                  Price - lowest fare regardless of availability")
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
    print_line("  TKTV     Void issued ticket(s) - same-day reversal, no penalty. Fare quote")
    print_line("           and ticketing arrangement stay on file, so TKTT can reissue right away.")
    print_line("  TKTR     Refund issued ticket(s) - clears the fare quote too (re-price with WP")
    print_line("           before reissuing). Blocked for a nonrefundable fare basis.")
    print_line("  WFR{TICKET#}   Exchange a previously issued ticket after a fare/itinerary")
    print_line("                 change - applies the old ticket's value toward the freshly")
    print_line("                 re-priced total (WP first), shows ADCOLL/residual, reissues.")
    print_blank()
    print_line("SPECIAL SERVICE / OTHER SERVICE INFO", "hd")
    print_line("  3{SSRCODE}[-{PAX#}][/{TEXT}]   Special service request   e.g. 3VGML  or  3WCHR-1/AISLE SEAT")
    print_line("  3OSI{AL}{TEXT}                 Other service info   e.g. 3OSIAA VIP PASSENGER")
    print_line("  3FQTV{AL}{NUMBER}[/{TIER}]     Frequent flyer number, optional tier   e.g. 3FQTVAA1234567 or 3FQTVAA1234567/GLD")
    print_line("                                  Tiers: SLV GLD PLT DIA", "dim")
    print_line(
        "  SSR codes: WCHR WCHS WCHC VGML BBML CHML KSML MOML DBML BLND DEAF UMNR PETC BSCT SPML XBAG",
        "dim",
    )
    print_blank()
    print_line("PASSENGER DOCUMENTS (APIS)", "hd")
    print_line("  3DOCS{TYPE}/{COUNTRY}/{NUMBER}/{NATIONALITY}/{DOB}/{SEX}/{EXPIRY}-{PAX#}[.{INFANT#}]")
    print_line("    e.g. 3DOCSP/US/123456789/US/12JAN90/M/25DEC30-1", "dim")
    print_line("    infant e.g. 3DOCSP/US/123456789/US/12JAN26/M/25DEC30-1.1  (1st infant travelling with PAX 1)", "dim")
    print_line("    TYPE: P (passport). DOB/EXPIRY: DDMONYY. SEX: M or F.", "dim")
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
    print_line("  SP{N}  or  SP{N},{M}   Divide passenger(s) into a new PNR   e.g. SP2 or SP2,3")
    print_line("                         Itinerary/contact/ticketing fields are copied to the new")
    print_line("                         PNR; both PNRs then need a fresh fare quote (WP).")
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
