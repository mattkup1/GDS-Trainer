"""Airport code -> [name, city, country] lookup, loaded from spec/airports.json -
shared with the browser edition (see spec/README.md)."""

from __future__ import annotations

import json
from pathlib import Path

_SPEC_DIR = Path(__file__).resolve().parents[2] / "spec"


def _load() -> dict[str, list[str]]:
    return json.loads((_SPEC_DIR / "airports.json").read_text(encoding="utf-8"))


AIRPORTS: dict[str, list[str]] = _load()


def city_name(code: str) -> str:
    a = AIRPORTS.get(code)
    if a:
        return f"{a[1].upper()} {code}"
    return f"CITY {code}"
