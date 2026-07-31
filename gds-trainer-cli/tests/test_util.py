"""Unit tests for util.py's pad()."""

from gds_trainer.util import pad


def test_pad_extends_short_string():
    assert pad("Y", 3) == "Y  "


def test_pad_leaves_exact_length_unchanged():
    assert pad("ABC", 3) == "ABC"


def test_pad_does_not_truncate_long_string():
    assert pad("TOOLONG", 3) == "TOOLONG"


def test_pad_coerces_non_string_input():
    assert pad(7, 3) == "7  "


def test_pad_zero_width():
    assert pad("X", 0) == "X"
