"""Attribute access on message classes, without the v1 conversions.

Fields declared with validators, as compiled definitions have them, convert
``char`` arrays to and from ``str``. Fields declared directly in ``_fields_``
behave as ctypes fields do.
"""

import ctypes

import pytest

import pyrtma.core_defs as cd
from pyrtma.header import MessageHeader
from pyrtma.message_base import MessageMeta
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


@pytest.mark.parametrize(
    "cls",
    [
        cd.MDF_SUBSCRIBE,
        cd.MDF_UNSUBSCRIBE,
        cd.MDF_PAUSE_SUBSCRIPTION,
        cd.MDF_RESUME_SUBSCRIPTION,
    ],
)
def test_subscription_message_is_built_from_its_type(cls: type) -> None:
    # The client builds these with the type as the only argument, which
    # ctypes stores in the one field without running its validator.
    msg = cls(7010)

    assert [name for name, *_ in cls._fields_] == ["_msg_type"]
    assert msg.msg_type == 7010
