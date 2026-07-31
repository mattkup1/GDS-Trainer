"""Deterministic hashing/PRNG, ported from script.js's hashStr()/mulberry32().

Not a bit-for-bit match with the JS app's output (that's not required — this
is a separate app), but the same FNV-1a + mulberry32 algorithms, so the same
query always yields the same synthetic flight/seat/fare data within a session.
"""

from __future__ import annotations

from typing import Callable

_MASK32 = 0xFFFFFFFF


def _i32(x: int) -> int:
    x &= _MASK32
    return x - 0x100000000 if x >= 0x80000000 else x


def _u32(x: int) -> int:
    return x & _MASK32


def _imul32(a: int, b: int) -> int:
    return _i32((_i32(a) * _i32(b)) & _MASK32)


def _urshift(x: int, n: int) -> int:
    return _u32(x) >> (n & 31)


def hash_str(s: str) -> int:
    h = 2166136261
    for ch in s:
        h = _i32(h ^ ord(ch))
        h = _imul32(h, 16777619)
    return _u32(h)


def mulberry32(seed: int) -> Callable[[], float]:
    box = {"a": _i32(seed)}

    def rng() -> float:
        a = _i32(box["a"] + 0x6D2B79F5)
        box["a"] = a
        t = _imul32(a ^ _urshift(a, 15), 1 | a)
        t = _i32((t + _imul32(t ^ _urshift(t, 7), 61 | t)) ^ t)
        return _u32(t ^ _urshift(t, 14)) / 4294967296

    return rng
