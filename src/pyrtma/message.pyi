import ctypes
from typing import ClassVar

class _RTMA_MSG_HEADER(ctypes.Structure):
    msg_type: int
    msg_count: int
    send_time: float
    recv_time: float
    src_host_id: int
    src_mod_id: int
    dest_host_id: int
    dest_mod_id: int
    num_data_bytes: int
    remaining_bytes: int
    is_dynamic: int
    reserved: int

class MessageHeader(_RTMA_MSG_HEADER): ...

class TimeCodeMessageHeader(MessageHeader):
    utc_seconds: int
    utc_fraction: int

class MessageData(ctypes.Structure):
    type_id: ClassVar[int]
    type_name: ClassVar[str]
    type_hash: int
    type_src: str
