import ctypes

import pyrtma
from typing import ClassVar

from pyrtma.message_base import MessageBase
from pyrtma.message_data import MessageData
from pyrtma.validators import (
    Int8,
    Int16,
    Int32,
    Int64,
    Uint8,
    Uint16,
    Uint32,
    Uint64,
    Float,
    Double,
    Struct,
    IntArray,
    FloatArray,
    StructArray,
    String,
    Bytes,
)


# Constants
MAX_MODULES: int = 200
DYN_MOD_ID_START: int = 100
MAX_HOSTS: int = 5
MAX_MESSAGE_TYPES: int = 10000
MIN_STREAM_TYPE: int = 9000
MAX_TIMERS: int = 100
MAX_INTERNAL_TIMERS: int = 20
MAX_RTMA_MSG_TYPE: int = 99
MAX_RTMA_MODULE_ID: int = 9
MAX_LOGGER_FILENAME_LENGTH: int = 256
MAX_CONTIGUOUS_MESSAGE_DATA: int = 9000
ALL_MESSAGE_TYPES: int = 2147483647

# String Constants

# Type Aliases
MODULE_ID = ctypes.c_short
HOST_ID = ctypes.c_short
MSG_TYPE = ctypes.c_int
MSG_COUNT = ctypes.c_int

# Host IDs
LOCAL_HOST: int = 0
ALL_HOSTS: int = 32767

# Module IDs
MID_MESSAGE_MANAGER: int = 0
MID_QUICK_LOGGER: int = 5

# Message Type IDs
MT_EXIT: int = 0
MT_KILL: int = 1
MT_ACKNOWLEDGE: int = 2
MT_FAIL_SUBSCRIBE: int = 6
MT_FAILED_MESSAGE: int = 8
MT_CONNECT: int = 13
MT_DISCONNECT: int = 14
MT_SUBSCRIBE: int = 15
MT_UNSUBSCRIBE: int = 16
MT_MODULE_READY: int = 26
MT_LM_EXIT: int = 55
MT_SAVE_MESSAGE_LOG: int = 56
MT_MESSAGE_LOG_SAVED: int = 57
MT_PAUSE_MESSAGE_LOGGING: int = 58
MT_RESUME_MESSAGE_LOGGING: int = 59
MT_RESET_MESSAGE_LOG: int = 60
MT_DUMP_MESSAGE_LOG: int = 61
MT_TIMING_MESSAGE: int = 80
MT_FORCE_DISCONNECT: int = 82
MT_PAUSE_SUBSCRIPTION: int = 85
MT_RESUME_SUBSCRIPTION: int = 86
MT_LM_READY: int = 96


# Struct Definitions
class RTMA_MSG_HEADER(MessageBase):
    _fields_ = [
        ("_msg_type", MSG_TYPE),
        ("_msg_count", MSG_COUNT),
        ("_send_time", ctypes.c_double),
        ("_recv_time", ctypes.c_double),
        ("_src_host_id", HOST_ID),
        ("_src_mod_id", MODULE_ID),
        ("_dest_host_id", HOST_ID),
        ("_dest_mod_id", MODULE_ID),
        ("_num_data_bytes", ctypes.c_int),
        ("_remaining_bytes", ctypes.c_int),
        ("_is_dynamic", ctypes.c_int),
        ("_reserved", ctypes.c_uint),
    ]

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


# Message Definitions
@pyrtma.message_def
class MDF_EXIT(MessageData):
    _fields_ = []
    type_id: ClassVar[int] = 0
    type_name: ClassVar[str] = "EXIT"
    type_hash: ClassVar[int] = 0x095E0546
    type_source: ClassVar[str] = "core_defs/core_defs.yaml"
    type_def: ClassVar[str] = "'EXIT:\n  id: 0\n  fields: null'"


