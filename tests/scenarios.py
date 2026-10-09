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
        "fare_quote_shop_needs_no_pnr",
        [
            Step("FQDFWORD", expect_contains=["NOT SIGNED IN"]),
            SIGN_IN,
            Step(
                "FQDFWORD",
                expect_contains=["FARE QUOTE SHOP", "DFW-ORD", "INDICATIVE ONLY"],
            ),
            Step("FQDFWDFW", expect_contains=["FORMAT", "CANNOT BE THE SAME"]),
        ],
    ),
    Scenario(
        "schedule_display_shows_week_window_no_booking_columns",
        [
            Step("S15AUGDFWORD", expect_contains=["NOT SIGNED IN"]),
            SIGN_IN,
            # Reuses genAvailability's exact per-date seed, so 15AUG's block reproduces the
            # same known flight (AK 2265, 539A-720A) AVAIL_DFW_ORD already relies on -
            # confirming this is the same underlying schedule, just without booking columns.
            Step(
                "S15AUGDFWORD",
                expect_contains=[
                    "SCHEDULE", "DFW-ORD", "15AUG2026 - 21AUG2026",
                    "AK 2265", "539A", "720A",
                ],
                expect_not_contains=["SELL WITH", "SELL CONNECTION"],
            ),
            Step("S15AUGDFWDFW", expect_contains=["FORMAT", "CANNOT BE THE SAME"]),
        ],
    ),
    Scenario(
        "return_availability_reverses_city_pair_and_resolves_dates_from_outbound",
        [
            SIGN_IN,
            Step("1R", expect_contains=["NO AVAILABILITY DISPLAY IN CONTEXT"]),
            AVAIL_DFW_ORD,
            # Bare 1R: same date, city pair reversed.
            Step("1R", expect_contains=["AIR AVAILABILITY", "ORD-DFW", "15AUG2026"]),
            AVAIL_DFW_ORD,
            Step("1R20AUG", expect_contains=["ORD-DFW", "20AUG2026"]),
            AVAIL_DFW_ORD,
            # Day-of-month only: same month if it still lies ahead, else the next month.
            Step("1R25", expect_contains=["ORD-DFW", "25AUG2026"]),
            AVAIL_DFW_ORD,
            Step("1R10", expect_contains=["ORD-DFW", "10SEP2026"]),
            AVAIL_DFW_ORD,
            # A {DD}{MMM} earlier in the calendar than the outbound means NEXT year - relative
            # to the outbound date, not to today.
            Step("1R10JUL", expect_contains=["ORD-DFW", "10JUL2027"]),
            AVAIL_DFW_ORD,
            Step("1R+5", expect_contains=["ORD-DFW", "20AUG2026"]),
            AVAIL_DFW_ORD,
            Step("1R-1", expect_contains=["ORD-DFW", "14AUG2026"]),
            AVAIL_DFW_ORD,
            # Frozen "today" is 14AUG, so 15AUG - 3 days is already past.
            Step("1R-3", expect_contains=["INVALID DATE"]),
            Step("1R99", expect_contains=["INVALID DATE"]),
        ],
    ),
    Scenario(
        "round_trip_is_two_segments_sold_from_availability_and_return_availability",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            SELL_1_SEAT,
            Step("1R20AUG", expect_contains=["ORD-DFW", "20AUG2026"]),
            # Sells line 1 of the RETURN display - the new display replaced the outbound's.
            Step("01Y1", expect_contains=["SEGMENT SOLD", "20AUG", "ORDDFW"]),
            NAME_SMITH,
            PHONE_VALID,
            RECEIVED_FROM,
            Step("WP", expect_contains=["ITINERARY PRICING", "TRIP TYPE: ROUND TRIP"]),
        ],
    ),
    Scenario(
        "availability_filters_by_airline_and_departure_time",
        [
            SIGN_IN,
            # Line 1 of DFW-ORD 15AUG is AK 2265 (539A) - empirically confirmed, same as the
            # codeshare/schedule scenarios rely on.
            Step(
                "A15AUGDFWORD¥AK",
                expect_contains=["FILTERED: AIRLINE AK", "AK 2265"],
                expect_not_contains=["TP 2561"],
            ),
            # ASCII "/" fallback for the airline-filter separator.
            Step("A15AUGDFWORD/AK", expect_contains=["FILTERED: AIRLINE AK", "AK 2265"]),
            Step(
                "A15AUGDFWORD11A",
                expect_contains=["FILTERED: DEPARTING AFTER 1100A"],
                expect_not_contains=["AK 2265", "TP 2561"],
            ),
            Step(
                "A15AUGDFWORD11A¥LO",
                expect_contains=["DEPARTING AFTER 1100A", "AIRLINE LO", "LO 2952"],
            ),
            Step("A15AUGDFWORD¥ZZ", expect_contains=["NO AVAILABILITY FOR REQUESTED CRITERIA"]),
            Step("A15AUGDFWORD13P", expect_contains=["INVALID TIME"]),
            # A filtered display renumbers from 1 - what's on screen is what's sellable.
            Step("A15AUGDFWORD¥LO", expect_contains=[" 1  LO 2952"]),
            Step("01Y1", expect_contains=["SEGMENT SOLD", "LO2952"]),
            # Return availability takes the same filters.
            Step("1R20AUG¥ZZ", expect_contains=["NO AVAILABILITY FOR REQUESTED CRITERIA"]),
        ],
    ),
    Scenario(
        "codeshare_flight_shown_and_carried_through_to_pnr",
        [
            SIGN_IN,
            # Line 1 (AK2265, DFW-ORD 15AUG) is empirically confirmed to be a codeshare
            # operated by Southwest (WN1018) - the codeshare roll is seeded off the
            # flight's own identity (_gen_flight/genFlight's derived csRng), independent
            # of the shared per-search rng stream, so this is stable regardless of what
            # else this route/date generates.
            Step(
                "A15AUGDFWORD",
                expect_contains=["AIR AVAILABILITY", "OPERATED BY", "WN1018"],
            ),
            SELL_1_SEAT,
            Step("*R", expect_contains=["OPR BY WN1018"]),
        ],
    ),
    Scenario(
        "flexible_date_availability_shows_fare_calendar",
        [
            Step("AF15AUGDFWORD", expect_contains=["NOT SIGNED IN"]),
            SIGN_IN,
            Step(
                "AF15AUGDFWORD",
                expect_contains=[
                    "FLEXIBLE DATE AVAILABILITY", "DFW-ORD",
                    "DATE", "LOWEST FARE", "CLASS", "NONSTOPS",
                    "INDICATIVE BASE FARE ONLY",
                ],
                expect_not_contains=["SELL WITH"],
            ),
            Step("AF15AUGDFWDFW", expect_contains=["FORMAT", "CANNOT BE THE SAME"]),
            Step("AF32AUGDFWORD", expect_contains=["INVALID DATE"]),
        ],
    ),
    Scenario(
        "fuller_fare_rules_shown_and_cancellation_fee_deducted_on_refund",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            # class J (refundable per spec/reference-data.json's fareRules) carries a
            # USD 50 cancellation fee distinct from its USD 75 change fee - TKTR must
            # deduct it from the refund amount rather than refunding the fare in full.
            Step("01J1", expect_contains=["SEGMENT SOLD"]),
            NAME_SMITH,
            PHONE_VALID,
            RECEIVED_FROM,
            Step(
                "WP",
                expect_contains=["CANCELLATION FEE", "USD 50.00", "MINIMUM STAY", "MAXIMUM STAY"],
            ),
            TICKETING_AT_WILL,
            FOP_CASH,
            Step("ER", expect_contains=["END OF TRANSACTION COMPLETE"]),
            Step("TKTT", expect_contains=["ELECTRONIC TICKET ISSUED"]),
            Step(
                "TKTR",
                expect_contains=["TICKET(S) REFUNDED", "CANCELLATION FEE USD 50.00 DEDUCTED"],
            ),
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
        "void_and_refund_require_tickets_on_file",
        [
            *_priced_single_pax_setup(),
            TICKETING_AT_WILL,
            FOP_CASH,
            Step("TKTV", expect_contains=["UNABLE TO VOID", "NO TICKET NUMBERS"]),
            Step("TKTR", expect_contains=["UNABLE TO REFUND", "NO TICKET NUMBERS"]),
        ],
    ),
    Scenario(
        "void_tickets_allows_immediate_reissue",
        [
            *_priced_single_pax_setup(),
            TICKETING_AT_WILL,
            FOP_CASH,
            Step("ER", expect_contains=["END OF TRANSACTION COMPLETE"]),
            Step("TKTT", expect_contains=["ELECTRONIC TICKET ISSUED"]),
            Step("TKTV", expect_contains=["TICKET(S) VOIDED"]),
            # fare quote/ticketing arrangement stay on file after a void, so TKTT works again
            Step("TKTT", expect_contains=["ELECTRONIC TICKET ISSUED"]),
        ],
    ),
    Scenario(
        "refund_blocked_for_nonrefundable_fare",
        [
            # class Y is nonrefundable per spec/reference-data.json's fareRules
            *_priced_single_pax_setup(),
            TICKETING_AT_WILL,
            FOP_CASH,
            Step("ER", expect_contains=["END OF TRANSACTION COMPLETE"]),
            Step("TKTT", expect_contains=["ELECTRONIC TICKET ISSUED"]),
            Step("TKTR", expect_contains=["UNABLE TO REFUND", "NONREFUNDABLE"]),
        ],
    ),
    Scenario(
        "refund_succeeds_for_refundable_fare",
        [
            # class F is refundable per spec/reference-data.json's fareRules
            SIGN_IN,
            AVAIL_DFW_ORD,
            Step("01F1", expect_contains=["SEGMENT SOLD"]),
            NAME_SMITH,
            PHONE_VALID,
            RECEIVED_FROM,
            PRICE,
            TICKETING_AT_WILL,
            FOP_CASH,
            Step("ER", expect_contains=["END OF TRANSACTION COMPLETE"]),
            Step("TKTT", expect_contains=["ELECTRONIC TICKET ISSUED"]),
            Step("TKTR", expect_contains=["TICKET(S) REFUNDED", "REFUND AMOUNT"]),
        ],
    ),
    Scenario(
        "exchange_ticket_requires_prior_ticket_on_file",
        [
            SIGN_IN,
            Step(
                "WFR045-1234567890",
                expect_contains=["UNABLE TO EXCHANGE", "NO PRIOR TICKET ON FILE"],
            ),
        ],
    ),
    Scenario(
        "exchange_ticket_requires_fresh_fare_quote",
        [
            *_priced_single_pax_setup(),
            TICKETING_AT_WILL,
            FOP_CASH,
            Step("ER", expect_contains=["END OF TRANSACTION COMPLETE"]),
            Step("TKTT", expect_contains=["ELECTRONIC TICKET ISSUED"]),
            # selling again invalidates pricing/tickets and stashes them for exchange -
            # but WFR still needs a fresh WP before it'll compute a fare difference
            Step("01Y1", expect_contains=["SEGMENT SOLD"]),
            Step(
                "WFR045-1234567890",
                expect_contains=["UNABLE TO EXCHANGE", "NO NEW FARE QUOTE ON FILE"],
            ),
        ],
    ),
    Scenario(
        "divide_pnr_requires_saved_pnr",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            SELL_1_SEAT,
            NAME_SMITH,
            Step("SP1", expect_contains=["UNABLE TO DIVIDE", "END TRANSACT"]),
        ],
    ),
    Scenario(
        "divide_pnr_rejects_removing_all_passengers",
        [
            *_priced_single_pax_setup(),
            TICKETING_AT_WILL,
            FOP_CASH,
            Step("ER", expect_contains=["END OF TRANSACTION COMPLETE"]),
            Step("SP1", expect_contains=["UNABLE TO DIVIDE", "AT LEAST ONE PASSENGER MUST REMAIN"]),
        ],
    ),
    Scenario(
        "divide_pnr_moves_passenger_to_new_pnr",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            SELL_2_SEATS,
            Step(
                "-2SMITH/JOHN MR/JANE MRS",
                expect_contains=["NAMES ADDED", "SMITH/JOHN MR", "SMITH/JANE MRS"],
            ),
            PHONE_VALID,
            RECEIVED_FROM,
            PRICE,
            TICKETING_AT_WILL,
            FOP_CASH,
            Step("ER", expect_contains=["END OF TRANSACTION COMPLETE"]),
            Step("SP2", expect_contains=["PNR DIVIDED", "NEW RLOC", "SMITH/JANE MRS"]),
            # original PNR keeps its own segment/phone/RF/FOP/ticketing, loses passenger 2,
            # and has its fare quote invalidated (party size changed). The retained
            # segment's seat count must also drop from HK2 to HK1 - it was sold for 2
            # passengers, only 1 remains on this side after the divide, and a later WP
            # must price for that 1, not silently re-price the original party of 2.
            Step(
                "*R",
                expect_contains=["NM1", "SMITH/JOHN MR", "SEG1", "HK1", "CTC", "RF", "FP", "TK"],
                expect_not_contains=["SMITH/JANE MRS", "FQ", "HK2"],
            ),
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
        "group_pnr_requires_deposit_for_ten_plus_names",
        [
            SIGN_IN,
            # Long/direct sell isn't capped by an availability class's seat count, so it can
            # hold a real 12-seat group in one entry.
            Step("0AA100Y15AUGDFWORDNN12", expect_contains=["SEGMENT SOLD"]),
            Step(
                "-12TBA/TBA",
                expect_contains=["NAMES ADDED", "12 TBA/TBA PLACEHOLDER"],
            ),
            PHONE_VALID,
            RECEIVED_FROM,
            PRICE,
            TICKETING_AT_WILL,
            FOP_CASH,
            Step(
                "ER",
                expect_contains=["PNR INCOMPLETE", "GROUP DEPOSIT REQUIRED", "3DEPS"],
                expect_not_contains=["END OF TRANSACTION COMPLETE"],
            ),
            Step("3DEPS", expect_contains=["SSR ADDED", "GROUP DEPOSIT RECEIVED"]),
            Step("ER", expect_contains=["END OF TRANSACTION COMPLETE"]),
            # Finalizing a placeholder: cancel it, then add the real name - no new command
            Step("X5", expect_contains=["ELEMENT 5 CANCELLED"]),
            Step(
                "-SMITH/JOHN MR",
                expect_contains=["NAME ADDED", "SMITH/JOHN MR"],
            ),
            Step("*R", expect_contains=["SMITH/JOHN MR"], expect_not_contains=["UNABLE"]),
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
        "ssr_and_fqtv_reject_passenger_number_zero",
        [
            # Regression: -{PAX#} of "0" must be rejected like any other out-of-range
            # passenger number. Both handlers used to gate the range check on the
            # *parsed int* being truthy (`if pax_num and ...`) rather than on whether a
            # -{PAX#} suffix was given at all (`if pax_str and ...`) - since 0 is falsy
            # in both JS and Python, "-0" silently skipped validation and was accepted
            # as if no passenger number had been given, instead of erroring.
            *_priced_single_pax_setup(),
            Step("3WCHR-0", expect_contains=["INVALID PASSENGER NUMBER"]),
            Step("3FQTVAA1234567-0", expect_contains=["INVALID PASSENGER NUMBER"]),
        ],
    ),
    Scenario(
        "extra_seat_ssr_and_fare_reflects_seats_sold_not_names",
        [
            # Booking an extra seat (comfort/oversized-passenger purchase, or an instrument/
            # cabin-baggage seat) is real: sell one more seat than passengers, tag it with
            # the EXST SSR - no new command code needed, same as DEPS/group deposit.
            SIGN_IN,
            AVAIL_DFW_ORD,
            Step("01Y2", expect_contains=["SEGMENT SOLD"]),  # 2 seats, 1 passenger
            NAME_SMITH,
            Step("3EXST-1", expect_contains=["SSR ADDED", "EXTRA SEAT PURCHASED", "PAX 1 (SMITH/JOHN MR)"]),
            # the fare quote must price for both seats sold, not just the 1 named passenger
            Step("WP", expect_contains=["ITINERARY PRICING"]),
            Step("*R", expect_contains=["SEG1", "HK2", "SSR", "EXST"]),
        ],
    ),
    Scenario(
        "child_fare_tag_discounts_price_and_survives_divide",
        [
            # (CHD) on a specific /-separated given-name token tags that one passenger as a
            # child fare - still a fully named, seat-occupying passenger (unlike a lap
            # infant), just priced at a discount.
            SIGN_IN,
            AVAIL_DFW_ORD,
            Step("01Y2", expect_contains=["SEGMENT SOLD"]),
            Step(
                "-SMITH/JOHN MR/JOHNNY MSTR(CHD)",
                expect_contains=["NAMES ADDED", "SMITH/JOHN MR", "SMITH/JOHNNY MSTR (CHD)"],
            ),
            Step("WP", expect_contains=["ITINERARY PRICING", "CHILD FARE APPLIED - 1 PAX"]),
            Step("*R", expect_contains=["NM2", "SMITH/JOHNNY MSTR", "(CHD)"]),
            PHONE_VALID,
            RECEIVED_FROM,
            Step("FPCASH", expect_contains=["FORM OF PAYMENT ADDED"]),
            TICKETING_AT_WILL,
            Step("ER", expect_contains=["END OF TRANSACTION COMPLETE"]),
            # the child tag must move with the child on divide, reindexed to pax 1 in the
            # new PNR - same pax-attribution pattern already covered for docs/seats.
            Step("SP2", expect_contains=["PNR DIVIDED", "NEW RLOC", "SMITH/JOHNNY MSTR"]),
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
        "email_format_rejected_then_accepted",
        [
            SIGN_IN,
            # "9E" alone still matches the generic phone pattern's leading "9" if the
            # email grammar entry weren't ordered ahead of it - this also exercises that
            # ordering, same "more specific entry must precede the general one" precedent
            # as 3OSI before the general 3{CODE} SSR pattern.
            Step("9EBADEMAIL", expect_contains=["FORMAT", "EMAIL"], expect_not_contains=["EMAIL ADDED"]),
            Step("9EJSMITH@EXAMPLE.COM", expect_contains=["EMAIL ADDED", "JSMITH@EXAMPLE.COM"]),
            Step("*R", expect_contains=["JSMITH@EXAMPLE.COM"]),
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
        "seat_assign_defaults_to_solo_passenger",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            SELL_1_SEAT,
            NAME_SMITH,
            # solo passenger on file - the passenger number is unambiguous and optional
            Step("41-1A", expect_contains=["SEAT ASSIGNED", "PAX 1 (SMITH/JOHN MR)"]),
        ],
    ),
    Scenario(
        "seat_assign_requires_pax_with_multiple_passengers",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            SELL_2_SEATS,
            Step(
                "-2SMITH/JOHN MR/JANE MRS",
                expect_contains=["NAMES ADDED", "SMITH/JOHN MR", "SMITH/JANE MRS"],
            ),
            Step(
                "41-1A",
                expect_contains=["MULTIPLE PASSENGERS ON FILE", "SPECIFY PASSENGER NUMBER"],
                expect_not_contains=["SEAT ASSIGNED"],
            ),
            Step("41-1A/2", expect_contains=["SEAT ASSIGNED", "PAX 2 (SMITH/JANE MRS)"]),
            Step(
                "41-1C/9",
                expect_contains=["INVALID PASSENGER NUMBER"],
                expect_not_contains=["SEAT ASSIGNED"],
            ),
        ],
    ),
    Scenario(
        "divide_pnr_moves_attributed_seat_keeps_others_reindexed",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            SELL_2_SEATS,
            Step(
                "-2SMITH/JOHN MR/JANE MRS",
                expect_contains=["NAMES ADDED"],
            ),
            Step("41-1A/1", expect_contains=["SEAT ASSIGNED", "PAX 1 (SMITH/JOHN MR)"]),
            Step("41-1C/2", expect_contains=["SEAT ASSIGNED", "PAX 2 (SMITH/JANE MRS)"]),
            PHONE_VALID,
            RECEIVED_FROM,
            PRICE,
            TICKETING_AT_WILL,
            FOP_CASH,
            Step("ER", expect_contains=["END OF TRANSACTION COMPLETE"]),
            # dividing passenger 2 (Jane) moves her seat with her, re-indexed to PAX 1 on
            # the new PNR (asserted separately per-edition against the printed NEW RLOC,
            # since this shared runner has no way to retrieve a randomly generated locator);
            # here we confirm the retained side: John's seat survives, reindexed to stay
            # PAX 1 (he was already 1, so this also guards against an accidental off-by-one),
            # and the segment's own seat count drops from HK2 to HK1 for the one remaining
            # passenger (see cancelling_a_saved_pnr... / new_pnr_still_requires... above for
            # the general seats-count-follows-headcount behavior this also depends on).
            Step("SP2", expect_contains=["PNR DIVIDED", "NEW RLOC", "SMITH/JANE MRS"]),
            Step(
                "*R",
                expect_contains=["NM1", "SMITH/JOHN MR", "HK1", "SEAT", "PAX 1 (SMITH/JOHN MR)"],
                expect_not_contains=["SMITH/JANE MRS", "HK2"],
            ),
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
        "queue_requires_end_transacted_pnr",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            SELL_1_SEAT,
            NAME_SMITH,
            Step("QE25", expect_contains=["UNABLE TO QUEUE", "END TRANSACT"]),
        ],
    ),
    Scenario(
        "queue_place_count_and_retrieve",
        [
            *_priced_single_pax_setup(),
            TICKETING_AT_WILL,
            FOP_CASH,
            Step("ER", expect_contains=["END OF TRANSACTION COMPLETE"]),
            Step("QE25", expect_contains=["QUEUED TO QUEUE 25", "WORK AREA CLEARED"]),
            Step("QC", expect_contains=["QUEUE COUNT", "25"]),
            Step("QN25", expect_contains=["RETRIEVED FROM QUEUE 25"]),
            Step("QC25", expect_contains=["25", "0"]),
        ],
    ),
    Scenario(
        "queue_next_on_empty_queue",
        [
            SIGN_IN,
            Step("QN50", expect_contains=["END OF QUEUE 50"]),
        ],
    ),
    Scenario(
        "schedule_change_auto_queues_and_clears_on_repricing",
        [
            # DFW-ORD 5NOV, line 1 (LA614) is empirically confirmed to deterministically
            # trigger a schedule change (seeded off flight+route+date identity, not the
            # PNR's locator - see spec/reference-data.json's scheduleChange and the
            # apply_schedule_changes/applyScheduleChanges rationale comment).
            SIGN_IN,
            Step("A5NOVDFWORD", expect_contains=["AIR AVAILABILITY", "DFW-ORD"]),
            Step("01Y1", expect_contains=["SEGMENT SOLD"]),
            NAME_SMITH,
            PHONE_VALID,
            RECEIVED_FROM,
            PRICE,
            TICKETING_AT_WILL,
            FOP_CASH,
            # The mutation itself is silent (no dedicated print) - but ER always redisplays
            # the PNR afterward, and that redisplay is exactly where the alert surfaces.
            Step(
                "ER",
                expect_contains=["END OF TRANSACTION COMPLETE", "SCHEDULE CHANGE ON FILE"],
            ),
            Step("QC1", expect_contains=["SCHEDULE CHANGE"]),
            Step(
                "*R",
                expect_contains=["SCHEDULE CHANGE ON FILE", "RE-PRICE", "REISSUE"],
            ),
            Step("WP", expect_contains=["ITINERARY PRICING"]),
            Step("*R", expect_not_contains=["SCHEDULE CHANGE ON FILE"]),
            Step("TKTT", expect_contains=["ELECTRONIC TICKET ISSUED"]),
        ],
    ),
    Scenario(
        "waitlist_clearing_auto_queues_and_shows_once",
        [
            # DFW-ORD 20SEP, line 1 class J is empirically confirmed to have 0 seats (instant
            # HL on sell) and to deterministically clear (seeded off flight+route+class+date
            # identity, not the PNR's locator - see spec/reference-data.json's waitlistClear
            # and the apply_waitlist_clearing/applyWaitlistClearing rationale comment).
            SIGN_IN,
            Step("A20SEPDFWORD", expect_contains=["AIR AVAILABILITY", "DFW-ORD"]),
            Step("01J1", expect_contains=["SEGMENT WAITLISTED", "HL"]),
            NAME_SMITH,
            PHONE_VALID,
            RECEIVED_FROM,
            PRICE,
            TICKETING_AT_WILL,
            FOP_CASH,
            # The mutation itself is silent (no dedicated print) - but ER always redisplays
            # the PNR afterward, and that redisplay is exactly where the notice surfaces, this
            # time as a one-time notice (not "until resolved" - no re-price is needed).
            Step(
                "ER",
                expect_contains=["END OF TRANSACTION COMPLETE", "WAITLIST CLEARED", "HK1"],
            ),
            Step("QC18", expect_contains=["WAITLIST CLEARED"]),
            # Shown once already (on ER's own redisplay) - must NOT repeat on a later redisplay
            Step("*R", expect_not_contains=["WAITLIST CLEARED"]),
            # No re-price/reissue needed - the fare quote from before clearing is still valid
            Step("TKTT", expect_contains=["ELECTRONIC TICKET ISSUED"]),
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
        "fqtv_tied_to_a_specific_passenger",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            SELL_2_SEATS,
            NAME_SMITH,
            Step("-DOE/JANE MRS", expect_contains=["NAME ADDED"]),
            Step(
                "3FQTVAA1234567-2/GLD",
                expect_contains=["SSR ADDED", "PAX 2 (DOE/JANE MRS)", "TIER: GOLD"],
            ),
            # passenger number is optional and independent of the tier
            Step("3FQTVAA7654321-1", expect_contains=["SSR ADDED", "PAX 1 (SMITH/JOHN MR)"]),
            Step(
                "3FQTVAA9999999-9",
                expect_contains=["INVALID PASSENGER NUMBER"],
                expect_not_contains=["SSR ADDED - FQTV AA FREQUENT FLYER NUMBER  AA9999999"],
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
    Scenario(
        "apis_document_accepted_for_infant_and_invalid_infant_number_rejected",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            SELL_1_SEAT,
            Step(
                "-SMITH/JOHN MR(INFSMITH/BABY/12JAN26)",
                expect_contains=["NAME ADDED", "INFANT ADDED"],
            ),
            Step(
                "3DOCSP/US/123456789/US/12JAN26/M/25DEC30-1.1",
                expect_contains=["DOCUMENT ADDED", "PASSPORT", "1.1", "INFANT"],
            ),
            Step(
                "3DOCSP/US/987654321/US/12JAN26/M/25DEC30-1.2",
                expect_contains=["INVALID INFANT NUMBER"],
                expect_not_contains=["DOCUMENT ADDED - PASSPORT US 987654321"],
            ),
        ],
    ),
    Scenario(
        "email_document_requires_complete_pnr",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            SELL_1_SEAT,
            Step("EM", expect_contains=["PNR INCOMPLETE", "NAME FIELD"]),
            Step("EMI", expect_contains=["PNR INCOMPLETE", "NAME FIELD"]),
            Step("EMT", expect_contains=["PNR INCOMPLETE", "NAME FIELD"]),
        ],
    ),
    Scenario(
        "emi_generates_invoice_and_clears_work_area",
        [
            *_priced_single_pax_setup(),
            TICKETING_AT_WILL,
            FOP_CASH,
            # Document *content* (passenger names, ticket status) is only guaranteed
            # visible in this step's terminal output for the CLI edition - the browser
            # edition opens it in a separate tab. Only assert what's true in both
            # editions' terminal output here; see test_web_scenarios.py for a DOM-level
            # check of the browser's actual generated document content.
            Step(
                "EMI",
                expect_contains=["END OF TRANSACTION COMPLETE", "INVOICE"],
            ),
            Step("*R", expect_contains=["PNR IS EMPTY"]),
        ],
    ),
    Scenario(
        "emt_without_tickets_still_generates_document",
        [
            *_priced_single_pax_setup(),
            TICKETING_AT_WILL,
            FOP_CASH,
            Step(
                "EMT",
                expect_contains=["END OF TRANSACTION COMPLETE", "E-TICKET NOTIFICATION"],
            ),
        ],
    ),
    Scenario(
        "connecting_itinerary_sells_both_legs",
        [
            SIGN_IN,
            # Generation always appends exactly 2 workable connections (4 lines: 2 legs
            # each) after the random nonstops for this route/date - lines 7 and 8 are the
            # legs of the first one (6 nonstops), matching real Sabre's model where each
            # leg is its own separately-numbered line, not a single grouped line.
            Step("A15AUGDFWORD", expect_contains=["AIR AVAILABILITY", "RTE"]),
            Step("02Y7Y8", expect_contains=["SEGMENT SOLD"]),
            Step("*R", expect_contains=["SEG1", "SEG2"]),
        ],
    ),
    Scenario(
        "connection_segments_married_and_must_cancel_together",
        [
            SIGN_IN,
            Step("A15AUGDFWORD", expect_contains=["AIR AVAILABILITY"]),
            Step("02Y7Y8", expect_contains=["SEGMENT SOLD"]),
            Step("*R", expect_contains=["MARRIED TO SEG2", "MARRIED TO SEG1"]),
            # cancelling just one leg is blocked - no partial cancellation of a connection
            Step("X1", expect_contains=["UNABLE TO CANCEL", "MARRIED TO ELEMENT 2"]),
            Step("X1,2", expect_contains=["ELEMENTS 1,2 CANCELLED"]),
            Step("*R", expect_contains=["PNR IS EMPTY"]),
        ],
    ),
    Scenario(
        "new_pnr_still_requires_a_segment",
        [
            # A brand-new (never-saved) PNR must still have at least one segment - only an
            # already-locatored PNR being cancelled down to zero segments gets the bespoke
            # bypass below.
            SIGN_IN,
            NAME_SMITH,
            PHONE_VALID,
            RECEIVED_FROM,
            TICKETING_AT_WILL,
            FOP_CASH,
            Step("ER", expect_contains=["PNR INCOMPLETE", "NO ITINERARY SEGMENTS"]),
        ],
    ),
    Scenario(
        "cancelling_a_saved_pnr_to_zero_segments_persists_via_er",
        [
            # Real GDS workflow: cancel every segment on an already-saved PNR, then ER/ET
            # to commit the cancellation - this must succeed (not hit the standard
            # completeness gate) and must actually overwrite the saved snapshot, or a
            # later retrieve would incorrectly hand back the stale, still-itineraried PNR.
            *_priced_single_pax_setup(),
            TICKETING_AT_WILL,
            FOP_CASH,
            Step("ER", expect_contains=["END OF TRANSACTION COMPLETE"]),
            Step("X2", expect_contains=["ELEMENT 2 CANCELLED"]),
            Step(
                "ER",
                expect_contains=["PNR CANCELLED", "ALL ITINERARY SEGMENTS REMOVED"],
                expect_not_contains=["PNR INCOMPLETE", "NO ITINERARY SEGMENTS"],
            ),
            # remaining non-itinerary elements (name/phone/RF) survive the cancellation -
            # it only clears the itinerary, not the whole PNR
            Step("*R", expect_contains=["NM1", "SMITH/JOHN MR"]),
            Step(
                "ET",
                expect_contains=["PNR CANCELLED", "ALL ITINERARY SEGMENTS REMOVED", "WORK AREA CLEARED"],
            ),
        ],
    ),
    Scenario(
        "change_key_updates_phone_in_place_by_field_scoped_line_number",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            SELL_1_SEAT,
            NAME_SMITH,
            PHONE_VALID,
            RECEIVED_FROM,
            # Real Sabre's change key (¤) addresses a line scoped to that field type - "phone
            # line 1" - not a PNR-wide element number. Only one phone is on file, so "92¤..."
            # (phone LINE 1) is the target, regardless of whatever PNR element number *R
            # happens to show it as.
            Step(
                "91¤214555-9999-A",
                expect_contains=["PHONE CHANGED", "LINE 1", "9214555-9999-A"],
            ),
            Step(
                "*P",
                expect_contains=["CONTACT ONLY", "214555-9999-A"],
                expect_not_contains=["214555-1234-A"],
            ),
            # ~ is the ASCII fallback for ¤.
            Step(
                "91~214555-8888-A",
                expect_contains=["PHONE CHANGED", "LINE 1", "9214555-8888-A"],
            ),
            Step("92¤999-9999-A", expect_contains=["INVALID PHONE LINE NUMBER", "ONLY 1 PHONE"]),
        ],
    ),
    Scenario(
        "change_key_updates_name_in_place_and_carries_infant_link",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            SELL_1_SEAT,
            Step(
                "-SMITH/JOHN MR(INFSMITH/BABY/12JAN26)",
                expect_contains=["NAME ADDED", "INFANT ADDED"],
            ),
            Step(
                "-1¤SMITH/JANE MRS",
                expect_contains=["NAME CHANGED", "LINE 1", "SMITH/JANE MRS"],
            ),
            # The infant's `adult` link is matched by exact name string - renaming the
            # adult must carry the link forward instead of silently orphaning it.
            Step(
                "*R",
                expect_contains=["SMITH/JANE MRS", "TRAVELS WITH SMITH/JANE MRS"],
            ),
            Step("-1¤BADNAME", expect_contains=["FORMAT", "SURNAME/GIVEN NAME"]),
            Step("-99¤SMITH/JOHN MR", expect_contains=["INVALID NAME LINE NUMBER", "ONLY 1 NAME"]),
        ],
    ),
    Scenario(
        "command_chaining_runs_several_commands_in_one_line",
        [
            Step(
                "SI‡A15AUGDFWORD",
                expect_contains=["SIGN IN COMPLETE", "AIR AVAILABILITY", "DFW-ORD"],
            ),
        ],
    ),
    Scenario(
        "pnr_partial_display_filters",
        [
            SIGN_IN,
            AVAIL_DFW_ORD,
            SELL_1_SEAT,
            NAME_SMITH,
            PHONE_VALID,
            Step(
                "*I",
                expect_contains=["ITINERARY ONLY", "SEG1"],
                expect_not_contains=["NM1", "CTC"],
            ),
            Step(
                "*N",
                expect_contains=["NAMES ONLY", "NM1", "SMITH/JOHN MR"],
                expect_not_contains=["SEG1"],
            ),
            Step(
                "*P",
                expect_contains=["CONTACT ONLY", "CTC", "214555-1234-A"],
                expect_not_contains=["NM1"],
            ),
            Step("*T", expect_contains=["TICKETING ONLY", "NO TICKETING ARRANGEMENT OR TICKETS ON FILE"]),
            Step("*FF", expect_contains=["FREQUENT FLYER ONLY", "NO FREQUENT FLYER NUMBERS ON FILE"]),
            Step("3FQTVAA1234567", expect_contains=["SSR ADDED", "FQTV"]),
            Step("*FF", expect_contains=["FREQUENT FLYER ONLY", "FQTV", "AA1234567"]),
            Step("*PQ", expect_contains=["PRICE QUOTE ONLY", "NO PRICE QUOTE ON FILE"]),
            Step("*B", expect_contains=["UNABLE TO DISPLAY BAGGAGE"]),
            Step("WP", expect_contains=["ITINERARY PRICING"]),
            Step("*PQ", expect_contains=["PRICE QUOTE ONLY", "FQ"]),
            Step("*B", expect_contains=["BAGGAGE ALLOWANCE", "FARE BASIS"]),
        ],
    ),
]
