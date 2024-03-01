import time

from .exceptions import InvalidMessageDefinition
from .message import Message, MessageHeader, MessageData, get_header_cls, get_msg_cls

from collections import deque
from typing import Type, Optional, Tuple


class MessageBufferOverflow(Exception):
    """Raised when a MessageBuffer reaches max allowed size"""

    pass


class MessageBuffer:
    DEFAULT_ALLOC = 8192
    DEFAULT_SIZE = 8192
    MAX_SIZE = 65536

    def __init__(self, timecode: bool = False):
        self._timecode: bool = timecode
        self._wbufp: int = 0
        self._rbufp: int = 0
        self._buf: bytearray = bytearray(MessageBuffer.DEFAULT_SIZE)
        self._deque: deque[Message] = deque()
        self._header_cls: Type[MessageHeader] = get_header_cls(timecode)
        self._header_size: int = get_header_cls(timecode)().size
        self._pending: Optional[MessageHeader] = None

    @property
    def length(self) -> int:
        return self._wbufp

    @property
    def capacity(self) -> int:
        return len(self._buf)

    @property
    def unused(self) -> int:
        return self.capacity - self.length

    @property
    def pending(self) -> bool:
        return self._pending is not None

    @property
    def bytes_needed(self) -> int:
        if self._pending is None:
            return 0

        return max(self._pending.num_data_bytes - (self._wbufp - self._rbufp), 0)

    def get(self) -> Optional[Message]:
        try:
            return self._deque.popleft()
        except IndexError:
            return None

    def append(self, buf: bytes):
        sz = len(buf)
        i = self._wbufp
        j = i + sz

        if len(buf) < self.unused:
            self._buf[i:j] = buf
        else:
            if (sz + self.capacity) < MessageBuffer.MAX_SIZE:
                pad = max(MessageBuffer.DEFAULT_ALLOC - sz, 0)
                self._buf.extend(bytes(sz + pad))
                self._buf[i:j] = buf
            else:
                raise MessageBufferOverflow(
                    "Client should call read_message more frequently."
                )

        self._wbufp = j

        while self._parse():
            pass

    def _parse(self) -> bool:
        if self._pending is None:
            if (self._wbufp - self._rbufp) >= self._header_size:
                hdr = self._header_cls.from_buffer_copy(self._buf, self._rbufp)
                hdr.recv_time = time.perf_counter()
                self._pending = hdr
                self._rbufp += self._header_size

                if self._rbufp == self._wbufp:
                    self._wbufp = 0
                    self._rbufp = 0

            else:
                return False

        if (self._wbufp - self._rbufp) < self._pending.num_data_bytes:
            return False

        hdr = self._pending

        msg_cls = get_msg_cls(hdr.msg_type)
        type_size = msg_cls.type_size
        if type_size == -1:  # not defined for v1 message defs
            type_size = msg_cls().size

        if type_size != hdr.num_data_bytes:
            raise InvalidMessageDefinition(
                f"Received message header indicating a message data size ({hdr.num_data_bytes}) that does not match the expected size ({type_size}) of message type {msg_cls.type_name}. Message definitions may be out of sync across systems."
            )

        data = msg_cls.from_buffer_copy(self._buf, self._rbufp)

        self._rbufp += hdr.num_data_bytes
        if self._rbufp == self._wbufp:
            self._wbufp = 0
            self._rbufp = 0

        self._deque.append(Message(hdr, data))
        self._pending = None

        return True