@pyrtma.message_def
class MDF_KILL(MessageData):
    _fields_ = []
    type_id: ClassVar[int] = 1
    type_name: ClassVar[str] = "KILL"
    type_hash: ClassVar[int] = 0x82FC702D
    type_source: ClassVar[str] = "core_defs/core_defs.yaml"
    type_def: ClassVar[str] = "'KILL:\n  id: 1\n  fields: null'"


@pyrtma.message_def
class MDF_ACKNOWLEDGE(MessageData):
    _fields_ = []
    type_id: ClassVar[int] = 2
    type_name: ClassVar[str] = "ACKNOWLEDGE"
    type_hash: ClassVar[int] = 0xB725B581
    type_source: ClassVar[str] = "core_defs/core_defs.yaml"
    type_def: ClassVar[str] = "'ACKNOWLEDGE:\n  id: 2\n  fields: null'"


@pyrtma.message_def
class MDF_FAIL_SUBSCRIBE(MessageData):
    _fields_ = [
        ("_mod_id", MODULE_ID),
        ("_reserved", ctypes.c_short),
        ("_msg_type", MSG_TYPE),
    ]
    type_id: ClassVar[int] = 6
    type_name: ClassVar[str] = "FAIL_SUBSCRIBE"
    type_hash: ClassVar[int] = 0x9AD70A15
    type_source: ClassVar[str] = "core_defs/core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'FAIL_SUBSCRIBE:\n  id: 6\n  fields:\n    mod_id: MODULE_ID\n    reserved: short\n    msg_type: MSG_TYPE'"

    mod_id: Int16 = Int16()
    reserved: Int16 = Int16()
    msg_type: Int32 = Int32()


@pyrtma.message_def
class MDF_FAILED_MESSAGE(MessageData):
    _fields_ = [
        ("_dest_mod_id", MODULE_ID),
        ("_reserved", ctypes.c_short * 3),
        ("_time_of_failure", ctypes.c_double),
        ("_msg_header", RTMA_MSG_HEADER),
    ]
    type_id: ClassVar[int] = 8
    type_name: ClassVar[str] = "FAILED_MESSAGE"
    type_hash: ClassVar[int] = 0xDCA545B2
    type_source: ClassVar[str] = "core_defs/core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'FAILED_MESSAGE:\n  id: 8\n  fields:\n    dest_mod_id: MODULE_ID\n    reserved: short[3]\n    time_of_failure: double\n    msg_header: RTMA_MSG_HEADER'"

    dest_mod_id: Int16 = Int16()
    reserved: IntArray[Int16] = IntArray(Int16, 3)
    time_of_failure: Double = Double()
    msg_header: Struct[RTMA_MSG_HEADER] = Struct(RTMA_MSG_HEADER)


@pyrtma.message_def
class MDF_CONNECT(MessageData):
    _fields_ = [("_logger_status", ctypes.c_short), ("_daemon_status", ctypes.c_short)]
    type_id: ClassVar[int] = 13
    type_name: ClassVar[str] = "CONNECT"
    type_hash: ClassVar[int] = 0x6F2E3CA5
    type_source: ClassVar[str] = "core_defs/core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'CONNECT:\n  id: 13\n  fields:\n    logger_status: short\n    daemon_status: short'"

    logger_status: Int16 = Int16()
    daemon_status: Int16 = Int16()


@pyrtma.message_def
class MDF_DISCONNECT(MessageData):
    _fields_ = []
    type_id: ClassVar[int] = 14
    type_name: ClassVar[str] = "DISCONNECT"
    type_hash: ClassVar[int] = 0xD0126BF9
    type_source: ClassVar[str] = "core_defs/core_defs.yaml"
    type_def: ClassVar[str] = "'DISCONNECT:\n  id: 14\n  fields: null'"


@pyrtma.message_def
class MDF_SUBSCRIBE(MessageData):
    _fields_ = [("_msg_type", MSG_TYPE)]
    type_id: ClassVar[int] = 15
    type_name: ClassVar[str] = "SUBSCRIBE"
    type_hash: ClassVar[int] = 0xF5B437C8
    type_source: ClassVar[str] = "core_defs/core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'SUBSCRIBE:\n  id: 15\n  fields:\n    msg_type: MSG_TYPE'"

    msg_type: Int32 = Int32()


