"""QuickLogger version 1 files built by hand, for the formatter and reader tests.

The layout is that of the existing readers, MATLAB's included: a file header
of six 32-bit fields, every message header, a 32-bit offset into the data
block for each message, then the data block. Everything is in native byte
order, as the formatter writes it.
"""

from __future__ import annotations

import ctypes
import struct

from pyrtma.header import MessageHeader
from pyrtma.message import Message
from pyrtma.message_data import MessageData

from .test_msg_defs import test_defs as td

FILE_HEADER_SIZE: int = 24


def message(data: MessageData, recv_time: float) -> Message:
    """Wrap message data in a header like one a logger receives.

    Args:
        data: The message data.
        recv_time: The header's receive time, which the reader sorts by.

    Returns:
        The message.
    """
    header = MessageHeader()
    header.msg_type = data.type_id
    header.num_data_bytes = ctypes.sizeof(data)
    header.recv_time = recv_time
    return Message(header, data)


def starts(count: int, first: int = 0) -> list[Message]:
    """``TEST_START`` messages with IDs ``first`` onwards."""
    messages = []
    for i in range(first, first + count):
        data = td.MDF_TEST_START()
        data.id = i
        messages.append(message(data, float(i)))
    return messages


def v1_file(messages: list[Message]) -> bytes:
    """Lay out messages as a QuickLogger version 1 file.

    Args:
        messages: The messages, in file order.

    Returns:
        The file's bytes.
    """
    header_size = ctypes.sizeof(MessageHeader)
    blobs = [bytes(m.data)[: m.header.num_data_bytes] for m in messages]
    offsets, position = [], 0
    for blob in blobs:
        offsets.append(position)
        position += len(blob)
    data = b"".join(blobs)
    total = FILE_HEADER_SIZE + len(messages) * (4 + header_size) + len(data)
    file_header = struct.pack("=6I", 1, total, len(messages), header_size, 4, len(data))
    return (
        file_header
        + b"".join(bytes(m.header) for m in messages)
        + struct.pack(f"={len(offsets)}I", *offsets)
        + data
    )
