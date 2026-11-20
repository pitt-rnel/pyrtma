"""Tests for the random values that ``MessageBase.from_random()`` uses."""

from __future__ import annotations

import ctypes
import math
from typing import Any

import pytest

from pyrtma.utils.random_fields import _random_struct

DRAWS = 50

INT_TYPES = [
    ctypes.c_int8,
    ctypes.c_uint8,
    ctypes.c_int16,
    ctypes.c_uint16,
    ctypes.c_int32,
    ctypes.c_uint32,
    ctypes.c_int64,
    ctypes.c_uint64,
    ctypes.c_long,
    ctypes.c_ulong,
    ctypes.c_longlong,
    ctypes.c_ulonglong,
]


def draw(ctype: Any, count: int = DRAWS) -> list[Any]:
    """Fill a structure with one scalar and one array field many times.

    Args:
        ctype: The ctypes element type of both fields.
        count: How many structures to fill.

    Returns:
        Every value drawn, scalars and array elements together.
    """

    class Sample(ctypes.Structure):
        _fields_ = [("scalar", ctype), ("array", ctype * 8)]

    values: list[Any] = []
    for _ in range(count):
        sample = _random_struct(Sample())
        values.append(sample.scalar)
        values.extend(sample.array)
    return values


def type_range(ctype: Any) -> tuple[int, int]:
    """Return the smallest and largest value an integer ctype holds.

    Args:
        ctype: A ctypes integer type.

    Returns:
        The minimum and maximum.
    """
    bits = ctypes.sizeof(ctype) * 8
    if ctype(-1).value < 0:
        return -(2 ** (bits - 1)), 2 ** (bits - 1) - 1
    return 0, 2**bits - 1


@pytest.mark.parametrize("ctype", [ctypes.c_int64, ctypes.c_longlong])
def test_int64_values_use_full_range(ctype: Any) -> None:
    values = draw(ctype)

    assert any(v < 0 for v in values)
    assert any(abs(v) >= 2**32 for v in values)


@pytest.mark.parametrize("ctype", [ctypes.c_uint64, ctypes.c_ulonglong])
def test_uint64_values_use_full_range(ctype: Any) -> None:
    values = draw(ctype)

    assert any(v >= 2**32 for v in values)


@pytest.mark.parametrize("ctype", INT_TYPES)
def test_int_values_stay_in_range(ctype: Any) -> None:
    low, high = type_range(ctype)

    values = draw(ctype)

    assert all(low <= v <= high for v in values)
    # A sign error would put every value in the lower half of an unsigned range.
    assert any(v > high // 2 for v in values)


@pytest.mark.parametrize("ctype", [ctypes.c_float, ctypes.c_double])
def test_float_values_include_negatives_and_large_values(ctype: Any) -> None:
    values = draw(ctype)

    assert all(math.isfinite(v) for v in values)
    assert any(v < 0 for v in values)
    assert any(abs(v) > 1 for v in values)