@pyrtma.message_def
class MDF_UNSUBSCRIBE(MessageData):
    _fields_ = [("_msg_type", MSG_TYPE)]
    type_id: ClassVar[int] = 16
    type_name: ClassVar[str] = "UNSUBSCRIBE"
    type_hash: ClassVar[int] = 0x193FB9E0
    type_source: ClassVar[str] = "core_defs/core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'UNSUBSCRIBE:\n  id: 16\n  fields:\n    msg_type: MSG_TYPE'"

    msg_type: Int32 = Int32()


@pyrtma.message_def
class MDF_MODULE_READY(MessageData):
    _fields_ = [("_pid", ctypes.c_int)]
    type_id: ClassVar[int] = 26
    type_name: ClassVar[str] = "MODULE_READY"
    type_hash: ClassVar[int] = 0x0DF81813
    type_source: ClassVar[str] = "core_defs/core_defs.yaml"
    type_def: ClassVar[str] = "'MODULE_READY:\n  id: 26\n  fields:\n    pid: int'"

    pid: Int32 = Int32()


@pyrtma.message_def
class MDF_LM_EXIT(MessageData):
    _fields_ = []
    type_id: ClassVar[int] = 55
    type_name: ClassVar[str] = "LM_EXIT"
    type_hash: ClassVar[int] = 0x35DD547B
    type_source: ClassVar[str] = "core_defs/core_defs.yaml"
    type_def: ClassVar[str] = "'LM_EXIT:\n  id: 55\n  fields: null'"


@pyrtma.message_def
class MDF_SAVE_MESSAGE_LOG(MessageData):
    _fields_ = [("_pathname", ctypes.c_char * 256), ("_pathname_length", ctypes.c_int)]
    type_id: ClassVar[int] = 56
    type_name: ClassVar[str] = "SAVE_MESSAGE_LOG"
    type_hash: ClassVar[int] = 0x515569E9
    type_source: ClassVar[str] = "core_defs/core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'SAVE_MESSAGE_LOG:\n  id: 56\n  fields:\n    pathname: char[MAX_LOGGER_FILENAME_LENGTH]\n    pathname_length: int'"

    pathname: String = String(256)
    pathname_length: Int32 = Int32()


@pyrtma.message_def
class MDF_MESSAGE_LOG_SAVED(MessageData):
    _fields_ = []
    type_id: ClassVar[int] = 57
    type_name: ClassVar[str] = "MESSAGE_LOG_SAVED"
    type_hash: ClassVar[int] = 0x66E84AE5
    type_source: ClassVar[str] = "core_defs/core_defs.yaml"
    type_def: ClassVar[str] = "'MESSAGE_LOG_SAVED:\n  id: 57\n  fields: null'"


@pyrtma.message_def
class MDF_PAUSE_MESSAGE_LOGGING(MessageData):
    _fields_ = []
    type_id: ClassVar[int] = 58
    type_name: ClassVar[str] = "PAUSE_MESSAGE_LOGGING"
    type_hash: ClassVar[int] = 0x20C1E922
    type_source: ClassVar[str] = "core_defs/core_defs.yaml"
    type_def: ClassVar[str] = "'PAUSE_MESSAGE_LOGGING:\n  id: 58\n  fields: null'"


@pyrtma.message_def
class MDF_RESUME_MESSAGE_LOGGING(MessageData):
    _fields_ = []
    type_id: ClassVar[int] = 59
    type_name: ClassVar[str] = "RESUME_MESSAGE_LOGGING"
    type_hash: ClassVar[int] = 0x0D1A3E77
    type_source: ClassVar[str] = "core_defs/core_defs.yaml"
    type_def: ClassVar[str] = "'RESUME_MESSAGE_LOGGING:\n  id: 59\n  fields: null'"


