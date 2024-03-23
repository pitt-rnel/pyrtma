"""This message def file was auto-generated by pyrtma.compile version 2.2.2"""
import ctypes

import pyrtma
from pyrtma.__version__ import check_compiled_version
from typing import ClassVar, Dict, Any

from pyrtma.message_base import MessageBase, MessageMeta
from pyrtma.message_data import MessageData
from pyrtma.context import update_context, get_context
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
    Char,
    String,
    Byte,
    ByteArray,
)


COMPILED_PYRTMA_VERSION: str = "2.2.2"
check_compiled_version(COMPILED_PYRTMA_VERSION)

# Constants
MAX_DATA_SETS: int = 6
MAX_LOGGER_FILENAME_LENGTH: int = 256
MAX_MODULES: int = 200
DYN_MOD_ID_START: int = 100
MAX_HOSTS: int = 5
MAX_MESSAGE_TYPES: int = 10000
MIN_STREAM_TYPE: int = 9000
MAX_TIMERS: int = 100
MAX_INTERNAL_TIMERS: int = 20
MAX_RTMA_MSG_TYPE: int = 99
MAX_RTMA_MODULE_ID: int = 9
MAX_CONTIGUOUS_MESSAGE_DATA: int = 9000
ALL_MESSAGE_TYPES: int = 2147483647
MAX_CLIENTS: int = 256
MAX_SUBSCRIBERS: int = 256
MAX_SUBS: int = 256
MAX_NAME_LEN: int = 32
MAX_LOG_LENGTH: int = 1024
MESSAGE_TRAFFIC_SIZE: int = 64
MAX_MESSAGE_SIZE: int = 65535

# String Constants

# Type Aliases
MODULE_ID = ctypes.c_int16
HOST_ID = ctypes.c_int16
MSG_TYPE = ctypes.c_int32
MSG_COUNT = ctypes.c_int32

# Host IDs
LOCAL_HOST: int = 0
ALL_HOSTS: int = 32767

# Module IDs
MID_MESSAGE_MANAGER: int = 0
MID_DATA_LOGGER: int = 4
MID_QUICK_LOGGER: int = 5

# Message Type IDs
MT_DATA_LOGGER_STATUS: int = 62
MT_DATA_LOGGER_STATUS_REQUEST: int = 63
MT_ADD_DATA_COLLECTION: int = 64
MT_REMOVE_DATA_COLLECTION: int = 65
MT_ADD_DATA_SET: int = 66
MT_REMOVE_DATA_SET: int = 67
MT_DATA_COLLECTION_CONFIG_REQUEST: int = 68
MT_DATA_COLLECTION_CONFIG: int = 69
MT_DATA_COLLECTION_STARTED: int = 70
MT_DATA_COLLECTION_STOPPED: int = 71
MT_DATA_COLLECTION_SAVED: int = 72
MT_DATA_LOGGER_START: int = 73
MT_DATA_LOGGER_STOP: int = 74
MT_DATA_LOGGER_PAUSE: int = 75
MT_DATA_LOGGER_RESUME: int = 76
MT_DATA_LOGGER_RESET: int = 77
MT_DATA_LOGGER_ERROR: int = 78
MT_DATA_LOGGER_METADATA_UPDATE: int = 79
MT_DATA_LOGGER_METADATA_REQUEST: int = 87
MT_DATA_LOGGER_METADATA: int = 88
MT_DATA_LOG_TEST_2048: int = 89
MT_LM_READY: int = 96
MT_LM_STATUS: int = 54
MT_LM_EXIT: int = 55
MT_SAVE_MESSAGE_LOG: int = 56
MT_MESSAGE_LOG_SAVED: int = 57
MT_PAUSE_MESSAGE_LOGGING: int = 58
MT_RESUME_MESSAGE_LOGGING: int = 59
MT_RESET_MESSAGE_LOG: int = 60
MT_DUMP_MESSAGE_LOG: int = 61
MT_EXIT: int = 0
MT_KILL: int = 1
MT_ACKNOWLEDGE: int = 2
MT_FAIL_SUBSCRIBE: int = 6
MT_FAILED_MESSAGE: int = 8
MT_CONNECT: int = 13
MT_CONNECT_V2: int = 4
MT_DISCONNECT: int = 14
MT_SUBSCRIBE: int = 15
MT_UNSUBSCRIBE: int = 16
MT_MODULE_READY: int = 26
MT_TIMING_MESSAGE: int = 80
MT_FORCE_DISCONNECT: int = 82
MT_PAUSE_SUBSCRIPTION: int = 85
MT_RESUME_SUBSCRIPTION: int = 86
MT_MM_LOG: int = 29
MT_MESSAGE_TRAFFIC: int = 30
MT_ACTIVE_CLIENTS: int = 31
MT_CLIENT_INFO: int = 32
MT_CLIENT_CLOSED: int = 33
MT_CLIENT_SET_NAME: int = 34
MT_RTMA_LOG: int = 40
MT_RTMA_LOG_CRITICAL: int = 41
MT_RTMA_LOG_ERROR: int = 42
MT_RTMA_LOG_WARNING: int = 43
MT_RTMA_LOG_INFO: int = 44
MT_RTMA_LOG_DEBUG: int = 45


