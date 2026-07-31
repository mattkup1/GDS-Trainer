"""Runs the shared scenarios (scenarios.py) against the CLI edition directly,
via gds_trainer.dispatcher.process_command - no subprocess, no Chrome.
"""

from __future__ import annotations

import pytest

from scenarios import SCENARIOS


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.name)
def test_scenario_against_cli(scenario, cli_console):
    from gds_trainer.dispatcher import process_command

    for step in scenario.steps:
        before = len(cli_console.getvalue())
        process_command(step.command)
        output = cli_console.getvalue()[before:]

        for expected in step.expect_contains:
            assert expected in output, (
                f"[{scenario.name}] after {step.command!r}, expected {expected!r} in output:\n{output}"
            )
        for unexpected in step.expect_not_contains:
            assert unexpected not in output, (
                f"[{scenario.name}] after {step.command!r}, did NOT expect {unexpected!r} in output:\n{output}"
            )