@pyrtma.message_def
class MDF_RESET_MESSAGE_LOG(MessageData):
    _fields_ = []
    type_id: ClassVar[int] = 60
    type_name: ClassVar[str] = "RESET_MESSAGE_LOG"
    type_hash: ClassVar[int] = 0x68EC4AAB
    type_source: ClassVar[str] = "core_defs/core_defs.yaml"
    type_def: ClassVar[str] = "'RESET_MESSAGE_LOG:\n  id: 60\n  fields: null'"


@pyrtma.message_def
class MDF_DUMP_MESSAGE_LOG(MessageData):
    _fields_ = []
    type_id: ClassVar[int] = 61
    type_name: ClassVar[str] = "DUMP_MESSAGE_LOG"
    type_hash: ClassVar[int] = 0xF9D7E2BF
    type_source: ClassVar[str] = "core_defs/core_defs.yaml"
    type_def: ClassVar[str] = "'DUMP_MESSAGE_LOG:\n  id: 61\n  fields: null'"


@pyrtma.message_def
class MDF_TIMING_MESSAGE(MessageData):
    _fields_ = [
        ("_timing", ctypes.c_ushort * 10000),
        ("_ModulePID", ctypes.c_int * 200),
        ("_send_time", ctypes.c_double),
    ]
    type_id: ClassVar[int] = 80
    type_name: ClassVar[str] = "TIMING_MESSAGE"
    type_hash: ClassVar[int] = 0x3595C23E
    type_source: ClassVar[str] = "core_defs/core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'TIMING_MESSAGE:\n  id: 80\n  fields:\n    timing: unsigned short[MAX_MESSAGE_TYPES]\n    ModulePID: int[MAX_MODULES]\n    send_time: double'"

    timing: IntArray[Uint16] = IntArray(Uint16, 10000)
    ModulePID: IntArray[Int32] = IntArray(Int32, 200)
    send_time: Double = Double()


@pyrtma.message_def
class MDF_FORCE_DISCONNECT(MessageData):
    _fields_ = [("_mod_id", ctypes.c_int)]
    type_id: ClassVar[int] = 82
    type_name: ClassVar[str] = "FORCE_DISCONNECT"
    type_hash: ClassVar[int] = 0xC37C54E8
    type_source: ClassVar[str] = "core_defs/core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'FORCE_DISCONNECT:\n  id: 82\n  fields:\n    mod_id: int'"

    mod_id: Int32 = Int32()


@pyrtma.message_def
class MDF_PAUSE_SUBSCRIPTION(MessageData):
    _fields_ = [("_msg_type", MSG_TYPE)]
    type_id: ClassVar[int] = 85
    type_name: ClassVar[str] = "PAUSE_SUBSCRIPTION"
    type_hash: ClassVar[int] = 0x22338A6D
    type_source: ClassVar[str] = "core_defs/core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'PAUSE_SUBSCRIPTION:\n  id: 85\n  fields:\n    msg_type: MSG_TYPE'"

    msg_type: Int32 = Int32()


@pyrtma.message_def
class MDF_RESUME_SUBSCRIPTION(MessageData):
    _fields_ = [("_msg_type", MSG_TYPE)]
    type_id: ClassVar[int] = 86
    type_name: ClassVar[str] = "RESUME_SUBSCRIPTION"
    type_hash: ClassVar[int] = 0xC56A97F2
    type_source: ClassVar[str] = "core_defs/core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'RESUME_SUBSCRIPTION:\n  id: 86\n  fields:\n    msg_type: MSG_TYPE'"

    msg_type: Int32 = Int32()


@pyrtma.message_def
class MDF_LM_READY(MessageData):
    _fields_ = []
    type_id: ClassVar[int] = 96
    type_name: ClassVar[str] = "LM_READY"
    type_hash: ClassVar[int] = 0x4863B960
    type_source: ClassVar[str] = "core_defs/core_defs.yaml"
    type_def: ClassVar[str] = "'LM_READY:\n  id: 96\n  fields: null'"


