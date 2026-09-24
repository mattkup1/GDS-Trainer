"""Runs the shared scenarios (scenarios.py) against the browser edition, via a
real headless Chrome driven over CDP (tests/cdp.py) - the actual page, the
actual #cmdline input, the actual keydown handler, not script.js internals.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from cdp import split_transcript
from scenarios import SCENARIOS


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_scenario_against_web(scenario, web_session):
    commands = [step.command for step in scenario.steps]
    full_transcript = web_session.run_commands(commands)
    chunks = split_transcript(full_transcript, commands)

    for step, output in zip(scenario.steps, chunks):
        for expected in step.expect_contains:
            assert expected in output, (
                f"[{scenario.name}] after {step.command!r}, expected {expected!r} in output:\n{output}"
            )
        for unexpected in step.expect_not_contains:
            assert unexpected not in output, (
                f"[{scenario.name}] after {step.command!r}, did NOT expect {unexpected!r} in output:\n{output}"
            )


def test_seat_map_panel_renders_aircraft_accurate_grid(web_session):
    """GUI-only regression guard (not part of the shared Scenario/Step text
    system, since this asserts DOM structure, not terminal text) - see
    notes/GUI Expansion Scope-Out.md. Confirms the seat map panel opens and
    renders the correct number of seat cells for whichever aircraft the
    deterministic RNG assigned to this flight, independently re-derived from
    spec/reference-data.json rather than trusting the app's own lookup.
    """
    seat_layouts = json.loads(
        (Path(__file__).resolve().parents[1] / "spec" / "reference-data.json").read_text()
    )["seatLayouts"]

    web_session.run_commands(["SI", "A15AUGDFWORD", "01Y1", "41"])

    panel_state = web_session.evaluate(
        "({"
        "hidden: document.getElementById('seatMapPanel').classList.contains('hidden'),"
        "cellCount: document.querySelectorAll('.seatcell').length,"
        "title: document.getElementById('seatMapTitle').textContent"
        "})"
    )

    assert panel_state["hidden"] is False

    m = re.match(r"^SEAT MAP - [A-Z]{2}\d+ (\S+) SEG\d+$", panel_state["title"])
    assert m, f"unexpected seat map title format: {panel_state['title']!r}"
    layout = seat_layouts.get(m.group(1), seat_layouts["_default"])
    expected_cells = layout["rows"] * sum(len(group) for group in layout["cols"])
    assert panel_state["cellCount"] == expected_cells


def test_pnr_dock_panel_reflects_pnr_state(web_session):
    """GUI-only regression guard for the persistent PNR dock panel added
    alongside the seat-map GUI - see notes/GUI Expansion Scope-Out.md item
    #2. Confirms the dock mirrors live PNR state (not just the terminal),
    and that the explicit renderPnrPanel() call added to ignorePnr() (IG) -
    a reset path that doesn't go through refreshAndPrintPNR - actually fires,
    rather than leaving stale content in the panel.
    """
    web_session.run_commands(["SI", "A15AUGDFWORD", "01Y1"])

    body_text = web_session.evaluate("document.getElementById('dockPnrBody').textContent")
    assert "SEG1" in body_text

    web_session.run_commands(["IG"])
    empty_state = web_session.evaluate(
        "({body: document.getElementById('dockPnrBody').textContent,"
        " rloc: document.getElementById('dockRloc').textContent})"
    )
    assert "PNR IS EMPTY" in empty_state["body"]
    assert "NOT SAVED" in empty_state["rloc"]


def test_lookup_panel_decode_click_runs_real_command(web_session):
    """GUI-only regression guard for the ENCODE/DECODE dock panel. Confirms an
    exact code match ranks first (searching "ORD" among thousands of airports
    should surface Chicago O'Hare, not an unrelated city whose name merely
    contains "ord" like Alamogordo), and that clicking a result runs the real
    DC{code} command through submitCommand()/processCommand() rather than
    rendering decoded info directly from state - the guiding constraint in
    notes/GUI Expansion Scope-Out.md.
    """
    web_session.run_commands(["SI"])
    web_session.evaluate("document.querySelector('.helper-btn[data-target=\"lookup\"]').click()")
    web_session.evaluate(
        "(() => {"
        "const input = document.getElementById('lookupInput');"
        "input.value = 'ORD';"
        "input.dispatchEvent(new Event('input', { bubbles: true }));"
        "})()"
    )

    first_code = web_session.evaluate("document.querySelector('.lookup-code').textContent")
    assert first_code == "ORD"

    web_session.evaluate("document.querySelector('.lookup-row').click()")
    output = web_session.evaluate("document.getElementById('output').textContent")
    assert "DCORD" in output
    assert "O'HARE" in output.upper()


def test_format_finder_click_inserts_without_submitting(web_session):
    """GUI-only regression guard for the FORMAT FINDER dock panel. Per the
    guiding constraint in notes/GUI Expansion Scope-Out.md, GUI affordances
    must not become a point-and-click alternative to typing a PNR-mutating
    entry - clicking a result should only insert its example into #cmdline
    for the user to review and submit themselves, never auto-submit it.
    """
    web_session.run_commands(["SI"])
    web_session.evaluate("document.querySelector('.helper-btn[data-target=\"formats\"]').click()")
    web_session.evaluate(
        "(() => {"
        "const input = document.getElementById('formatsInput');"
        "input.value = 'seat map';"
        "input.dispatchEvent(new Event('input', { bubbles: true }));"
        "})()"
    )

    before_output = web_session.evaluate("document.getElementById('output').textContent")
    web_session.evaluate("document.querySelector('.format-row').click()")
    after = web_session.evaluate(
        "({cmdline: document.getElementById('cmdline').value,"
        " output: document.getElementById('output').textContent})"
    )

    assert after["cmdline"] == "41"
    assert after["output"] == before_output  # nothing was submitted


_FULL_BOOKING_COMMANDS = [
    "SI", "A15AUGDFWORD", "01Y1", "-SMITH/JOHN MR", "WP",
    "9214555-1234-A", "6JSMITH", "7TAW/", "FPCASH",
]


def _stub_window_open(web_session) -> None:
    """Installs a fake window.open that captures the written HTML into
    window.__capturedDoc instead of opening a real tab - CDP has no simple
    hook for a newly-opened window/target, and this project's test harness
    otherwise sticks to evaluate()-only DOM assertions (see cdp.py). Must
    run before the command that triggers window.open."""
    web_session.evaluate(
        "window.__capturedDoc = null;"
        "window.open = () => ({ document: { open(){}, write(h){ window.__capturedDoc = h; }, close(){} } });"
    )


def test_emi_document_contains_full_invoice_content(web_session):
    """GUI-only regression guard for the EMI itinerary/invoice document -
    see notes/GUI Expansion Scope-Out.md-style rationale in CLAUDE.md's
    EM/EMI/EMT bullet. The shared scenario in scenarios.py only asserts
    terminal-visible confirmation text (true for both editions); this test
    verifies the actual document content the browser writes into the new
    tab, which has no CLI equivalent to cross-check against.
    """
    _stub_window_open(web_session)
    web_session.run_commands([*_FULL_BOOKING_COMMANDS, "EMI"])
    doc = web_session.evaluate("window.__capturedDoc")

    assert doc is not None
    for expected in ["GDS TRAINER", "INVOICE", "SMITH/JOHN MR", "FARE SUMMARY", "NOT YET TICKETED"]:
        assert expected in doc, f"expected {expected!r} in generated document:\n{doc}"


def test_pop_up_blocked_shows_terminal_error_not_a_crash(web_session):
    """If the browser blocks window.open (returns a falsy value), the app
    should surface a terminal error instead of throwing - see
    openItineraryDocument in web/script.js."""
    web_session.evaluate("window.open = () => null;")
    output = web_session.run_commands([*_FULL_BOOKING_COMMANDS, "EMI"])
    assert "POP-UP BLOCKED" in output
    assert "WORK AREA CLEARED" in output
