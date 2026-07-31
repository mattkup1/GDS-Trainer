"""App state, ported from script.js's `state`/freshPNR()/logActivity()/nowStamp().

PNRs are kept as plain dicts (mirroring the JS app's own loose typing) so
save/retrieve can use copy.deepcopy the same way the JS app uses
JSON.parse(JSON.stringify(...)) for snapshotting.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .data import MONTHS


def fresh_pnr() -> dict[str, Any]:
    return {
        "locator": None,
        "names": [],
        "segments": [],
        "phones": [],
        "received_from": None,
        "ticketing": None,
        "pricing": None,
        "infants": [],
        "ssrs": [],
        "osis": [],
        "seats": [],
        "form_of_payment": None,
        "activity_log": [],
        "tickets": [],
    }


class AppState:
    def __init__(self) -> None:
        self.signed_in = False
        self.sine: str | None = None
        self.pcc: str | None = None
        self.last_avail: dict[str, Any] | None = None
        self.pnr: dict[str, Any] = fresh_pnr()
        self.last_display: list[dict[str, Any]] = []
        self.history: dict[str, dict[str, Any]] = {}


# Single shared instance, mirroring script.js's module-level `state`.
STATE = AppState()


def now_stamp() -> str:
    now = datetime.now()
    return f"{now.day}{MONTHS[now.month - 1]}/{now.hour:02d}{now.minute:02d}"


def log_activity(state: AppState, text: str) -> None:
    state.pnr["activity_log"].append(
        {"stamp": now_stamp(), "sine": state.sine or "----", "text": text}
    )
