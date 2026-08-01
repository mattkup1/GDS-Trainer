"""Command dispatcher, generic over spec/command-grammar.json - shared with the browser
edition (see spec/README.md). The signed-in/signed-out gate is structural (different
handling entirely, not a repeating pattern) and stays hardcoded here; everything after it
is spec-driven so the two editions can't silently drift out of sync on syntax or ordering.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from . import commands as c
from .printer import print_err
from .state import STATE

_SPEC_DIR = Path(__file__).resolve().parents[2] / "spec"
COMMAND_GRAMMAR = json.loads((_SPEC_DIR / "command-grammar.json").read_text(encoding="utf-8"))
_COMPILED_GRAMMAR = [(entry["handler"], re.compile(entry["pattern"])) for entry in COMMAND_GRAMMAR]

# handler token (from COMMAND_GRAMMAR) -> local callable. Every handler is called as
# handler(rawMatchedString, *captureGroups) so the dispatch loop below stays fully generic.
HANDLERS = {
    "SIGN_OUT": lambda raw, *g: c.sign_out(),
    "HELP": lambda raw, *g: c.show_help(),
    "AVAILABILITY": lambda raw, day, mon, orig, dest: c.gen_availability(day, mon, orig, dest),
    "SELL_FROM_AVAIL": lambda raw, line, cls, seats: c.sell_from_avail(int(line), cls, int(seats)),
    "LONG_SELL": lambda raw, al, flt, cls, day, mon, orig, dest, status, seats: c.direct_sell(
        al, flt, cls, day, mon, orig, dest, status, int(seats)
    ),
    "NAME_FIELD": lambda raw, *g: c.handle_name(raw),
    "PHONE": lambda raw, *g: c.handle_phone(raw),
    "RECEIVED_FROM": lambda raw, *g: c.handle_received_from(raw),
    "GENERAL_REMARK": lambda raw, *g: c.handle_general_remark(raw),
    "PRICE_ITINERARY": lambda raw, mode, corp_code: c.price_itinerary(mode, corp_code),
    "TICKETING_AT_WILL": lambda raw, *g: c.add_ticketing_at_will(),
    "TICKETING_AT_WILL_DATED": lambda raw, day, mon, time: c.add_ticketing_at_will_dated(day, mon, time),
    "TICKETING_TIME_LIMIT": lambda raw, day, mon, time: c.add_ticketing_time_limit(day, mon, time),
    "FOP_CASH": lambda raw, *g: c.add_fop_cash(),
    "FOP_CHECK": lambda raw, *g: c.add_fop_check(),
    "FOP_CREDIT_CARD": lambda raw, card_type, num, mm, yy: c.add_fop_credit_card(card_type, num, mm, yy),
    "ISSUE_TICKETS": lambda raw, *g: c.issue_tickets(),
    "DOCS": lambda raw, doc_type, country, number, nationality, dob, sex, expiry, pax, infant: c.add_docs(
        doc_type, country, number, nationality, dob, sex, expiry, pax, infant
    ),
    "SSR_FQTV": lambda raw, airline, num, tier: c.add_fqtv(airline, num, tier),
    "OSI": lambda raw, airline, text: c.add_osi(airline, text),
    "SSR": lambda raw, code, pax, free_text: c.add_ssr(code, pax, free_text),
    "SEAT_MAP": lambda raw, n: c.show_seat_map(int(n)),
    "SEAT_ASSIGN": lambda raw, n, seat: c.assign_seat(int(n), seat),
    "DECODE_AIRPORT": lambda raw, code: c.decode_airport(code),
    "SEARCH_AIRPORTS": lambda raw, term: c.search_airports(term),
    "PNR_REDISPLAY": lambda raw, *g: c.refresh_and_print_pnr(),
    "PNR_HISTORY": lambda raw, *g: c.show_history(),
    "PNR_RETRIEVE": lambda raw, loc: c.retrieve_by_locator(loc),
    "QUEUE_ENQUEUE": lambda raw, n: c.queue_enqueue(n),
    "QUEUE_NEXT": lambda raw, n: c.queue_next(n),
    "QUEUE_COUNT": lambda raw, n: c.queue_count(n),
    "CANCEL_ITINERARY": lambda raw, *g: c.cancel_itinerary(),
    "CANCEL_ELEMENTS": lambda raw, range_str: c.handle_cancel(range_str),
    "IGNORE": lambda raw, *g: c.ignore_pnr(),
    "END_TRANSACT_ER": lambda raw, *g: c.end_transaction("ER"),
    "END_TRANSACT_ET": lambda raw, *g: c.end_transaction("ET"),
}


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

    for handler_token, pattern in _COMPILED_GRAMMAR:
        m = pattern.match(u)
        if m:
            HANDLERS[handler_token](u, *m.groups())
            return

    print_err("FORMAT - INVALID ENTRY, CHECK ENTRY AND REENTER (TYPE HELP)")
