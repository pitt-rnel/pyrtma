"""Random field values for ``MessageBase.from_random()``.

Integer values cover the whole range of each field's type, and float values
are finite, with random sign and magnitude.
"""

import ctypes
import random
import string
from typing import Any, TypeVar

# ctypes simple-type codes for signed and unsigned integers. Types are matched
# by code and size rather than by class, because ctypes aliases differ between
# platforms: c_int64 is c_long on Linux and c_longlong on Windows.
_SIGNED_CODES = "bhilq"
_UNSIGNED_CODES = "BHILQ"

# Decimal exponents for random float magnitudes, kept well inside each type's
# finite range so that values never overflow to infinity.
_FLOAT_EXPONENTS = (-30, 30)
_DOUBLE_EXPONENTS = (-300, 300)


def _random_str(length: int) -> str:
    """Utility to generate random string

    Args:
        length (int): String length

    Returns:
        str: Random string
    """
    if length > 1:
        length -= 1

    return "".join(random.choice(string.printable) for _ in range(length))


def _random_int_array(length: int, min: int = 0, max: int = 9) -> list[int]:
    """Utility to generate random int array

    Args:
        length (int): Array length
        min (int, optional): Minimum value. Defaults to 0.
        max (int, optional): Maximum value. Defaults to 9.

    Returns:
        list[int]: List of random ints
    """
    return [random.randint(min, max) for _ in range(length)]


def _int_range(ctype: Any) -> tuple[int, int] | None:
    """Return the range of a ctypes integer type.

    Args:
        ctype: A ctypes type.

    Returns:
        The minimum and maximum value, or None if ``ctype`` isn't an integer
        type.
    """
    code = getattr(ctype, "_type_", None)
    if not isinstance(code, str):
        return None
    bits = ctypes.sizeof(ctype) * 8
    if code in _SIGNED_CODES:
        return -(2 ** (bits - 1)), 2 ** (bits - 1) - 1
    if code in _UNSIGNED_CODES:
        return 0, 2**bits - 1
    return None


def _random_real(exponents: tuple[int, int]) -> float:
    """Return a finite float with random sign and magnitude.

    Args:
        exponents: The smallest and largest decimal exponent of the magnitude.

    Returns:
        A value whose magnitude lies between ``10**exponents[0]`` and
        ``10**(exponents[1] + 1)``.
    """
    magnitude = random.uniform(1.0, 10.0) * 10.0 ** random.randint(*exponents)
    return random.choice((-1.0, 1.0)) * magnitude


def _random_float_array(length: int) -> list[float]:
    """Utility to generate random float array

    Restricted to values that a 32-bit float can hold without overflowing.

    Args:
        length (int): Array length

    Returns:
        list[float]: List of random floats
    """
    return [_random_real(_FLOAT_EXPONENTS) for _ in range(length)]


def _random_double_array(length: int) -> list[float]:
    """Utility to generate random float array

    Values are of double (64-bit) precision

    Args:
        length (int): Array length

    Returns:
        list[float]: List of random floats
    """
    return [_random_real(_DOUBLE_EXPONENTS) for _ in range(length)]


def _random_byte_array(length: int) -> bytes:
    """Utility to generate random byte string

    Args:
        length (int): byte string length

    Returns:
        bytes: Random byte string
    """
    return bytes([random.randint(0, 255) for _ in range(length)])


CStruct = TypeVar("CStruct", bound=ctypes.Structure)


def _random_struct(obj: CStruct) -> CStruct:
    """Fill a ctypes structure with random values, in place.

    Nested structures and arrays of structures are filled recursively. Field
    types that aren't recognized keep their current value.

    Args:
        obj: The structure to fill.

    Returns:
        The same structure, filled.
    """
    for _name, ftype, *_ in obj._fields_:
        name = _name[1:] if _name[0] == "_" else _name
        if issubclass(ftype, ctypes.Structure):
            setattr(obj, name, _random_struct(getattr(obj, name)))
        elif issubclass(ftype, ctypes.Array):
            length: int = ftype._length_  # type: ignore
            etype: type = ftype._type_  # type: ignore
            int_range = _int_range(etype)
            if issubclass(etype, ctypes.Structure):
                for i in range(length):
                    getattr(obj, name)[i] = _random_struct(getattr(obj, name)[i])
            elif etype is ctypes.c_char:
                setattr(obj, name, _random_str(length))
            elif etype is ctypes.c_ubyte:
                getattr(obj, name)[:] = _random_byte_array(length)
            elif int_range is not None:
                low, high = int_range
                getattr(obj, name)[:] = _random_int_array(length, min=low, max=high)
            elif etype is ctypes.c_float:
                getattr(obj, name)[:] = _random_float_array(length)
            elif etype is ctypes.c_double:
                getattr(obj, name)[:] = _random_double_array(length)
        else:
            int_range = _int_range(ftype)
            if ftype is ctypes.c_char:
                setattr(obj, name, _random_str(1))
            elif ftype is ctypes.c_ubyte:
                setattr(obj, name, random.randint(0, 255))
            elif int_range is not None:
                setattr(obj, name, random.randint(*int_range))
            elif ftype is ctypes.c_float:
                setattr(obj, name, _random_real(_FLOAT_EXPONENTS))
            elif ftype is ctypes.c_double:
                setattr(obj, name, _random_real(_DOUBLE_EXPONENTS))

    return obj
