"""Shared fixtures for the gds_trainer unit/integration suite."""

import pytest

from gds_trainer.state import STATE, fresh_pnr


@pytest.fixture(autouse=True)
def reset_state():
    """Give every test a clean STATE - these tests mutate module-level global state
    (state.py's STATE is a singleton, mirroring script.js's module-level `state`),
    so without this, tests would leak PNR data into each other depending on order.
    """
    STATE.signed_in = False
    STATE.sine = None
    STATE.pcc = None
    STATE.last_avail = None
    STATE.pnr = fresh_pnr()
    STATE.last_display = []
    STATE.history = {}
    STATE.queues = {}
    yield
