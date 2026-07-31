"""Unit tests for dates.py's parse_date/minutes_to_clock."""

import datetime as datetime_module

import pytest

from gds_trainer import dates as dates_module
from gds_trainer.dates import minutes_to_clock, parse_date


class _FixedDate(datetime_module.date):
    """date subclass with a controllable .today() for deterministic rollover tests."""

    _fixed: datetime_module.date

    @classmethod
    def today(cls):
        return cls._fixed


def _freeze_today(monkeypatch, year, month, day):
    fixed = type("_Fixed", (_FixedDate,), {"_fixed": datetime_module.date(year, month, day)})
    monkeypatch.setattr(dates_module, "date", fixed)
    return fixed._fixed


# ---------- parse_date: invalid input ----------

def test_parse_date_rejects_invalid_month():
    assert parse_date("15", "XXX") is None


def test_parse_date_rejects_day_zero():
    assert parse_date("0", "JAN") is None


def test_parse_date_rejects_day_above_31():
    assert parse_date("32", "JAN") is None


def test_parse_date_rejects_feb_30():
    assert parse_date("30", "FEB") is None  # no year has a Feb 30


def test_parse_date_rejects_non_numeric_day():
    assert parse_date("AB", "JAN") is None


# ---------- parse_date: rollover behavior ----------

def test_parse_date_same_day_as_today_does_not_roll_forward(monkeypatch):
    today = _freeze_today(monkeypatch, 2026, 1, 1)
    info = parse_date("1", "JAN")
    assert info is not None
    assert info.year == today.year


def test_parse_date_before_today_rolls_to_next_year(monkeypatch):
    _freeze_today(monkeypatch, 2026, 6, 15)
    info = parse_date("1", "JAN")  # Jan 1 already passed this year
    assert info is not None
    assert info.year == 2027


def test_parse_date_after_today_stays_this_year(monkeypatch):
    _freeze_today(monkeypatch, 2026, 1, 1)
    info = parse_date("15", "AUG")
    assert info is not None
    assert info.year == 2026


def test_parse_date_weekday_matches_independent_computation(monkeypatch):
    _freeze_today(monkeypatch, 2026, 1, 1)
    info = parse_date("15", "AUG")
    assert info is not None
    expected_weekday = datetime_module.date(info.year, 8, 15).strftime("%a").upper()
    assert info.weekday == expected_weekday


def test_parse_date_leap_year_feb_29(monkeypatch):
    _freeze_today(monkeypatch, 2028, 1, 1)  # 2028 is a leap year
    info = parse_date("29", "FEB")
    assert info is not None
    assert info.day == 29
    assert info.mon == "FEB"


def test_parse_date_non_leap_year_feb_29_rejected(monkeypatch):
    _freeze_today(monkeypatch, 2026, 1, 1)  # 2026 is not a leap year
    assert parse_date("29", "FEB") is None


# ---------- minutes_to_clock ----------

@pytest.mark.parametrize(
    "mins,expected",
    [
        (0, "1200A"),
        (1, "1201A"),
        (60, "100A"),
        (719, "1159A"),
        (720, "1200P"),
        (750, "1230P"),
        (1439, "1159P"),
        (1440, "1200A"),  # wraps to next day, same as 0
        (-60, "1100P"),  # negative wraps backward
    ],
)
def test_minutes_to_clock(mins, expected):
    assert minutes_to_clock(mins) == expected
