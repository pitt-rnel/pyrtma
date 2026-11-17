"""The message header's packed layout, which the client builds headers with.

``MessageHeader._pack_into`` writes a whole header with one ``struct`` call.
Its layout is built from the header's own ctypes fields when the module is
imported, so these tests compare it with headers built field by field.
"""

import ctypes
import random
import struct
from typing import Any

import pytest

from pyrtma.header import MessageHeader, _field_struct, _layout_struct
from pyrtma.validators import IntValidatorBase

FIELD_NAMES = [name[1:] for name, *_ in MessageHeader._fields_]


def random_values(rng: random.Random) -> dict[str, Any]:
    """Draw a value for every header field, anywhere in the field's range.

    Args:
        rng: The random generator.

    Returns:
        Values by field name.
    """
    values: dict[str, Any] = {}
    for name in FIELD_NAMES:
        validator = vars(MessageHeader)[name]
        if isinstance(validator, IntValidatorBase):
            values[name] = rng.randint(validator.min, validator.max)
        else:
            values[name] = rng.uniform(-1e12, 1e12)
    return values


def header_from_fields(values: dict[str, Any]) -> MessageHeader:
    """Build a header by setting its fields one by one.

    Args:
        values: Values by field name.

    Returns:
        The header.
    """
    header = MessageHeader()
    for name, value in values.items():
        setattr(header, name, value)
    return header


def test_layout_has_the_headers_size() -> None:
    assert MessageHeader._LAYOUT.size == ctypes.sizeof(MessageHeader)


def test_packed_header_matches_one_set_field_by_field() -> None:
    rng = random.Random(1234)

    for _ in range(200):
        values = random_values(rng)
        packed = bytearray(MessageHeader._LAYOUT.size)
        MessageHeader._pack_into(packed, 0, **values)

        assert bytes(packed) == bytes(header_from_fields(values))


def test_layout_reads_back_in_field_order() -> None:
    values = random_values(random.Random(99))
    header = header_from_fields(values)

    unpacked = MessageHeader._LAYOUT.unpack_from(header)

    assert list(unpacked) == [values[name] for name in FIELD_NAMES]


def test_pack_into_writes_only_its_bytes() -> None:
    size = MessageHeader._LAYOUT.size
    buffer = bytearray(b"\xaa" * (size + 16))
    values = random_values(random.Random(7))

    MessageHeader._pack_into(buffer, 8, **values)

    assert buffer[:8] == b"\xaa" * 8
    assert buffer[8 + size :] == b"\xaa" * 8
    assert bytes(buffer[8 : 8 + size]) == bytes(header_from_fields(values))


def test_set_recv_time_changes_only_recv_time() -> None:
    values = random_values(random.Random(5))
    header = header_from_fields(values)

    header._set_recv_time(1234.5)

    assert header.recv_time == 1234.5
    expected = header_from_fields({**values, "recv_time": 1234.5})
    assert bytes(header) == bytes(expected)


def test_layout_adds_the_structures_padding() -> None:
    class Padded(ctypes.Structure):
        _fields_ = [("a", ctypes.c_int8), ("b", ctypes.c_double), ("c", ctypes.c_int16)]

    layout = _layout_struct(Padded)
    packed = layout.pack(-5, 2.5, 300)

    assert layout.size == ctypes.sizeof(Padded)
    assert packed == bytes(Padded(-5, 2.5, 300))


@pytest.mark.parametrize(
    "ctype", [ctypes.c_char * 4, ctypes.c_char_p], ids=["char array", "pointer"]
)
def test_layout_rejects_fields_struct_cannot_describe(ctype: Any) -> None:
    class Unpackable(ctypes.Structure):
        _fields_ = [("a", ctypes.c_int32), ("b", ctype)]

    with pytest.raises(TypeError, match="Unpackable.b"):
        _layout_struct(Unpackable)


def test_field_struct_finds_one_field() -> None:
    layout, offset = _field_struct(MessageHeader, "_num_data_bytes")
    header = MessageHeader()
    header.num_data_bytes = 4096

    (value,) = layout.unpack_from(header, offset)

    assert value == 4096
    assert layout.size == struct.calcsize("=i")


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("msg_type", 6001),
        ("msg_count", -7),
        ("send_time", 12.5),
        ("recv_time", 13.25),
        ("src_host_id", 3),
        ("src_mod_id", 101),
        ("dest_host_id", -2),
        ("dest_mod_id", 200),
        ("num_data_bytes", 4096),
        ("remaining_bytes", 9),
        ("is_dynamic", 1),
        ("reserved", 0x89ABCDEF),
    ],
)
def test_field_struct_reads_each_field_by_its_name(name: str, value: Any) -> None:
    header = MessageHeader()
    setattr(header, name, value)

    layout, offset = MessageHeader.field_struct(name)

    assert layout.unpack_from(header, offset) == (value,)
    assert layout.size == getattr(MessageHeader, f"_{name}").size


def test_field_struct_writes_into_a_buffer() -> None:
    buffer = bytearray(ctypes.sizeof(MessageHeader))
    layout, offset = MessageHeader.field_struct("send_time")

    layout.pack_into(buffer, offset, 99.5)

    assert MessageHeader.from_buffer(buffer).send_time == 99.5


def test_field_struct_rejects_an_unknown_name() -> None:
    with pytest.raises(KeyError, match="no_such_field"):
        MessageHeader.field_struct("no_such_field")
