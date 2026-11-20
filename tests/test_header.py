"""The message header's packed layout, and the header's raw read and write helpers.

``MessageHeader._pack_into`` writes a whole header with one ``struct`` call,
and the client and manager read and write single fields in raw buffers. The
layouts behind them are written out in ``pyrtma.header``, so these tests
compare each with headers built field by field.
"""

import ctypes
import random
import struct
from typing import Any

import pytest

from pyrtma.header import MessageHeader
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


@pytest.mark.parametrize("seed", [1, 2, 3])
def test_unpack_type_and_size_reads_both_fields(seed: int) -> None:
    values = random_values(random.Random(seed))
    header = header_from_fields(values)
    expected = (values["msg_type"], values["num_data_bytes"])

    assert MessageHeader.unpack_type_and_size(header) == expected
    assert MessageHeader.unpack_type_and_size(bytes(header) + b"payload") == expected


def test_unpack_num_data_bytes_reads_it_from_a_buffer() -> None:
    values = random_values(random.Random(11))
    buffer = bytearray(bytes(header_from_fields(values))) + b"payload"

    assert MessageHeader.unpack_num_data_bytes(buffer) == (values["num_data_bytes"],)


def test_pack_send_time_changes_only_send_time() -> None:
    values = random_values(random.Random(13))
    buffer = bytearray(bytes(header_from_fields(values))) + b"payload"

    MessageHeader.pack_send_time(buffer, 99.25)

    expected = bytes(header_from_fields({**values, "send_time": 99.25}))
    assert bytes(buffer) == expected + b"payload"
