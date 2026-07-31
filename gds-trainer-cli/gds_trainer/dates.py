"""Date helpers, ported from script.js's parseDate()/minutesToClock()."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from .data import MONTHS, WEEKDAYS


@dataclass
class DateInfo:
    date: date
    day: int
    mon: str
    year: int
    weekday: str


def parse_date(day_str: str, mon_str: str) -> DateInfo | None:
    mon_str = mon_str.upper()
    if mon_str not in MONTHS:
        return None
    mi = MONTHS.index(mon_str)  # 0-based, JAN=0
    try:
        day = int(day_str, 10)
    except (TypeError, ValueError):
        return None
    if not day or day < 1 or day > 31:
        return None

    today = date.today()
    year = today.year
    days_in_month = calendar.monthrange(year, mi + 1)[1]
    if day > days_in_month:
        return None

    d = date(year, mi + 1, day)
    if d < today:
        year += 1
        d = date(year, mi + 1, day)

    weekday = WEEKDAYS[(d.weekday() + 1) % 7]  # JS getDay(): SUN=0..SAT=6
    return DateInfo(date=d, day=day, mon=mon_str, year=year, weekday=weekday)


def minutes_to_clock(mins: int) -> str:
    mins = ((mins % 1440) + 1440) % 1440
    hh, mm = divmod(mins, 60)
    ampm = "A" if hh < 12 else "P"
    hh12 = hh % 12
    if hh12 == 0:
        hh12 = 12
    return f"{hh12}{mm:02d}{ampm}"
