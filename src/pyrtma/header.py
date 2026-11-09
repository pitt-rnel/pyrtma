"""The RTMA message header."""

import ctypes
import struct
from typing import ClassVar, Tuple, Type

from .message_base import MessageBase, MessageMeta
from .validators import Int16, Double, Int32, Uint32

# Type Aliases
MODULE_ID = ctypes.c_short
HOST_ID = ctypes.c_short
MSG_TYPE = ctypes.c_int
MSG_COUNT = ctypes.c_int


class MessageHeader(MessageBase, metaclass=MessageMeta):
    """RTMA Message Header class

    Fields are read and set through their validators, like any message's.
    The client builds whole headers with :meth:`_pack_into` instead, which
    writes every field with one ``struct`` call, in the same layout.
    """

    msg_type: Int32 = Int32()
    msg_count: Int32 = Int32()
    send_time: Double = Double()
    recv_time: Double = Double()
    src_host_id: Int16 = Int16()
    src_mod_id: Int16 = Int16()
    dest_host_id: Int16 = Int16()
    dest_mod_id: Int16 = Int16()
    num_data_bytes: Int32 = Int32()
    remaining_bytes: Int32 = Int32()
    is_dynamic: Int32 = Int32()
    reserved: Uint32 = Uint32()

    # The fields' layout as a struct, set below once the class exists.
    _LAYOUT: ClassVar[struct.Struct]

    @property
    def version(self) -> int:
        return self.reserved

    @version.setter
    def version(self, value: int):
        self.reserved = value

    @classmethod
    def _pack_into(
        cls,
        buffer: bytearray,
        offset: int,
        msg_type: int,
        msg_count: int,
        send_time: float,
        recv_time: float,
        src_host_id: int,
        src_mod_id: int,
        dest_host_id: int,
        dest_mod_id: int,
        num_data_bytes: int,
        remaining_bytes: int,
        is_dynamic: int,
        reserved: int,
    ) -> None:
        """Write a whole header into a buffer, in the header's layout.

        The bytes are the same as a header with these field values, but
        nothing is validated, and integers must already fit their fields:
        ``struct`` raises rather than truncate, as ctypes would.

        Args:
            buffer: A writable buffer with room for a header at ``offset``.
            offset: Where the header starts in ``buffer``.
            msg_type: The header's fields, in their order.
            msg_count: See ``msg_type``.
            send_time: See ``msg_type``.
            recv_time: See ``msg_type``.
            src_host_id: See ``msg_type``.
            src_mod_id: See ``msg_type``.
            dest_host_id: See ``msg_type``.
            dest_mod_id: See ``msg_type``.
            num_data_bytes: See ``msg_type``.
            remaining_bytes: See ``msg_type``.
            is_dynamic: See ``msg_type``.
            reserved: See ``msg_type``; the message's version.

        Raises:
            struct.error: A value doesn't fit its field, or the buffer is
                too small.
        """
        cls._LAYOUT.pack_into(
            buffer,
            offset,
            msg_type,
            msg_count,
            send_time,
            recv_time,
            src_host_id,
            src_mod_id,
            dest_host_id,
            dest_mod_id,
            num_data_bytes,
            remaining_bytes,
            is_dynamic,
            reserved,
        )

    def _set_recv_time(self, value: float) -> None:
        """Set ``recv_time`` directly, without its validator.

        The client does this for every message it reads.

        Args:
            value: The receive time.
        """
        _RECV_TIME.pack_into(self, _RECV_TIME_OFFSET, value)


def _field_code(cls: Type[ctypes.Structure], name: str, ctype: type) -> str:
    """Find the ``struct`` format code of a structure field.

    Args:
        cls: The structure, for error messages.
        name: The field's name, for error messages.
        ctype: The field's ctypes type.

    Raises:
        TypeError: The type isn't a simple ctypes type, such as an array or a
            pointer, or its standard ``struct`` size isn't its ctypes size.

    Returns:
        The one-character format code.
    """
    code = getattr(ctype, "_type_", None)
    where = f"{cls.__name__}.{name}"
    if not isinstance(code, str) or len(code) != 1:
        raise TypeError(f"{where}: {ctype.__name__} has no struct format code")
    try:
        size = struct.calcsize("=" + code)
    except struct.error as e:
        raise TypeError(f"{where}: {ctype.__name__} has no struct format code") from e
    if size != ctypes.sizeof(ctype):
        raise TypeError(
            f"{where}: {ctype.__name__} is {ctypes.sizeof(ctype)} bytes, but "
            f"struct's {code!r} is {size}"
        )
    return code


def _layout_struct(cls: Type[ctypes.Structure]) -> struct.Struct:
    """Build a ``struct.Struct`` with the same layout as a ctypes structure.

    Each field gets its type's format code in native byte order and standard
    sizes, and pad bytes go wherever the structure has padding, so every field
    lands at its ctypes offset and the size is the structure's.

    Args:
        cls: The structure.

    Raises:
        TypeError: A field isn't a simple ctypes type, its size differs from
            its format code's, or it's a bit field.

    Returns:
        The layout.
    """
    fmt = "="
    end = 0
    for name, ctype, *bits in cls._fields_:
        if bits:
            raise TypeError(f"{cls.__name__}.{name}: bit fields aren't supported")
        code = _field_code(cls, name, ctype)
        field = getattr(cls, name)
        if field.offset > end:
            fmt += f"{field.offset - end}x"
        fmt += code
        end = field.offset + field.size
    total = ctypes.sizeof(cls)
    if total > end:
        fmt += f"{total - end}x"
    return struct.Struct(fmt)


def _field_struct(cls: Type[ctypes.Structure], name: str) -> Tuple[struct.Struct, int]:
    """Build a ``struct.Struct`` for one field of a ctypes structure.

    Args:
        cls: The structure.
        name: The field's name in ``_fields_``.

    Raises:
        TypeError: As for :func:`_layout_struct`.

    Returns:
        The field's layout, and its offset in the structure.
    """
    ctype = dict((n, t) for n, t, *_ in cls._fields_)[name]
    return struct.Struct("=" + _field_code(cls, name, ctype)), getattr(cls, name).offset


MessageHeader._LAYOUT = _layout_struct(MessageHeader)
_RECV_TIME, _RECV_TIME_OFFSET = _field_struct(MessageHeader, "_recv_time")


def get_header_cls() -> Type[MessageHeader]:
    """Get the message header class.

    There is one header class; this function is kept for existing callers.

    Returns:
        The ``MessageHeader`` class.
    """
    return MessageHeader