# Collect all info into one object
class _constants:
    MAX_MODULES = 200
    DYN_MOD_ID_START = 100
    MAX_HOSTS = 5
    MAX_MESSAGE_TYPES = 10000
    MIN_STREAM_TYPE = 9000
    MAX_TIMERS = 100
    MAX_INTERNAL_TIMERS = 20
    MAX_RTMA_MSG_TYPE = 99
    MAX_RTMA_MODULE_ID = 9
    MAX_LOGGER_FILENAME_LENGTH = 256
    MAX_CONTIGUOUS_MESSAGE_DATA = 9000
    ALL_MESSAGE_TYPES = 2147483647


class _HID:
    LOCAL_HOST = 0
    ALL_HOSTS = 32767


class _MID:
    MESSAGE_MANAGER = 0
    QUICK_LOGGER = 5


class _aliases:
    MODULE_ID = MODULE_ID
    HOST_ID = HOST_ID
    MSG_TYPE = MSG_TYPE
    MSG_COUNT = MSG_COUNT


class _SDF:
    RTMA_MSG_HEADER = RTMA_MSG_HEADER


class _MT:
    EXIT = 0
    KILL = 1
    ACKNOWLEDGE = 2
    FAIL_SUBSCRIBE = 6
    FAILED_MESSAGE = 8
    CONNECT = 13
    DISCONNECT = 14
    SUBSCRIBE = 15
    UNSUBSCRIBE = 16
    MODULE_READY = 26
    LM_EXIT = 55
    SAVE_MESSAGE_LOG = 56
    MESSAGE_LOG_SAVED = 57
    PAUSE_MESSAGE_LOGGING = 58
    RESUME_MESSAGE_LOGGING = 59
    RESET_MESSAGE_LOG = 60
    DUMP_MESSAGE_LOG = 61
    TIMING_MESSAGE = 80
    FORCE_DISCONNECT = 82
    PAUSE_SUBSCRIPTION = 85
    RESUME_SUBSCRIPTION = 86
    LM_READY = 96


class _MDF:
    EXIT = MDF_EXIT
    KILL = MDF_KILL
    ACKNOWLEDGE = MDF_ACKNOWLEDGE
    FAIL_SUBSCRIBE = MDF_FAIL_SUBSCRIBE
    FAILED_MESSAGE = MDF_FAILED_MESSAGE
    CONNECT = MDF_CONNECT
    DISCONNECT = MDF_DISCONNECT
    SUBSCRIBE = MDF_SUBSCRIBE
    UNSUBSCRIBE = MDF_UNSUBSCRIBE
    MODULE_READY = MDF_MODULE_READY
    LM_EXIT = MDF_LM_EXIT
    SAVE_MESSAGE_LOG = MDF_SAVE_MESSAGE_LOG
    MESSAGE_LOG_SAVED = MDF_MESSAGE_LOG_SAVED
    PAUSE_MESSAGE_LOGGING = MDF_PAUSE_MESSAGE_LOGGING
    RESUME_MESSAGE_LOGGING = MDF_RESUME_MESSAGE_LOGGING
    RESET_MESSAGE_LOG = MDF_RESET_MESSAGE_LOG
    DUMP_MESSAGE_LOG = MDF_DUMP_MESSAGE_LOG
    TIMING_MESSAGE = MDF_TIMING_MESSAGE
    FORCE_DISCONNECT = MDF_FORCE_DISCONNECT
    PAUSE_SUBSCRIPTION = MDF_PAUSE_SUBSCRIPTION
    RESUME_SUBSCRIPTION = MDF_RESUME_SUBSCRIPTION
    LM_READY = MDF_LM_READY


class _RTMA:
    constants = _constants
    HID = _HID
    MID = _MID
    aliases = _aliases
    MT = _MT
    MDF = _MDF
    SDF = _SDF


RTMA: _RTMA = _RTMA()
