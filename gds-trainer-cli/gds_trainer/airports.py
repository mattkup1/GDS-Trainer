"""Airport code -> [name, city, country] lookup, loaded from airports.json
(converted once from the browser app's airports.js — same OpenFlights data)."""

from __future__ import annotations

import json
from importlib import resources


def _load() -> dict[str, list[str]]:
    with resources.files(__package__).joinpath("airports.json").open("r", encoding="utf-8") as f:
        return json.load(f)


AIRPORTS: dict[str, list[str]] = _load()


def city_name(code: str) -> str:
    a = AIRPORTS.get(code)
    if a:
        return f"{a[1].upper()} {code}"
    return f"CITY {code}"
