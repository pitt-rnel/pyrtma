"""Attribute access on message classes, without the v1 conversions.

Fields declared with validators, as compiled definitions have them, convert
``char`` arrays to and from ``str``. Fields declared directly in ``_fields_``
behave as ctypes fields do.
"""

import ctypes

import pytest

import pyrtma.core_defs as cd
from pyrtma.header import MessageHeader
from pyrtma.message_base import MessageMeta, field_size, field_struct
from pyrtma.message_data import MessageData
from pyrtma.validators import String


class PlainChars(MessageData, metaclass=MessageMeta):
    _fields_ = [("name", ctypes.c_char * 8)]


class Named(MessageData, metaclass=MessageMeta):
    name = String(8)


def test_plain_char_fields_read_as_bytes() -> None:
    msg = PlainChars()

    msg.name = b"abc"

    assert msg.name == b"abc"


def test_plain_char_fields_take_only_bytes() -> None:
    msg = PlainChars()

    with pytest.raises(TypeError):
        msg.name = "abc"  # type: ignore[assignment]


def test_string_fields_still_read_as_str() -> None:
    msg = Named()

    msg.name = "abc"

    assert msg.name == "abc"
    assert bytes(msg)[:4] == b"abc\x00"


def test_field_size_of_a_string_counts_its_terminator() -> None:
    assert field_size(Named, "name") == 8
    assert field_size(Named(), "name") == 8


@pytest.mark.parametrize(
    ("cls", "name", "size"),
    [
        (MessageHeader, "send_time", 8),
        (MessageHeader, "src_host_id", 2),
        (cd.MDF_FAILED_MESSAGE, "msg_header", 48),
        (cd.DATASET, "msg_types", 4 * 64),
        (cd.MDF_RTMA_LOG, "message", cd.MAX_LOG_LENGTH),
    ],
)
def test_field_size_of_each_kind_of_field(cls: type, name: str, size: int) -> None:
    assert field_size(cls, name) == size


@pytest.mark.parametrize(
    ("cls", "name"),
    [(Named, "nope"), (PlainChars, "name"), (MessageHeader, "LAYOUT")],
    ids=["unknown", "plain ctypes field", "class attribute"],
)
def test_field_size_rejects_what_is_not_a_field(cls: type, name: str) -> None:
    with pytest.raises(KeyError, match=name):
        field_size(cls, name)


def test_field_struct_reads_and_writes_a_field_in_place() -> None:
    msg = cd.MDF_DATASET_STATUS()
    layout, offset = field_struct(msg, "elapsed_time")

    layout.pack_into(msg, offset, 2.5)

    assert msg.elapsed_time == 2.5
    assert layout.unpack_from(msg, offset) == (2.5,)
    from_class, class_offset = field_struct(cd.MDF_DATASET_STATUS, "elapsed_time")
    assert (from_class.format, class_offset) == (layout.format, offset)


@pytest.mark.parametrize(
    ("cls", "name"),
    [(Named, "nope"), (PlainChars, "name"), (MessageHeader, "LAYOUT")],
    ids=["unknown", "plain ctypes field", "class attribute"],
)
def test_field_struct_rejects_what_is_not_a_field(cls: type, name: str) -> None:
    with pytest.raises(KeyError, match=name):
        field_struct(cls, name)


def test_subscription_messages_share_their_msg_type_layout() -> None:
    # The client writes msg_type into any of them with one struct.
    layouts = {
        (layout.format, offset)
        for layout, offset in (
            field_struct(cls, "msg_type")
            for cls in (
                cd.MDF_SUBSCRIBE,
                cd.MDF_UNSUBSCRIBE,
                cd.MDF_PAUSE_SUBSCRIPTION,
                cd.MDF_RESUME_SUBSCRIPTION,
            )
        )
    }

    assert len(layouts) == 1
