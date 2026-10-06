"""Date helpers, ported from script.js's parseDate()/minutesToClock()."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta

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


def _date_info(d: date) -> DateInfo:
    return DateInfo(
        date=d,
        day=d.day,
        mon=MONTHS[d.month - 1],
        year=d.year,
        weekday=WEEKDAYS[(d.weekday() + 1) % 7],
    )


def parse_date_after(day_str: str, mon_str: str, base: date) -> DateInfo | None:
    """Resolve a bare {DD}{MMM} to its first occurrence on or after `base` (not after
    today, like parse_date) - a return-availability date is relative to the outbound
    date it follows, so "1R10JUL" after a 15NOV outbound means 10JUL of next year."""
    mon_str = mon_str.upper()
    if mon_str not in MONTHS:
        return None
    mi = MONTHS.index(mon_str)
    try:
        day = int(day_str, 10)
    except (TypeError, ValueError):
        return None
    if day < 1 or day > 31:
        return None
    for year in (base.year, base.year + 1):
        if day > calendar.monthrange(year, mi + 1)[1]:
            continue
        d = date(year, mi + 1, day)
        if d >= base:
            return _date_info(d)
    return None


def parse_day_after(day_str: str, base: date) -> DateInfo | None:
    """Resolve a bare day-of-month ("1R12") to the first such day on or after `base`,
    staying in base's month if it still fits and otherwise moving to a later month."""
    try:
        day = int(day_str, 10)
    except (TypeError, ValueError):
        return None
    if day < 1 or day > 31:
        return None
    year, month = base.year, base.month
    for _ in range(13):
        if day <= calendar.monthrange(year, month)[1]:
            d = date(year, month, day)
            if d >= base:
                return _date_info(d)
        month += 1
        if month > 12:
            month, year = 1, year + 1
    return None


def shift_date(base: date, days: int) -> DateInfo | None:
    """base +/- days, refusing a date already in the past (nothing to search there)."""
    d = base + timedelta(days=days)
    if d < date.today():
        return None
    return _date_info(d)


def parse_clock(num_str: str, ampm: str) -> int | None:
    """"6P"/"630P"/"1215A" -> minutes since midnight, or None if not a real clock time."""
    if not num_str.isdigit():
        return None
    if len(num_str) <= 2:
        hh, mm = int(num_str), 0
    else:
        hh, mm = int(num_str[:-2]), int(num_str[-2:])
    if not 1 <= hh <= 12 or mm > 59:
        return None
    return (hh % 12 + (12 if ampm.upper() == "P" else 0)) * 60 + mm


def minutes_to_clock(mins: int) -> str:
    mins = ((mins % 1440) + 1440) % 1440
    hh, mm = divmod(mins, 60)
    ampm = "A" if hh < 12 else "P"
    hh12 = hh % 12
    if hh12 == 0:
        hh12 = 12
    return f"{hh12}{mm:02d}{ampm}"


def format_arrival(dep: int, arr: int) -> str:
    """Real Sabre marks an arrival that lands on a different calendar day than its
    departure with a +N suffix (e.g. "245A+1") rather than silently showing a same-day
    clock time - without it, a red-eye/long-haul flight looks like it arrives before it
    departs, or like a suspiciously short trip. Computed as a diff of whole-day counts
    between the two raw minute values (not just "does arr exceed 1440") so it stays
    correct even after a schedule change shifts both dep and arr by an identical delta -
    genuinely relative, not tied to either value being in [0,1440) to begin with.
    """
    offset = arr // 1440 - dep // 1440
    suffix = "" if offset == 0 else (f"+{offset}" if offset > 0 else str(offset))
    return minutes_to_clock(arr) + suffix
