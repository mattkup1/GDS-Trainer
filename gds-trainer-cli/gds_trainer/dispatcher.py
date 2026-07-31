"""Command dispatcher, ported from script.js's processCommand().

Branch order is preserved exactly from the JS version — several patterns are
single-character-prefixed and could otherwise collide (3OSI/3FQTV must be
checked before the general 3{CODE} SSR pattern, etc).
"""

from __future__ import annotations

import re

from . import commands as c
from .data import CARD_TYPES, MONTHS, PHONE_LOC_CODES, SSR_CODES
from .dates import parse_date
from .printer import print_err, print_line
from .state import STATE, fresh_pnr

_INF_RE = re.compile(r"\(INF([A-Z][A-Z\-' ]*)/([A-Z][A-Z\-' ]*)/(\d{1,2}[A-Z]{3}\d{2})\)\s*$")
_HEAD_RE = re.compile(r"^(\d{1,2})?([A-Z][A-Z\-' ]*)$")
_DOB_RE = re.compile(r"^(\d{1,2})([A-Z]{3})(\d{2})$")
_PHONE_RE = re.compile(r"^(?:/([A-Z]{3}))?(\d[\d\-]{4,14})-([A-Z]{1,3})$")


def _handle_name(u: str) -> None:
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
    incoming = parts[1:]
    segments = STATE.pnr["segments"]
    max_party = min(s["seats"] for s in segments) if segments else None
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
    c.log_activity(STATE, f"NAME{suffix} ADDED - {'  '.join(added)}")
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
            c.log_activity(
                STATE,
                f"INFANT ADDED - {infant_data['surname']}/{infant_data['given']}  DOB {infant_data['dob']}",
            )
    c.refresh_and_print_pnr()


def _handle_phone(u: str) -> None:
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
    c.log_activity(STATE, f"PHONE ADDED - 9{formatted}")
    c.refresh_and_print_pnr()


def _handle_cancel(nums_part: str) -> None:
    nums: list[int] = []
    valid = True
    for part in nums_part.split(","):
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
    c.cancel_elements(nums)


