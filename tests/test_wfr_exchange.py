"""Ticket exchange (WFR{TICKET#}) needs a dynamically-generated ticket number as
part of its own command string, which the shared Scenario/Step format (scenarios.py)
has no mechanism to capture from a prior step's output - so this drives the CLI
directly instead, the same way test_commands_unit.py exercises pure logic, but
through real commands end-to-end rather than hand-built state. Rejection paths that
don't need a captured value are still covered as ordinary shared scenarios (see
scenarios.py's "exchange_ticket_*" entries), which do run against both editions.
"""

from __future__ import annotations

import re

from gds_trainer.dispatcher import process_command as pc
from gds_trainer.state import STATE


def _run(*commands: str) -> str:
    for cmd in commands:
        pc(cmd)
    return ""


def test_exchange_applies_old_value_and_reissues(cli_console):
    _run(
        "SI",
        "A15AUGDFWORD",
        "01Y1",
        "-SMITH/JOHN MR",
        "9214555-1234-A",
        "6JSMITH",
        "WP",
        "7TAW/",
        "FPCASH",
        "ER",
        "TKTT",
    )
    old_total = STATE.pnr["pricing"]["total"]
    old_ticket = STATE.pnr["tickets"][0]["ticket_num"]
    assert re.match(r"^\d{3}-\d{10}$", old_ticket)

    # Selling a second segment invalidates pricing/tickets and stashes them for exchange.
    _run("02Y1")
    assert STATE.pnr["pricing"] is None
    assert STATE.pnr["tickets"] == []
    assert STATE.pnr["prior_tickets"][0]["ticket_num"] == old_ticket
    assert STATE.pnr["prior_pricing"]["total"] == old_total

    _run("WP")
    new_total = STATE.pnr["pricing"]["total"]
    expected_diff = round((new_total - old_total) * 100) / 100

    cli_console.truncate(0)
    cli_console.seek(0)
    _run(f"WFR{old_ticket}")
    out = cli_console.getvalue()

    assert "EXCHANGE PROCESSED" in out
    assert old_ticket in out
    if expected_diff > 0:
        assert f"ADCOLL): USD {expected_diff:.2f}" in out
    elif expected_diff < 0:
        assert f"RESIDUAL VALUE: USD {-expected_diff:.2f}" in out
    else:
        assert "EVEN EXCHANGE" in out

    # Reissued with a fresh ticket number, and the exchange is consumed (not repeatable).
    assert STATE.pnr["tickets"][0]["ticket_num"] != old_ticket
    assert STATE.pnr["prior_tickets"] == []
    assert STATE.pnr["prior_pricing"] is None


def test_exchange_rejects_unknown_ticket_number(cli_console):
    _run(
        "SI",
        "A15AUGDFWORD",
        "01Y1",
        "-SMITH/JOHN MR",
        "9214555-1234-A",
        "6JSMITH",
        "WP",
        "7TAW/",
        "FPCASH",
        "ER",
        "TKTT",
        "02Y1",
        "WP",
    )
    cli_console.truncate(0)
    cli_console.seek(0)
    _run("WFR045-1234567890")
    assert "INVALID TICKET NUMBER" in cli_console.getvalue()
