"""Runs the shared scenarios (scenarios.py) against the browser edition, via a
real headless Chrome driven over CDP (tests/cdp.py) - the actual page, the
actual #cmdline input, the actual keydown handler, not script.js internals.
"""

from __future__ import annotations

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
