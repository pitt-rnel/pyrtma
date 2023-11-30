import ctypes
from typing import Type

from .message_base import MessageBase
from .validators import Int16, Double, Int32, Uint32

# Type Aliases
MODULE_ID = ctypes.c_short
HOST_ID = ctypes.c_short
MSG_TYPE = ctypes.c_int
MSG_COUNT = ctypes.c_int


class MessageHeader(MessageBase):
    """RTMA Message Header class"""

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

    @property
    def version(self) -> int:
        return self.reserved

    @version.setter
    def version(self, value: int):
        self.reserved = value


class TimeCodeMessageHeader(MessageHeader):

    utc_seconds: Uint32 = Uint32()
    utc_fraction: Uint32 = Uint32()


def get_header_cls(timecode: bool = False) -> Type[MessageHeader]:
    if timecode:
        return TimeCodeMessageHeader
    else:
        return MessageHeader
