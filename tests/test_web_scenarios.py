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


def test_toolbar_sign_in_button_submits_real_command(web_session):
    """Confirms the toolbar's quick-action buttons go through the real
    command dispatcher (submitCommand -> processCommand), never a shortcut
    that bypasses it - the guiding constraint in notes/GUI Expansion
    Scope-Out.md. web_session starts signed-out (see conftest.web_session).
    """
    before = web_session.evaluate(
        "({signInDisabled: document.getElementById('btnSignIn').disabled,"
        " priceDisabled: document.getElementById('btnPrice').disabled})"
    )
    assert before["signInDisabled"] is False
    assert before["priceDisabled"] is True

    web_session.evaluate("document.getElementById('btnSignIn').click()")

    after = web_session.evaluate(
        "({output: document.getElementById('output').textContent,"
        " signInDisabled: document.getElementById('btnSignIn').disabled,"
        " priceDisabled: document.getElementById('btnPrice').disabled})"
    )
    assert "SIGN IN COMPLETE" in after["output"]
    assert after["signInDisabled"] is True
    assert after["priceDisabled"] is False
