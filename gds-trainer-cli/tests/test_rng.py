"""Unit tests for rng.py's hash_str/mulberry32.

Values are regression-pinned (computed once, asserted forever) rather than
independently re-derived — the point isn't to re-implement FNV-1a/mulberry32
in the test, it's to catch any accidental change to the algorithm that would
silently reshuffle every synthetic flight/fare/seat this app has ever shown.
"""

from gds_trainer.rng import hash_str, mulberry32


def test_hash_str_empty_string():
    assert hash_str("") == 2166136261  # FNV-1a offset basis, untouched


def test_hash_str_regression_pinned_values():
    assert hash_str("abc") == 440920331
    assert hash_str("DFWORD15AUG2026") == 3544092130


def test_hash_str_returns_uint32_range():
    h = hash_str("some fairly long arbitrary route+date string AA1234")
    assert 0 <= h <= 0xFFFFFFFF


def test_mulberry32_same_seed_reproduces_sequence():
    seed = hash_str("test-seed")
    rng_a = mulberry32(seed)
    rng_b = mulberry32(seed)
    assert [rng_a() for _ in range(10)] == [rng_b() for _ in range(10)]


def test_mulberry32_different_seed_diverges():
    rng_a = mulberry32(hash_str("test-seed"))
    rng_b = mulberry32(hash_str("different-seed"))
    assert [rng_a() for _ in range(5)] != [rng_b() for _ in range(5)]


def test_mulberry32_values_in_unit_interval():
    rng = mulberry32(hash_str("range-check"))
    for _ in range(200):
        v = rng()
        assert 0.0 <= v < 1.0


def test_mulberry32_regression_pinned_first_values():
    rng = mulberry32(hash_str("test-seed"))
    got = [rng() for _ in range(5)]
    expected = [
        0.35841897572390735,
        0.5269410228356719,
        0.12075472134165466,
        0.4566779953893274,
        0.02979772095568478,
    ]
    for g, e in zip(got, expected):
        assert g == e