def process_command(raw: str) -> None:
    cmd = raw.strip()
    if not cmd:
        return
    u = cmd.upper()

    if not STATE.signed_in:
        if u.startswith("SI"):
            c.sign_in(u[2:])
            return
        if u.startswith("HELP"):
            c.show_help()
            return
        print_err("NOT SIGNED IN - ENTER: SI")
        return

    if u == "SO":
        c.sign_out()
        return
    if u.startswith("HELP"):
        c.show_help()
        return

    if m := re.match(r"^A(\d{1,2})([A-Z]{3})([A-Z]{3})([A-Z]{3})$", u):
        c.gen_availability(m[1], m[2], m[3], m[4])
        return
    if m := re.match(r"^1(\d{1,2})([A-Z]{3})([A-Z]{3})([A-Z]{3})$", u):
        c.gen_availability(m[1], m[2], m[3], m[4])
        return
    if m := re.match(r"^0(\d{1,2})([A-Z])(\d{1,2})$", u):
        c.sell_from_avail(int(m[1]), m[2], int(m[3]))
        return
    if m := re.match(
        r"^0([A-Z]{2})(\d{1,4})([A-Z])(\d{1,2})([A-Z]{3})([A-Z]{3})([A-Z]{3})([A-Z]{2})(\d{1,2})$", u
    ):
        c.direct_sell(m[1], m[2], m[3], m[4], m[5], m[6], m[7], m[8], int(m[9]))
        return
    if u.startswith("-"):
        _handle_name(u)
        return
    if u.startswith("9"):
        _handle_phone(u)
        return
    if u.startswith("6") and u != "6":
        text = u[1:].strip()
        if not text:
            print_err("FORMAT - RECEIVED FROM TEXT REQUIRED")
            return
        STATE.pnr["received_from"] = text
        print_line(f"RECEIVED FROM ADDED - {text}")
        c.log_activity(STATE, f"RECEIVED FROM ADDED - {text}")
        c.refresh_and_print_pnr()
        return
    if u in ("WP", "WPNCS"):
        c.price_itinerary(u)
        return
    if u in ("7TAW/", "7TAW"):
        STATE.pnr["ticketing"] = "7TAW/ (TICKETING AT WILL - TICKET ON OR BEFORE DEPARTURE)"
        print_line("TICKETING ARRANGEMENT ADDED - 7TAW/")
        c.log_activity(STATE, "TICKETING ARRANGEMENT ADDED - 7TAW/")
        c.refresh_and_print_pnr()
        return
    if m := re.match(r"^7TAW(\d{1,2})([A-Z]{3})/(\d{3,4})?$", u):
        dinfo = parse_date(m[1], m[2])
        if dinfo is None:
            print_err("INVALID DATE - CHECK ENTRY AND REENTER")
            return
        time_suffix = f"/{m[3]}" if m[3] else "/"
        queued = f" {m[3]}" if m[3] else ""
        STATE.pnr["ticketing"] = (
            f"7TAW{dinfo.day}{dinfo.mon}{time_suffix} "
            f"(TICKETING AT WILL - QUEUED {dinfo.day}{dinfo.mon}{queued})"
        )
        print_line(f"TICKETING ARRANGEMENT ADDED - 7TAW{dinfo.day}{dinfo.mon}{time_suffix}")
        c.log_activity(STATE, f"TICKETING ARRANGEMENT ADDED - 7TAW{dinfo.day}{dinfo.mon}{time_suffix}")
        c.refresh_and_print_pnr()
        return
    if m := re.match(r"^7TAX(\d{1,2})([A-Z]{3})/(\d{3,4})$", u):
        dinfo = parse_date(m[1], m[2])
        if dinfo is None:
            print_err("INVALID DATE - CHECK ENTRY AND REENTER")
            return
        STATE.pnr["ticketing"] = (
            f"7TAX{dinfo.day}{dinfo.mon}/{m[3]} (TIME LIMIT - TICKET BY {dinfo.day}{dinfo.mon} {m[3]})"
        )
        print_line(f"TICKETING ARRANGEMENT ADDED - 7TAX{dinfo.day}{dinfo.mon}/{m[3]}")
        c.log_activity(STATE, f"TICKETING ARRANGEMENT ADDED - 7TAX{dinfo.day}{dinfo.mon}/{m[3]}")
        c.refresh_and_print_pnr()
        return
    if u == "FPCASH":
        STATE.pnr["form_of_payment"] = {"type": "CASH", "display": "CASH"}
        print_line("FORM OF PAYMENT ADDED - CASH")
        c.log_activity(STATE, "FORM OF PAYMENT ADDED - CASH")
        c.refresh_and_print_pnr()
        return
    if u == "FPCHECK":
        STATE.pnr["form_of_payment"] = {"type": "CHECK", "display": "CHECK"}
        print_line("FORM OF PAYMENT ADDED - CHECK")
        c.log_activity(STATE, "FORM OF PAYMENT ADDED - CHECK")
        c.refresh_and_print_pnr()
        return
    if m := re.match(r"^FPCC([A-Z]{2})(\d{13,19})/(\d{2})(\d{2})$", u):
        card_type, num, mm_str, yy = m[1], m[2], m[3], m[4]
        if card_type not in CARD_TYPES:
            print_err(f"UNKNOWN CARD TYPE {card_type} - VALID: {' '.join(CARD_TYPES.keys())}")
            return
        mm = int(mm_str)
        if mm < 1 or mm > 12:
            print_err("INVALID EXPIRY MONTH - USE MMYY")
            return
        display = f"CC {card_type} {c.mask_card(num)}  EXP {mm_str}/{yy}  ({CARD_TYPES[card_type]})"
        STATE.pnr["form_of_payment"] = {"type": "CC", "display": display}
        print_line(f"FORM OF PAYMENT ADDED - {display}")
        c.log_activity(STATE, f"FORM OF PAYMENT ADDED - {display}")
        c.refresh_and_print_pnr()
        return
    if u == "TKTT":
        c.issue_tickets()
        return
    if m := re.match(r"^3FQTV([A-Z]{2})(\d{5,12})$", u):
        airline, num = m[1], m[2]
        text = f"FQTV {airline} FREQUENT FLYER NUMBER  {airline}{num}"
        STATE.pnr["ssrs"].append({"code": "FQTV", "text": text})
        print_line(f"SSR ADDED - {text}")
        c.log_activity(STATE, f"SSR ADDED - {text}")
        c.refresh_and_print_pnr()
        return
    if m := re.match(r"^3OSI([A-Z]{2})\s*(.+)$", u):
        text = m[2].strip()
        if not text:
            print_err("FORMAT - OSI REQUIRES FREE TEXT, e.g. 3OSIAA VIP PASSENGER")
            return
        full_text = f"{m[1]} {text}"
        STATE.pnr["osis"].append({"airline": m[1], "text": full_text})
        print_line(f"OSI ADDED - {full_text}")
        c.log_activity(STATE, f"OSI ADDED - {full_text}")
        c.refresh_and_print_pnr()
        return
    if m := re.match(r"^3([A-Z]{4})(?:-(\d{1,2}))?(?:/(.+))?$", u):
        code = m[1]
        desc = SSR_CODES.get(code)
        if not desc:
            print_err(f"UNKNOWN SSR CODE {code} - TYPE HELP FOR LIST")
            return
        pax_num = int(m[2]) if m[2] else None
        if pax_num and (pax_num < 1 or pax_num > len(STATE.pnr["names"])):
            print_err("INVALID PASSENGER NUMBER - CHECK NAME FIELD")
            return
        free_text = m[3].strip() if m[3] else ""
        text = f"{code} {desc}"
        if pax_num:
            text += f"  PAX {pax_num} ({STATE.pnr['names'][pax_num - 1]})"
        if free_text:
            text += f"  /{free_text}"
        STATE.pnr["ssrs"].append({"code": code, "text": text})
        print_line(f"SSR ADDED - {text}")
        c.log_activity(STATE, f"SSR ADDED - {text}")
        c.refresh_and_print_pnr()
        return
    if m := re.match(r"^4(\d{1,2})$", u):
        c.show_seat_map(int(m[1]))
        return
    if m := re.match(r"^4(\d{1,2})-(\d{1,2}[A-F])$", u):
        c.assign_seat(int(m[1]), m[2])
        return
    if m := re.match(r"^DC([A-Z]{3})$", u):
        c.decode_airport(m[1])
        return
    if m := re.match(r"^DAN(.+)$", u):
        c.search_airports(m[1].strip())
        return
    if u in ("*R", "*"):
        c.refresh_and_print_pnr()
        return
    if u == "*H":
        c.show_history()
        return
    if m := re.match(r"^\*([A-Z0-9]{6})$", u):
        c.retrieve_by_locator(m[1])
        return
    if u == "XI":
        c.cancel_itinerary()
        return
    if m := re.match(r"^X([\d,\-]+)$", u):
        _handle_cancel(m[1])
        return
    if u == "IG":
        STATE.pnr = fresh_pnr()
        STATE.last_display = []
        print_line("IGNORED - PNR NOT SAVED")
        return
    if u == "ER":
        c.end_transaction("ER")
        return
    if u == "ET":
        c.end_transaction("ET")
        return

    print_err("FORMAT - INVALID ENTRY, CHECK ENTRY AND REENTER (TYPE HELP)")
