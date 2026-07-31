"""Shared cross-edition test scenarios - the same command sequences and structural
expectations run against both the CLI (test_cli_scenarios.py) and the browser
(test_web_scenarios.py), so a behavior change in one edition that isn't mirrored
in the other shows up as a failure, instead of silently drifting (see
spec/README.md - this is the same "one definition, two consumers" idea applied
to tests instead of business rules).

Assertions are deliberately structural (message substrings, not exact values):
fares, seat occupancy, ticket serials, and record locators are independently
random per edition by design (see CLAUDE.md's Shared rules core section) -
matching exact values across editions was never a goal, only that the same
*rules* produce the same *kind* of outcome in both.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Step:
    command: str
    expect_contains: list[str] = field(default_factory=list)
    expect_not_contains: list[str] = field(default_factory=list)


@dataclass
class Scenario:
    name: str
    steps: list[Step]


# ---------- reusable step fragments ----------

SIGN_IN = Step("SI", expect_contains=["SIGN IN COMPLETE"])
AVAIL_DFW_ORD = Step("A15AUGDFWORD", expect_contains=["AIR AVAILABILITY", "DFW-ORD"])
SELL_1_SEAT = Step("01Y1", expect_contains=["SEGMENT SOLD"])
SELL_2_SEATS = Step("01Y2", expect_contains=["SEGMENT SOLD"])
NAME_SMITH = Step("-SMITH/JOHN MR", expect_contains=["NAME ADDED", "SMITH/JOHN MR"])
PHONE_VALID = Step("9214555-1234-A", expect_contains=["PHONE ADDED"])
RECEIVED_FROM = Step("6JSMITH", expect_contains=["RECEIVED FROM ADDED"])
PRICE = Step("WP", expect_contains=["ITINERARY PRICING", "FARE BASIS"])
TICKETING_AT_WILL = Step("7TAW/", expect_contains=["TICKETING ARRANGEMENT ADDED"])
FOP_CASH = Step("FPCASH", expect_contains=["FORM OF PAYMENT ADDED", "CASH"])


def _priced_single_pax_setup() -> list[Step]:
    """SI -> avail -> sell 1 seat -> name -> phone -> RF -> price. Common prefix
    for scenarios that need a priced, nameable PNR to test against."""
    return [SIGN_IN, AVAIL_DFW_ORD, SELL_1_SEAT, NAME_SMITH, PHONE_VALID, RECEIVED_FROM, PRICE]


# ---------- scenarios ----------

SCENARIOS: list[Scenario] = [
    Scenario(
        "sign_in_gate",
        [
            Step("A15AUGDFWORD", expect_contains=["NOT SIGNED IN"]),
            SIGN_IN,
            AVAIL_DFW_ORD,
        ],
    ),
    Scenario(
        "full_booking_flow_single_pax_through_ticketing",
        [
            *_priced_single_pax_setup(),
            TICKETING_AT_WILL,
            FOP_CASH,
            Step("ER", expect_contains=["END OF TRANSACTION COMPLETE", "RLOC"]),
            Step("TKTT", expect_contains=["ELECTRONIC TICKET ISSUED", "SMITH/JOHN MR"]),
        ],
    ),
    Scenario(
        "party_size_rejects_over_limit",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            SELL_1_SEAT,  # 1 seat sold
            NAME_SMITH,  # 1st name - fits
            Step(
                "-JONES/BOB MR",
                expect_contains=["PARTY SIZE EXCEEDS SEATS SOLD"],
                expect_not_contains=["NAME ADDED - JONES"],
            ),
        ],
    ),
    Scenario(
        "lap_infant_does_not_count_toward_party_size",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            SELL_1_SEAT,  # 1 seat sold - only room for 1 adult name
            Step(
                "-SMITH/JOHN MR(INFSMITH/BABY/12JAN26)",
                expect_contains=["NAME ADDED", "INFANT ADDED"],
            ),
        ],
    ),
    Scenario(
        "ssr_unknown_code_rejected_known_code_accepted",
        [
            *_priced_single_pax_setup(),
            Step("3ZZZZ", expect_contains=["UNKNOWN SSR CODE"]),
            Step("3VGML", expect_contains=["SSR ADDED", "VEGETARIAN"]),
        ],
    ),
    Scenario(
        "phone_format_rejected_then_accepted",
        [
            SIGN_IN,
            Step("9BADFORMAT", expect_contains=["FORMAT", "PHONE"], expect_not_contains=["PHONE ADDED"]),
            PHONE_VALID,
        ],
    ),
    Scenario(
        "seat_reassignment_of_same_seat_always_rejected",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            SELL_1_SEAT,
            Step("41-1A"),  # outcome depends on random occupancy - not asserted here
            Step("41-1A", expect_not_contains=["SEAT ASSIGNED - SEG1 1A"]),
        ],
    ),
    Scenario(
        "cancel_single_element",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            SELL_1_SEAT,
            NAME_SMITH,
            Step("X1", expect_contains=["ELEMENT 1 CANCELLED"]),
            Step("*R", expect_not_contains=["NM1"]),
        ],
    ),
    Scenario(
        "cancel_range_and_list_forms",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            SELL_1_SEAT,
            NAME_SMITH,
            PHONE_VALID,
            RECEIVED_FROM,
            Step("X2-3", expect_contains=["ELEMENTS 2,3 CANCELLED"]),
        ],
    ),
    Scenario(
        "cancel_entire_itinerary",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            SELL_1_SEAT,
            Step("XI", expect_contains=["ITINERARY CANCELLED"]),
            Step("*R", expect_not_contains=["SEG1"]),
        ],
    ),
    Scenario(
        "er_keeps_pnr_et_clears_it",
        [
            *_priced_single_pax_setup(),
            TICKETING_AT_WILL,
            FOP_CASH,
            Step("ER", expect_contains=["END OF TRANSACTION COMPLETE"]),
            Step("*R", expect_contains=["NM1"]),  # ER: PNR still loaded
            Step("ET", expect_contains=["WORK AREA CLEARED"]),
            Step("*R", expect_contains=["PNR IS EMPTY"]),  # ET: work area cleared
        ],
    ),
    Scenario(
        "end_transaction_completeness_gate",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            SELL_1_SEAT,
            Step("ER", expect_contains=["PNR INCOMPLETE", "NAME FIELD"]),
            NAME_SMITH,
            Step("ER", expect_contains=["PNR INCOMPLETE", "FARE QUOTE"]),
        ],
    ),
    Scenario(
        "ticketing_completeness_gate_requires_saved_pnr",
        [
            *_priced_single_pax_setup(),
            TICKETING_AT_WILL,
            FOP_CASH,
            Step("TKTT", expect_contains=["UNABLE TO TICKET", "END TRANSACT"]),
        ],
    ),
    Scenario(
        "retrieve_by_locator_unknown_then_known",
        [
            SIGN_IN,
            Step("*ZZZZZZ", expect_contains=["RECORD LOCATOR NOT FOUND"]),
        ],
    ),
    Scenario(
        "invalid_entry_falls_through_to_format_error",
        [
            SIGN_IN,
            Step("THIS IS NOT A COMMAND", expect_contains=["FORMAT", "INVALID ENTRY"]),
        ],
    ),
    Scenario(
        "help_lists_all_major_sections",
        [
            SIGN_IN,
            Step(
                "HELP",
                expect_contains=[
                    "SIGN ON/OFF",
                    "AVAILABILITY",
                    "PNR BUILD",
                    "TICKETING",
                    "PNR MANAGEMENT",
                ],
            ),
        ],
    ),
    Scenario(
        "airport_encode_decode",
        [
            SIGN_IN,
            Step("DCORD", expect_contains=["ORD", "CHICAGO"]),
            Step("DCZZZ", expect_contains=["UNABLE TO DECODE"]),
            Step("DANCHICAGO", expect_contains=["CITY/AIRPORT NAME SEARCH", "CHICAGO"]),
        ],
    ),
    Scenario(
        "apis_document_accepted_and_malformed_dob_rejected",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            SELL_1_SEAT,
            NAME_SMITH,
            Step(
                "3DOCSP/US/123456789/US/12JAN90/M/25DEC30-1",
                expect_contains=["DOCUMENT ADDED", "PASSPORT"],
            ),
            Step(
                "3DOCSP/US/987654321/US/99XXX90/M/25DEC30-1",
                expect_contains=["INVALID DOB"],
                expect_not_contains=["DOCUMENT ADDED - PASSPORT US 987654321"],
            ),
        ],
    ),
    Scenario(
        "general_remark_added",
        [
            SIGN_IN,
            Step(
                "5VIP CLIENT - HANDLE WITH CARE",
                expect_contains=["GENERAL REMARK ADDED", "VIP CLIENT"],
            ),
        ],
    ),
    Scenario(
        "fqtv_tier_shown_unknown_tier_rejected",
        [
            SIGN_IN,
            Step("3FQTVAA1234567/GLD", expect_contains=["SSR ADDED", "TIER: GOLD"]),
            Step(
                "3FQTVAA7654321/ZZZ",
                expect_contains=["UNKNOWN LOYALTY TIER"],
                expect_not_contains=["SSR ADDED - FQTV AA FREQUENT FLYER NUMBER  AA7654321"],
            ),
        ],
    ),
    Scenario(
        "corporate_code_discount_applied",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            SELL_1_SEAT,
            NAME_SMITH,
            Step("WP/ACME01", expect_contains=["CORPORATE CODE APPLIED", "ACME CORP"]),
        ],
    ),
    Scenario(
        "corporate_code_unknown_rejected",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            SELL_1_SEAT,
            NAME_SMITH,
            Step(
                "WP/BADCODE",
                expect_contains=["UNKNOWN CORPORATE CODE"],
                expect_not_contains=["FARE QUOTE STORED"],
            ),
        ],
    ),
    Scenario(
        "fare_rules_shown_on_every_price",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            SELL_1_SEAT,
            NAME_SMITH,
            Step(
                "WP",
                expect_contains=["FARE RULES", "CHANGE FEE", "REFUNDABLE", "ADVANCE PURCHASE REQUIRED"],
            ),
        ],
    ),
    Scenario(
        "cancel_docs_and_remark_elements",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            SELL_1_SEAT,
            NAME_SMITH,
            Step("3DOCSP/US/123456789/US/12JAN90/M/25DEC30-1", expect_contains=["DOCUMENT ADDED"]),
            Step("5AGENCY NOTE", expect_contains=["GENERAL REMARK ADDED"]),
            Step("*R", expect_contains=["DOC", "RM"]),
            Step("X2", expect_contains=["ELEMENT 2 CANCELLED"]),
            Step("*R", expect_contains=["RM"], expect_not_contains=["DOC"]),
            Step("X3", expect_contains=["ELEMENT 3 CANCELLED"]),
            Step("*R", expect_not_contains=["RM"]),
        ],
    ),
    Scenario(
        "seat_pool_depletes_to_waitlist",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            # Class capacity is randomly 0-9 seats; 9 unconditional 1-seat sells guarantee
            # the pool is fully drained by the 10th attempt regardless of the starting count.
            Step("01Y1"), Step("01Y1"), Step("01Y1"), Step("01Y1"), Step("01Y1"),
            Step("01Y1"), Step("01Y1"), Step("01Y1"), Step("01Y1"),
            Step("01Y1", expect_contains=["WAITLISTED", "HL"]),
        ],
    ),
]