# Struct Definitions
class DATA_SET(MessageBase, metaclass=MessageMeta):
    type_name: ClassVar[str] = "DATA_SET"
    type_hash: ClassVar[int] = 0xB267DE7B
    type_size: ClassVar[int] = 452
    type_source: ClassVar[str] = "data_logger.yaml"
    type_def: ClassVar[
        str
    ] = "'DATA_SET:\n  fields:\n    name: char[32]\n    sub_dir_fmt: char[128]\n    file_name_fmt: char[128]\n    formatter: char[32]\n    subdivide_interval: int32\n    msg_types: int32[32]'"

    name: String = String(32)
    sub_dir_fmt: String = String(128)
    file_name_fmt: String = String(128)
    formatter: String = String(32)
    subdivide_interval: Int32 = Int32()
    msg_types: IntArray[Int32] = IntArray(Int32, 32)


class DATA_COLLECTION(MessageBase, metaclass=MessageMeta):
    type_name: ClassVar[str] = "DATA_COLLECTION"
    type_hash: ClassVar[int] = 0x9FA9C51A
    type_size: ClassVar[int] = 3132
    type_source: ClassVar[str] = "data_logger.yaml"
    type_def: ClassVar[
        str
    ] = "'DATA_COLLECTION:\n  fields:\n    name: char[32]\n    base_path: char[256]\n    dir_fmt: char[128]\n    num_data_sets: int16\n    unused: int16\n    data_sets: DATA_SET[MAX_DATA_SETS]'"

    name: String = String(32)
    base_path: String = String(256)
    dir_fmt: String = String(128)
    num_data_sets: Int16 = Int16()
    unused: Int16 = Int16()
    data_sets: StructArray[DATA_SET] = StructArray(DATA_SET, 6)


class DATA_SET_INFO(MessageBase, metaclass=MessageMeta):
    type_name: ClassVar[str] = "DATA_SET_INFO"
    type_hash: ClassVar[int] = 0x65972A16
    type_size: ClassVar[int] = 452
    type_source: ClassVar[str] = "data_logger.yaml"
    type_def: ClassVar[
        str
    ] = "'DATA_SET_INFO:\n  fields:\n    name: char[32]\n    formatter: char[32]\n    save_path: char[256]\n    subdivide_interval: int32\n    msg_types: int32[32]'"

    name: String = String(32)
    formatter: String = String(32)
    save_path: String = String(256)
    subdivide_interval: Int32 = Int32()
    msg_types: IntArray[Int32] = IntArray(Int32, 32)


class DATA_COLLECTION_INFO(MessageBase, metaclass=MessageMeta):
    type_name: ClassVar[str] = "DATA_COLLECTION_INFO"
    type_hash: ClassVar[int] = 0x8FAF0CA3
    type_size: ClassVar[int] = 3004
    type_source: ClassVar[str] = "data_logger.yaml"
    type_def: ClassVar[
        str
    ] = "'DATA_COLLECTION_INFO:\n  fields:\n    name: char[32]\n    save_path: char[256]\n    num_data_sets: int16\n    unused: int16\n    data_sets: DATA_SET_INFO[MAX_DATA_SETS]'"

    name: String = String(32)
    save_path: String = String(256)
    num_data_sets: Int16 = Int16()
    unused: Int16 = Int16()
    data_sets: StructArray[DATA_SET_INFO] = StructArray(DATA_SET_INFO, 6)


