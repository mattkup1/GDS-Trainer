"""Fixtures for the cross-edition scenario suite. Run with the gds-trainer-cli
venv active (see tests/README.md) - that's what makes `gds_trainer` importable;
`cdp`/`scenarios` resolve via pytest's normal same-directory import handling.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from rich.console import Console

from cdp import ChromeSession

WEB_INDEX_URL = (Path(__file__).resolve().parents[1] / "web" / "index.html").as_uri()


@pytest.fixture(scope="session")
def chrome():
    """One headless Chrome instance, reused across every web scenario test -
    launching a fresh browser per test would dominate the suite's runtime."""
    with ChromeSession() as session:
        session.start(WEB_INDEX_URL)
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
    from gds_trainer import printer
    from gds_trainer.state import STATE, fresh_pnr

    buf = io.StringIO()
    test_console = Console(file=buf, markup=False, highlight=False, width=200)
    monkeypatch.setattr(printer, "console", test_console)

    STATE.signed_in = False
    STATE.sine = None
    STATE.pcc = None
    STATE.last_avail = None
    STATE.pnr = fresh_pnr()
    STATE.last_display = []
    STATE.history = {}

    return buf
