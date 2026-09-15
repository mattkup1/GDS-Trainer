"""Fixtures for the cross-edition scenario suite. Run with the gds-trainer-cli
venv active (see tests/README.md) - that's what makes `gds_trainer` importable;
`cdp`/`scenarios` resolve via pytest's normal same-directory import handling.
"""

from __future__ import annotations

import io
from datetime import date
from pathlib import Path

import pytest
from rich.console import Console

from cdp import ChromeSession

WEB_INDEX_URL = (Path(__file__).resolve().parents[1] / "web" / "index.html").as_uri()

# Both editions resolve a bare "{DD}{MMM}" command date (availability, schedule,
# ticketing arrangement, ...) to the *next* future occurrence relative to "today" -
# there's no year in the command syntax at all (see dates.py's parse_date /
# script.js's parseDate). scenarios.py then hardcodes flight numbers, seat
# availability, and connection line numbers that the shared seeded PRNG produces
# for specific route+resolved-date combinations (e.g. "empirically confirmed"
# comments near the schedule-change/waitlist-clearing scenarios) - those are only
# stable if "today" resolves every {DD}{MMM} in scenarios.py to the same year each
# of those magic constants was captured against. Freezing "today" here at the date
# the suite was last verified against (2026-08-14, before any of the 15AUG/20SEP/
# 5NOV dates used in scenarios.py had passed) keeps that resolution fixed
# regardless of the real wall-clock date the suite happens to run on - without it,
# every scenario pinned to a date that's since passed silently rolls to next year's
# occurrence and starts generating different (but still internally consistent)
# flights, breaking the hardcoded assertions until someone notices and re-freezes.
FROZEN_TODAY = date(2026, 8, 14)


@pytest.fixture(scope="session")
def chrome():
    """One headless Chrome instance, reused across every web scenario test -
    launching a fresh browser per test would dominate the suite's runtime."""
    with ChromeSession() as session:
        session.start(WEB_INDEX_URL, freeze_today=FROZEN_TODAY)
        yield session


@pytest.fixture
def web_session(chrome):
    """Give each test a freshly-booted app state via the page's own #btnReset
    button (see cdp.ChromeSession.reset for why not Page.navigate)."""
    chrome.reset()
    return chrome


@pytest.fixture
def cli_console(monkeypatch):
    """Swap gds_trainer's printer console for a wide, StringIO-backed one so
    each command's output can be captured and inspected, and reset STATE."""
    from gds_trainer import dates, printer
    from gds_trainer.state import STATE, fresh_pnr

    buf = io.StringIO()
    test_console = Console(file=buf, markup=False, highlight=False, width=200)
    monkeypatch.setattr(printer, "console", test_console)

    # See FROZEN_TODAY above - keeps parse_date's "next future occurrence" resolution
    # stable regardless of the real wall-clock date the suite runs on.
    class _FrozenDate(date):
        @classmethod
        def today(cls):
            return cls(FROZEN_TODAY.year, FROZEN_TODAY.month, FROZEN_TODAY.day)

    monkeypatch.setattr(dates, "date", _FrozenDate)

    STATE.signed_in = False
    STATE.sine = None
    STATE.pcc = None
    STATE.last_avail = None
    STATE.pnr = fresh_pnr()
    STATE.last_display = []
    STATE.history = {}
    STATE.queues = {}

    return buf