class RTMA_MSG_HEADER(MessageBase, metaclass=MessageMeta):
    type_name: ClassVar[str] = "RTMA_MSG_HEADER"
    type_hash: ClassVar[int] = 0x35CC5A39
    type_size: ClassVar[int] = 48
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'RTMA_MSG_HEADER:\n  fields:\n    msg_type: MSG_TYPE\n    msg_count: MSG_COUNT\n    send_time: double\n    recv_time: double\n    src_host_id: HOST_ID\n    src_mod_id: MODULE_ID\n    dest_host_id: HOST_ID\n    dest_mod_id: MODULE_ID\n    num_data_bytes: int32\n    remaining_bytes: int32\n    is_dynamic: int32\n    reserved: uint32'"

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
class MDF_DATA_LOGGER_STATUS(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 62
    type_name: ClassVar[str] = "DATA_LOGGER_STATUS"
    type_hash: ClassVar[int] = 0x9E922E93
    type_size: ClassVar[int] = 24
    type_source: ClassVar[str] = "data_logger.yaml"
    type_def: ClassVar[
        str
    ] = "'DATA_LOGGER_STATUS:\n  id: 62\n  fields:\n    timestamp: double\n    elapsed_time: double\n    is_recording: int32\n    is_paused: int32'"

    timestamp: Double = Double()
    elapsed_time: Double = Double()
    is_recording: Int32 = Int32()
    is_paused: Int32 = Int32()


@pyrtma.message_def
class MDF_DATA_LOGGER_STATUS_REQUEST(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 63
    type_name: ClassVar[str] = "DATA_LOGGER_STATUS_REQUEST"
    type_hash: ClassVar[int] = 0x168B0652
    type_size: ClassVar[int] = 0
    type_source: ClassVar[str] = "data_logger.yaml"
    type_def: ClassVar[str] = "'DATA_LOGGER_STATUS_REQUEST:\n  id: 63\n  fields: null'"


@pyrtma.message_def
class MDF_ADD_DATA_COLLECTION(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 64
    type_name: ClassVar[str] = "ADD_DATA_COLLECTION"
    type_hash: ClassVar[int] = 0xA50C4BC8
    type_size: ClassVar[int] = 3132
    type_source: ClassVar[str] = "data_logger.yaml"
    type_def: ClassVar[
        str
    ] = "'ADD_DATA_COLLECTION:\n  id: 64\n  fields:\n    collection: DATA_COLLECTION'"

    collection: Struct[DATA_COLLECTION] = Struct(DATA_COLLECTION)


@pyrtma.message_def
class MDF_REMOVE_DATA_COLLECTION(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 65
    type_name: ClassVar[str] = "REMOVE_DATA_COLLECTION"
    type_hash: ClassVar[int] = 0x5430DCF2
    type_size: ClassVar[int] = 32
    type_source: ClassVar[str] = "data_logger.yaml"
    type_def: ClassVar[
        str
    ] = "'REMOVE_DATA_COLLECTION:\n  id: 65\n  fields:\n    collection_name: char[32]'"

    collection_name: String = String(32)


@pyrtma.message_def
class MDF_ADD_DATA_SET(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 66
    type_name: ClassVar[str] = "ADD_DATA_SET"
    type_hash: ClassVar[int] = 0xB368D74F
    type_size: ClassVar[int] = 484
    type_source: ClassVar[str] = "data_logger.yaml"
    type_def: ClassVar[
        str
    ] = "'ADD_DATA_SET:\n  id: 66\n  fields:\n    collection_name: char[32]\n    data_set: DATA_SET'"

    collection_name: String = String(32)
    data_set: Struct[DATA_SET] = Struct(DATA_SET)


@pyrtma.message_def
class MDF_REMOVE_DATA_SET(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 67
    type_name: ClassVar[str] = "REMOVE_DATA_SET"
    type_hash: ClassVar[int] = 0x0BC39C04
    type_size: ClassVar[int] = 64
    type_source: ClassVar[str] = "data_logger.yaml"
    type_def: ClassVar[
        str
    ] = "'REMOVE_DATA_SET:\n  id: 67\n  fields:\n    collection_name: char[32]\n    name: char[32]'"

    collection_name: String = String(32)
    name: String = String(32)


@pyrtma.message_def
class MDF_DATA_COLLECTION_CONFIG_REQUEST(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 68
    type_name: ClassVar[str] = "DATA_COLLECTION_CONFIG_REQUEST"
    type_hash: ClassVar[int] = 0x1779D826
    type_size: ClassVar[int] = 0
    type_source: ClassVar[str] = "data_logger.yaml"
    type_def: ClassVar[
        str
    ] = "'DATA_COLLECTION_CONFIG_REQUEST:\n  id: 68\n  fields: null'"


@pyrtma.message_def
class MDF_DATA_COLLECTION_CONFIG(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 69
    type_name: ClassVar[str] = "DATA_COLLECTION_CONFIG"
    type_hash: ClassVar[int] = 0xC08D3576
    type_size: ClassVar[int] = 3132
    type_source: ClassVar[str] = "data_logger.yaml"
    type_def: ClassVar[
        str
    ] = "'DATA_COLLECTION_CONFIG:\n  id: 69\n  fields:\n    collection: DATA_COLLECTION'"

    collection: Struct[DATA_COLLECTION] = Struct(DATA_COLLECTION)


@pyrtma.message_def
class MDF_DATA_COLLECTION_STARTED(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 70
    type_name: ClassVar[str] = "DATA_COLLECTION_STARTED"
    type_hash: ClassVar[int] = 0x415737CA
    type_size: ClassVar[int] = 3004
    type_source: ClassVar[str] = "data_logger.yaml"
    type_def: ClassVar[
        str
    ] = "'DATA_COLLECTION_STARTED:\n  id: 70\n  fields:\n    collection: DATA_COLLECTION_INFO'"

    collection: Struct[DATA_COLLECTION_INFO] = Struct(DATA_COLLECTION_INFO)


@pyrtma.message_def
class MDF_DATA_COLLECTION_STOPPED(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 71
    type_name: ClassVar[str] = "DATA_COLLECTION_STOPPED"
    type_hash: ClassVar[int] = 0xDA1AF3AE
    type_size: ClassVar[int] = 3004
    type_source: ClassVar[str] = "data_logger.yaml"
    type_def: ClassVar[
        str
    ] = "'DATA_COLLECTION_STOPPED:\n  id: 71\n  fields:\n    collection: DATA_COLLECTION_INFO'"

    collection: Struct[DATA_COLLECTION_INFO] = Struct(DATA_COLLECTION_INFO)


@pyrtma.message_def
class MDF_DATA_COLLECTION_SAVED(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 72
    type_name: ClassVar[str] = "DATA_COLLECTION_SAVED"
    type_hash: ClassVar[int] = 0x74528518
    type_size: ClassVar[int] = 0
    type_source: ClassVar[str] = "data_logger.yaml"
    type_def: ClassVar[str] = "'DATA_COLLECTION_SAVED:\n  id: 72\n  fields: null'"


@pyrtma.message_def
class MDF_DATA_LOGGER_START(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 73
    type_name: ClassVar[str] = "DATA_LOGGER_START"
    type_hash: ClassVar[int] = 0x982D6942
    type_size: ClassVar[int] = 0
    type_source: ClassVar[str] = "data_logger.yaml"
    type_def: ClassVar[str] = "'DATA_LOGGER_START:\n  id: 73\n  fields: null'"


@pyrtma.message_def
class MDF_DATA_LOGGER_STOP(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 74
    type_name: ClassVar[str] = "DATA_LOGGER_STOP"
    type_hash: ClassVar[int] = 0xA5B66B24
    type_size: ClassVar[int] = 0
    type_source: ClassVar[str] = "data_logger.yaml"
    type_def: ClassVar[str] = "'DATA_LOGGER_STOP:\n  id: 74\n  fields: null'"


@pyrtma.message_def
class MDF_DATA_LOGGER_PAUSE(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 75
    type_name: ClassVar[str] = "DATA_LOGGER_PAUSE"
    type_hash: ClassVar[int] = 0x9A556835
    type_size: ClassVar[int] = 0
    type_source: ClassVar[str] = "data_logger.yaml"
    type_def: ClassVar[str] = "'DATA_LOGGER_PAUSE:\n  id: 75\n  fields: null'"


@pyrtma.message_def
class MDF_DATA_LOGGER_RESUME(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 76
    type_name: ClassVar[str] = "DATA_LOGGER_RESUME"
    type_hash: ClassVar[int] = 0x18811751
    type_size: ClassVar[int] = 0
    type_source: ClassVar[str] = "data_logger.yaml"
    type_def: ClassVar[str] = "'DATA_LOGGER_RESUME:\n  id: 76\n  fields: null'"


@pyrtma.message_def
class MDF_DATA_LOGGER_RESET(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 77
    type_name: ClassVar[str] = "DATA_LOGGER_RESET"
    type_hash: ClassVar[int] = 0x1EB32BEB
    type_size: ClassVar[int] = 0
    type_source: ClassVar[str] = "data_logger.yaml"
    type_def: ClassVar[str] = "'DATA_LOGGER_RESET:\n  id: 77\n  fields: null'"


@pyrtma.message_def
class MDF_DATA_LOGGER_ERROR(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 78
    type_name: ClassVar[str] = "DATA_LOGGER_ERROR"
    type_hash: ClassVar[int] = 0xAD3B4A67
    type_size: ClassVar[int] = 512
    type_source: ClassVar[str] = "data_logger.yaml"
    type_def: ClassVar[
        str
    ] = "'DATA_LOGGER_ERROR:\n  id: 78\n  fields:\n    msg: char[512]'"

    msg: String = String(512)


@pyrtma.message_def
class MDF_DATA_LOGGER_METADATA_UPDATE(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 79
    type_name: ClassVar[str] = "DATA_LOGGER_METADATA_UPDATE"
    type_hash: ClassVar[int] = 0x3C673526
    type_size: ClassVar[int] = 512
    type_source: ClassVar[str] = "data_logger.yaml"
    type_def: ClassVar[
        str
    ] = "'DATA_LOGGER_METADATA_UPDATE:\n  id: 79\n  fields:\n    json: char[512]'"

    json: String = String(512)


@pyrtma.message_def
class MDF_DATA_LOGGER_METADATA_REQUEST(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 87
    type_name: ClassVar[str] = "DATA_LOGGER_METADATA_REQUEST"
    type_hash: ClassVar[int] = 0x2D068003
    type_size: ClassVar[int] = 0
    type_source: ClassVar[str] = "data_logger.yaml"
    type_def: ClassVar[
        str
    ] = "'DATA_LOGGER_METADATA_REQUEST:\n  id: 87\n  fields: null'"


@pyrtma.message_def
class MDF_DATA_LOGGER_METADATA(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 88
    type_name: ClassVar[str] = "DATA_LOGGER_METADATA"
    type_hash: ClassVar[int] = 0x3852789B
    type_size: ClassVar[int] = 1024
    type_source: ClassVar[str] = "data_logger.yaml"
    type_def: ClassVar[
        str
    ] = "'DATA_LOGGER_METADATA:\n  id: 88\n  fields:\n    json: char[1024]'"

    json: String = String(1024)


@pyrtma.message_def
class MDF_DATA_LOG_TEST_2048(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 89
    type_name: ClassVar[str] = "DATA_LOG_TEST_2048"
    type_hash: ClassVar[int] = 0x651D3C98
    type_size: ClassVar[int] = 2048
    type_source: ClassVar[str] = "data_logger.yaml"
    type_def: ClassVar[
        str
    ] = "'DATA_LOG_TEST_2048:\n  id: 89\n  fields:\n    raw: char[2048]'"

    raw: String = String(2048)


@pyrtma.message_def
class MDF_LM_READY(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 96
    type_name: ClassVar[str] = "LM_READY"
    type_hash: ClassVar[int] = 0x4863B960
    type_size: ClassVar[int] = 0
    type_source: ClassVar[str] = "quick_logger.yaml"
    type_def: ClassVar[str] = "'LM_READY:\n  id: 96\n  fields: null'"


@pyrtma.message_def
class MDF_LM_STATUS(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 54
    type_name: ClassVar[str] = "LM_STATUS"
    type_hash: ClassVar[int] = 0x2DA5B6A1
    type_size: ClassVar[int] = 32
    type_source: ClassVar[str] = "quick_logger.yaml"
    type_def: ClassVar[
        str
    ] = "'LM_STATUS:\n  id: 54\n  fields:\n    is_logging: uint32\n    max_msgs: uint32\n    hdr_bufsz: uint32\n    data_bufsz: uint32\n    msg_count: uint32\n    hdr_total: uint32\n    data_total: uint32\n    ofs_total: uint32'"

    is_logging: Uint32 = Uint32()
    max_msgs: Uint32 = Uint32()
    hdr_bufsz: Uint32 = Uint32()
    data_bufsz: Uint32 = Uint32()
    msg_count: Uint32 = Uint32()
    hdr_total: Uint32 = Uint32()
    data_total: Uint32 = Uint32()
    ofs_total: Uint32 = Uint32()


@pyrtma.message_def
class MDF_LM_EXIT(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 55
    type_name: ClassVar[str] = "LM_EXIT"
    type_hash: ClassVar[int] = 0x35DD547B
    type_size: ClassVar[int] = 0
    type_source: ClassVar[str] = "quick_logger.yaml"
    type_def: ClassVar[str] = "'LM_EXIT:\n  id: 55\n  fields: null'"


@pyrtma.message_def
class MDF_SAVE_MESSAGE_LOG(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 56
    type_name: ClassVar[str] = "SAVE_MESSAGE_LOG"
    type_hash: ClassVar[int] = 0x515569E9
    type_size: ClassVar[int] = 260
    type_source: ClassVar[str] = "quick_logger.yaml"
    type_def: ClassVar[
        str
    ] = "'SAVE_MESSAGE_LOG:\n  id: 56\n  fields:\n    pathname: char[MAX_LOGGER_FILENAME_LENGTH]\n    pathname_length: int'"

    pathname: String = String(256)
    pathname_length: Int32 = Int32()


@pyrtma.message_def
class MDF_MESSAGE_LOG_SAVED(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 57
    type_name: ClassVar[str] = "MESSAGE_LOG_SAVED"
    type_hash: ClassVar[int] = 0x66E84AE5
    type_size: ClassVar[int] = 0
    type_source: ClassVar[str] = "quick_logger.yaml"
    type_def: ClassVar[str] = "'MESSAGE_LOG_SAVED:\n  id: 57\n  fields: null'"


@pyrtma.message_def
class MDF_PAUSE_MESSAGE_LOGGING(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 58
    type_name: ClassVar[str] = "PAUSE_MESSAGE_LOGGING"
    type_hash: ClassVar[int] = 0x20C1E922
    type_size: ClassVar[int] = 0
    type_source: ClassVar[str] = "quick_logger.yaml"
    type_def: ClassVar[str] = "'PAUSE_MESSAGE_LOGGING:\n  id: 58\n  fields: null'"


@pyrtma.message_def
class MDF_RESUME_MESSAGE_LOGGING(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 59
    type_name: ClassVar[str] = "RESUME_MESSAGE_LOGGING"
    type_hash: ClassVar[int] = 0x0D1A3E77
    type_size: ClassVar[int] = 0
    type_source: ClassVar[str] = "quick_logger.yaml"
    type_def: ClassVar[str] = "'RESUME_MESSAGE_LOGGING:\n  id: 59\n  fields: null'"


@pyrtma.message_def
class MDF_RESET_MESSAGE_LOG(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 60
    type_name: ClassVar[str] = "RESET_MESSAGE_LOG"
    type_hash: ClassVar[int] = 0x68EC4AAB
    type_size: ClassVar[int] = 0
    type_source: ClassVar[str] = "quick_logger.yaml"
    type_def: ClassVar[str] = "'RESET_MESSAGE_LOG:\n  id: 60\n  fields: null'"


@pyrtma.message_def
class MDF_DUMP_MESSAGE_LOG(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 61
    type_name: ClassVar[str] = "DUMP_MESSAGE_LOG"
    type_hash: ClassVar[int] = 0xF9D7E2BF
    type_size: ClassVar[int] = 0
    type_source: ClassVar[str] = "quick_logger.yaml"
    type_def: ClassVar[str] = "'DUMP_MESSAGE_LOG:\n  id: 61\n  fields: null'"


@pyrtma.message_def
class MDF_EXIT(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 0
    type_name: ClassVar[str] = "EXIT"
    type_hash: ClassVar[int] = 0x095E0546
    type_size: ClassVar[int] = 0
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[str] = "'EXIT:\n  id: 0\n  fields: null'"


@pyrtma.message_def
class MDF_KILL(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 1
    type_name: ClassVar[str] = "KILL"
    type_hash: ClassVar[int] = 0x82FC702D
    type_size: ClassVar[int] = 0
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[str] = "'KILL:\n  id: 1\n  fields: null'"


@pyrtma.message_def
class MDF_ACKNOWLEDGE(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 2
    type_name: ClassVar[str] = "ACKNOWLEDGE"
    type_hash: ClassVar[int] = 0xB725B581
    type_size: ClassVar[int] = 0
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[str] = "'ACKNOWLEDGE:\n  id: 2\n  fields: null'"


@pyrtma.message_def
class MDF_FAIL_SUBSCRIBE(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 6
    type_name: ClassVar[str] = "FAIL_SUBSCRIBE"
    type_hash: ClassVar[int] = 0x694BF3DB
    type_size: ClassVar[int] = 8
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'FAIL_SUBSCRIBE:\n  id: 6\n  fields:\n    mod_id: MODULE_ID\n    reserved: int16\n    msg_type: MSG_TYPE'"

    mod_id: Int16 = Int16()
    reserved: Int16 = Int16()
    msg_type: Int32 = Int32()


@pyrtma.message_def
class MDF_FAILED_MESSAGE(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 8
    type_name: ClassVar[str] = "FAILED_MESSAGE"
    type_hash: ClassVar[int] = 0x4EAFB837
    type_size: ClassVar[int] = 64
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'FAILED_MESSAGE:\n  id: 8\n  fields:\n    dest_mod_id: MODULE_ID\n    reserved: int16[3]\n    time_of_failure: double\n    msg_header: RTMA_MSG_HEADER'"

    dest_mod_id: Int16 = Int16()
    reserved: IntArray[Int16] = IntArray(Int16, 3)
    time_of_failure: Double = Double()
    msg_header: Struct[RTMA_MSG_HEADER] = Struct(RTMA_MSG_HEADER)


@pyrtma.message_def
class MDF_CONNECT(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 13
    type_name: ClassVar[str] = "CONNECT"
    type_hash: ClassVar[int] = 0xF4FDCFF3
    type_size: ClassVar[int] = 4
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'CONNECT:\n  id: 13\n  fields:\n    logger_status: int16\n    daemon_status: int16'"

    logger_status: Int16 = Int16()
    daemon_status: Int16 = Int16()


@pyrtma.message_def
class MDF_CONNECT_V2(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 4
    type_name: ClassVar[str] = "CONNECT_V2"
    type_hash: ClassVar[int] = 0xE1B49C8A
    type_size: ClassVar[int] = 44
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'CONNECT_V2:\n  id: 4\n  fields:\n    logger_status: int16\n    allow_multiple: int16\n    pad: int16\n    mod_id: MODULE_ID\n    pid: int32\n    name: char[MAX_NAME_LEN]'"

    logger_status: Int16 = Int16()
    allow_multiple: Int16 = Int16()
    pad: Int16 = Int16()
    mod_id: Int16 = Int16()
    pid: Int32 = Int32()
    name: String = String(32)


@pyrtma.message_def
class MDF_DISCONNECT(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 14
    type_name: ClassVar[str] = "DISCONNECT"
    type_hash: ClassVar[int] = 0xD0126BF9
    type_size: ClassVar[int] = 0
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[str] = "'DISCONNECT:\n  id: 14\n  fields: null'"


@pyrtma.message_def
class MDF_SUBSCRIBE(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 15
    type_name: ClassVar[str] = "SUBSCRIBE"
    type_hash: ClassVar[int] = 0xF5B437C8
    type_size: ClassVar[int] = 4
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'SUBSCRIBE:\n  id: 15\n  fields:\n    msg_type: MSG_TYPE'"

    msg_type: Int32 = Int32()


@pyrtma.message_def
class MDF_UNSUBSCRIBE(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 16
    type_name: ClassVar[str] = "UNSUBSCRIBE"
    type_hash: ClassVar[int] = 0x193FB9E0
    type_size: ClassVar[int] = 4
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'UNSUBSCRIBE:\n  id: 16\n  fields:\n    msg_type: MSG_TYPE'"

    msg_type: Int32 = Int32()


@pyrtma.message_def
class MDF_MODULE_READY(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 26
    type_name: ClassVar[str] = "MODULE_READY"
    type_hash: ClassVar[int] = 0xFD0E0311
    type_size: ClassVar[int] = 4
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[str] = "'MODULE_READY:\n  id: 26\n  fields:\n    pid: int32'"

    pid: Int32 = Int32()


@pyrtma.message_def
class MDF_TIMING_MESSAGE(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 80
    type_name: ClassVar[str] = "TIMING_MESSAGE"
    type_hash: ClassVar[int] = 0x3595C23E
    type_size: ClassVar[int] = 20808
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'TIMING_MESSAGE:\n  id: 80\n  fields:\n    timing: unsigned short[MAX_MESSAGE_TYPES]\n    ModulePID: int[MAX_MODULES]\n    send_time: double'"

    timing: IntArray[Uint16] = IntArray(Uint16, 10000)
    ModulePID: IntArray[Int32] = IntArray(Int32, 200)
    send_time: Double = Double()


@pyrtma.message_def
class MDF_FORCE_DISCONNECT(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 82
    type_name: ClassVar[str] = "FORCE_DISCONNECT"
    type_hash: ClassVar[int] = 0x335C7BBF
    type_size: ClassVar[int] = 4
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'FORCE_DISCONNECT:\n  id: 82\n  fields:\n    mod_id: int32'"

    mod_id: Int32 = Int32()


@pyrtma.message_def
class MDF_PAUSE_SUBSCRIPTION(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 85
    type_name: ClassVar[str] = "PAUSE_SUBSCRIPTION"
    type_hash: ClassVar[int] = 0x22338A6D
    type_size: ClassVar[int] = 4
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'PAUSE_SUBSCRIPTION:\n  id: 85\n  fields:\n    msg_type: MSG_TYPE'"

    msg_type: Int32 = Int32()


@pyrtma.message_def
class MDF_RESUME_SUBSCRIPTION(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 86
    type_name: ClassVar[str] = "RESUME_SUBSCRIPTION"
    type_hash: ClassVar[int] = 0xC56A97F2
    type_size: ClassVar[int] = 4
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'RESUME_SUBSCRIPTION:\n  id: 86\n  fields:\n    msg_type: MSG_TYPE'"

    msg_type: Int32 = Int32()


@pyrtma.message_def
class MDF_MM_LOG(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 29
    type_name: ClassVar[str] = "MM_LOG"
    type_hash: ClassVar[int] = 0xF4225C93
    type_size: ClassVar[int] = 264
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'MM_LOG:\n  id: 29\n  fields:\n    level: int32\n    pad: int32\n    message: char[256]'"

    level: Int32 = Int32()
    pad: Int32 = Int32()
    message: String = String(256)


@pyrtma.message_def
class MDF_MESSAGE_TRAFFIC(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 30
    type_name: ClassVar[str] = "MESSAGE_TRAFFIC"
    type_hash: ClassVar[int] = 0xA5D05FF5
    type_size: ClassVar[int] = 408
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'MESSAGE_TRAFFIC:\n  id: 30\n  fields:\n    seqno: uint32\n    sub_seqno: uint32\n    start_timestamp: double\n    end_timestamp: double\n    msg_type: MSG_TYPE[MESSAGE_TRAFFIC_SIZE]\n    msg_count: uint16[MESSAGE_TRAFFIC_SIZE]'"

    seqno: Uint32 = Uint32()
    sub_seqno: Uint32 = Uint32()
    start_timestamp: Double = Double()
    end_timestamp: Double = Double()
    msg_type: IntArray[Int32] = IntArray(Int32, 64)
    msg_count: IntArray[Uint16] = IntArray(Uint16, 64)


@pyrtma.message_def
class MDF_ACTIVE_CLIENTS(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 31
    type_name: ClassVar[str] = "ACTIVE_CLIENTS"
    type_hash: ClassVar[int] = 0xC203F18C
    type_size: ClassVar[int] = 1552
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'ACTIVE_CLIENTS:\n  id: 31\n  fields:\n    timestamp: double\n    num_clients: int16\n    padding: int16\n    reserved: int32\n    client_mod_id: MODULE_ID[MAX_CLIENTS]\n    client_pid: int32[MAX_CLIENTS]'"

    timestamp: Double = Double()
    num_clients: Int16 = Int16()
    padding: Int16 = Int16()
    reserved: Int32 = Int32()
    client_mod_id: IntArray[Int16] = IntArray(Int16, 256)
    client_pid: IntArray[Int32] = IntArray(Int32, 256)


@pyrtma.message_def
class MDF_CLIENT_INFO(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 32
    type_name: ClassVar[str] = "CLIENT_INFO"
    type_hash: ClassVar[int] = 0x401076E7
    type_size: ClassVar[int] = 80
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'CLIENT_INFO:\n  id: 32\n  fields:\n    addr: char[32]\n    uid: int32\n    pid: int32\n    mod_id: MODULE_ID\n    is_logger: int16\n    is_unique: int16\n    port: uint16\n    name: char[MAX_NAME_LEN]'"

    addr: String = String(32)
    uid: Int32 = Int32()
    pid: Int32 = Int32()
    mod_id: Int16 = Int16()
    is_logger: Int16 = Int16()
    is_unique: Int16 = Int16()
    port: Uint16 = Uint16()
    name: String = String(32)


@pyrtma.message_def
class MDF_CLIENT_CLOSED(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 33
    type_name: ClassVar[str] = "CLIENT_CLOSED"
    type_hash: ClassVar[int] = 0x087F4249
    type_size: ClassVar[int] = 80
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'CLIENT_CLOSED:\n  id: 33\n  fields:\n    addr: char[32]\n    uid: int32\n    pid: int32\n    mod_id: MODULE_ID\n    is_logger: int16\n    is_unique: int16\n    port: uint16\n    name: char[MAX_NAME_LEN]'"

    addr: String = String(32)
    uid: Int32 = Int32()
    pid: Int32 = Int32()
    mod_id: Int16 = Int16()
    is_logger: Int16 = Int16()
    is_unique: Int16 = Int16()
    port: Uint16 = Uint16()
    name: String = String(32)


@pyrtma.message_def
class MDF_CLIENT_SET_NAME(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 34
    type_name: ClassVar[str] = "CLIENT_SET_NAME"
    type_hash: ClassVar[int] = 0x34465AE2
    type_size: ClassVar[int] = 32
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'CLIENT_SET_NAME:\n  id: 34\n  fields:\n    name: char[MAX_NAME_LEN]'"

    name: String = String(32)


@pyrtma.message_def
class MDF_RTMA_LOG(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 40
    type_name: ClassVar[str] = "RTMA_LOG"
    type_hash: ClassVar[int] = 0x975F197F
    type_size: ClassVar[int] = 1936
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'RTMA_LOG:\n  id: 40\n  fields:\n    time: double\n    level: int32\n    lineno: int32\n    name: char[128]\n    pathname: char[512]\n    funcname: char[256]\n    message: char[MAX_LOG_LENGTH]'"

    time: Double = Double()
    level: Int32 = Int32()
    lineno: Int32 = Int32()
    name: String = String(128)
    pathname: String = String(512)
    funcname: String = String(256)
    message: String = String(1024)


@pyrtma.message_def
class MDF_RTMA_LOG_CRITICAL(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 41
    type_name: ClassVar[str] = "RTMA_LOG_CRITICAL"
    type_hash: ClassVar[int] = 0xDEBCA500
    type_size: ClassVar[int] = 1936
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'RTMA_LOG_CRITICAL:\n  id: 41\n  fields:\n    time: double\n    level: int32\n    lineno: int32\n    name: char[128]\n    pathname: char[512]\n    funcname: char[256]\n    message: char[MAX_LOG_LENGTH]'"

    time: Double = Double()
    level: Int32 = Int32()
    lineno: Int32 = Int32()
    name: String = String(128)
    pathname: String = String(512)
    funcname: String = String(256)
    message: String = String(1024)


@pyrtma.message_def
class MDF_RTMA_LOG_ERROR(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 42
    type_name: ClassVar[str] = "RTMA_LOG_ERROR"
    type_hash: ClassVar[int] = 0x45D2E328
    type_size: ClassVar[int] = 1936
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'RTMA_LOG_ERROR:\n  id: 42\n  fields:\n    time: double\n    level: int32\n    lineno: int32\n    name: char[128]\n    pathname: char[512]\n    funcname: char[256]\n    message: char[MAX_LOG_LENGTH]'"

    time: Double = Double()
    level: Int32 = Int32()
    lineno: Int32 = Int32()
    name: String = String(128)
    pathname: String = String(512)
    funcname: String = String(256)
    message: String = String(1024)


@pyrtma.message_def
class MDF_RTMA_LOG_WARNING(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 43
    type_name: ClassVar[str] = "RTMA_LOG_WARNING"
    type_hash: ClassVar[int] = 0xE6399270
    type_size: ClassVar[int] = 1936
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'RTMA_LOG_WARNING:\n  id: 43\n  fields:\n    time: double\n    level: int32\n    lineno: int32\n    name: char[128]\n    pathname: char[512]\n    funcname: char[256]\n    message: char[MAX_LOG_LENGTH]'"

    time: Double = Double()
    level: Int32 = Int32()
    lineno: Int32 = Int32()
    name: String = String(128)
    pathname: String = String(512)
    funcname: String = String(256)
    message: String = String(1024)


@pyrtma.message_def
class MDF_RTMA_LOG_INFO(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 44
    type_name: ClassVar[str] = "RTMA_LOG_INFO"
    type_hash: ClassVar[int] = 0x607B81E9
    type_size: ClassVar[int] = 1936
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'RTMA_LOG_INFO:\n  id: 44\n  fields:\n    time: double\n    level: int32\n    lineno: int32\n    name: char[128]\n    pathname: char[512]\n    funcname: char[256]\n    message: char[MAX_LOG_LENGTH]'"

    time: Double = Double()
    level: Int32 = Int32()
    lineno: Int32 = Int32()
    name: String = String(128)
    pathname: String = String(512)
    funcname: String = String(256)
    message: String = String(1024)


@pyrtma.message_def
class MDF_RTMA_LOG_DEBUG(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = 45
    type_name: ClassVar[str] = "RTMA_LOG_DEBUG"
    type_hash: ClassVar[int] = 0x45EDC532
    type_size: ClassVar[int] = 1936
    type_source: ClassVar[str] = "core_defs.yaml"
    type_def: ClassVar[
        str
    ] = "'RTMA_LOG_DEBUG:\n  id: 45\n  fields:\n    time: double\n    level: int32\n    lineno: int32\n    name: char[128]\n    pathname: char[512]\n    funcname: char[256]\n    message: char[MAX_LOG_LENGTH]'"

    time: Double = Double()
    level: Int32 = Int32()
    lineno: Int32 = Int32()
    name: String = String(128)
    pathname: String = String(512)
    funcname: String = String(256)
    message: String = String(1024)


# User Context
update_context(__name__)
