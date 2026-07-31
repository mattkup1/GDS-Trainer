"""Unit tests for a few of commands.py's pure(ish) helpers, in isolation from the
full dispatch/print flow: mask_card, _trip_type, and the PNR-completeness walker
(_first_incomplete_message) that both end_transaction and issue_tickets share.
"""

from gds_trainer.commands import _first_incomplete_message, _trip_type, mask_card
from gds_trainer.state import STATE


# ---------- mask_card ----------

def test_mask_card_masks_all_but_last_four():
    assert mask_card("4111111111111111") == "XXXXXXXXXXXX1111"


def test_mask_card_short_number_not_masked():
    assert mask_card("1234") == "1234"


def test_mask_card_shorter_than_four_unmasked():
    assert mask_card("12") == "12"


# ---------- _trip_type ----------

def test_trip_type_one_way():
    segs = [{"orig": "DFW", "dest": "ORD"}]
    assert _trip_type(segs) == "OW"


def test_trip_type_round_trip():
    segs = [{"orig": "DFW", "dest": "ORD"}, {"orig": "ORD", "dest": "DFW"}]
    assert _trip_type(segs) == "RT"


def test_trip_type_circle_trip():
    segs = [
        {"orig": "DFW", "dest": "ORD"},
        {"orig": "ORD", "dest": "JFK"},
        {"orig": "JFK", "dest": "DFW"},
    ]
    assert _trip_type(segs) == "CT"


def test_trip_type_open_jaw():
    segs = [{"orig": "DFW", "dest": "ORD"}, {"orig": "MIA", "dest": "JFK"}]
    assert _trip_type(segs) == "OJ"


# ---------- _first_incomplete_message ----------

def _complete_pnr():
    STATE.pnr["segments"] = [{"orig": "DFW", "dest": "ORD", "seats": 1}]
    STATE.pnr["names"] = ["SMITH/JOHN MR"]
    STATE.pnr["pricing"] = {"mode": "WP"}
    STATE.pnr["phones"] = ["214555-1234-A"]
    STATE.pnr["received_from"] = "JSMITH"
    STATE.pnr["form_of_payment"] = {"type": "CASH", "display": "CASH"}
    STATE.pnr["ticketing"] = "7TAW/"
    STATE.pnr["locator"] = "ABC123"
    STATE.pnr["tickets"] = []


def test_end_transaction_complete_pnr_has_no_incomplete_message():
    _complete_pnr()
    assert _first_incomplete_message("end_transaction") is None


def test_end_transaction_missing_segments_is_first_rule_checked():
    _complete_pnr()
    STATE.pnr["segments"] = []
    assert _first_incomplete_message("end_transaction") == "PNR INCOMPLETE - NO ITINERARY SEGMENTS"


def test_end_transaction_missing_names_reported_when_segments_present():
    _complete_pnr()
    STATE.pnr["names"] = []
    msg = _first_incomplete_message("end_transaction")
    assert msg == "PNR INCOMPLETE - NEED NAME FIELD (ENTRY: -SURNAME/GIVEN)"


def test_end_transaction_missing_pricing():
    _complete_pnr()
    STATE.pnr["pricing"] = None
    assert "FARE QUOTE" in _first_incomplete_message("end_transaction")


def test_end_transaction_missing_ticketing_arrangement():
    _complete_pnr()
    STATE.pnr["ticketing"] = None
    assert "TICKETING ARRANGEMENT" in _first_incomplete_message("end_transaction")


def test_issue_tickets_requires_locator_first():
    _complete_pnr()
    STATE.pnr["locator"] = None
    msg = _first_incomplete_message("issue_tickets")
    assert "END TRANSACT" in msg


def test_issue_tickets_rejects_already_ticketed():
    _complete_pnr()
    STATE.pnr["tickets"] = [{"passenger": "SMITH/JOHN MR", "ticket_num": "001-1", "is_infant": False}]
    msg = _first_incomplete_message("issue_tickets")
    assert "ALREADY TICKETED" in msg


def test_issue_tickets_complete_pnr_has_no_incomplete_message():
    _complete_pnr()
    assert _first_incomplete_message("issue_tickets") is None
