"""pyrtma core definitions """
import ctypes
import pyrtma

# Constants
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

# String Constants

# Type Aliases
MODULE_ID = ctypes.c_short


HOST_ID = ctypes.c_short


MSG_TYPE = ctypes.c_int


MSG_COUNT = ctypes.c_int


# Host IDs
LOCAL_HOST = 0
ALL_HOSTS = 32767

# Module IDs
MID_MESSAGE_MANAGER = 0
MID_QUICK_LOGGER = 5

# Message Type IDs
MT_EXIT = 0
MT_KILL = 1
MT_ACKNOWLEDGE = 2
MT_FAIL_SUBSCRIBE = 6
MT_FAILED_MESSAGE = 8
MT_CONNECT = 13
MT_DISCONNECT = 14
MT_SUBSCRIBE = 15
MT_UNSUBSCRIBE = 16
MT_MODULE_READY = 26
MT_LM_EXIT = 55
MT_SAVE_MESSAGE_LOG = 56
MT_MESSAGE_LOG_SAVED = 57
MT_PAUSE_MESSAGE_LOGGING = 58
MT_RESUME_MESSAGE_LOGGING = 59
MT_RESET_MESSAGE_LOG = 60
MT_DUMP_MESSAGE_LOG = 61
MT_TIMING_MESSAGE = 80
MT_FORCE_DISCONNECT = 82
MT_PAUSE_SUBSCRIPTION = 85
MT_RESUME_SUBSCRIPTION = 86
MT_LM_READY = 96


# Struct Definitions
class RTMA_MSG_HEADER(ctypes.Structure):
    _fields_ = [
        ("msg_type", MSG_TYPE),
        ("msg_count", MSG_COUNT),
        ("send_time", ctypes.c_double),
        ("recv_time", ctypes.c_double),
        ("src_host_id", HOST_ID),
        ("src_mod_id", MODULE_ID),
        ("dest_host_id", HOST_ID),
        ("dest_mod_id", MODULE_ID),
        ("num_data_bytes", ctypes.c_int),
        ("remaining_bytes", ctypes.c_int),
        ("is_dynamic", ctypes.c_int),
        ("reserved", ctypes.c_int),
    ]


# Message Definitions
@pyrtma.message_def
class MDF_EXIT(pyrtma.MessageData):
    _fields_ = []
    type_id = 0
    type_name = "EXIT"
    type_hash = 0x095E0546
    type_source = "core_defs/core_defs.yaml"
    type_def = "'EXIT:\n  id: 0\n  fields: null'"


@pyrtma.message_def
class MDF_KILL(pyrtma.MessageData):
    _fields_ = []
    type_id = 1
    type_name = "KILL"
    type_hash = 0x82FC702D
    type_source = "core_defs/core_defs.yaml"
    type_def = "'KILL:\n  id: 1\n  fields: null'"


@pyrtma.message_def
class MDF_ACKNOWLEDGE(pyrtma.MessageData):
    _fields_ = []
    type_id = 2
    type_name = "ACKNOWLEDGE"
    type_hash = 0xB725B581
    type_source = "core_defs/core_defs.yaml"
    type_def = "'ACKNOWLEDGE:\n  id: 2\n  fields: null'"


@pyrtma.message_def
class MDF_FAIL_SUBSCRIBE(pyrtma.MessageData):
    _fields_ = [
        ("mod_id", MODULE_ID),
        ("reserved", ctypes.c_short),
        ("msg_type", MSG_TYPE),
    ]
    type_id = 6
    type_name = "FAIL_SUBSCRIBE"
    type_hash = 0x9AD70A15
    type_source = "core_defs/core_defs.yaml"
    type_def = "'FAIL_SUBSCRIBE:\n  id: 6\n  fields:\n    mod_id: MODULE_ID\n    reserved: short\n    msg_type: MSG_TYPE'"


@pyrtma.message_def
class MDF_FAILED_MESSAGE(pyrtma.MessageData):
    _fields_ = [
        ("dest_mod_id", MODULE_ID),
        ("reserved", ctypes.c_short * 3),
        ("time_of_failure", ctypes.c_double),
        ("msg_header", RTMA_MSG_HEADER),
    ]
    type_id = 8
    type_name = "FAILED_MESSAGE"
    type_hash = 0xDCA545B2
    type_source = "core_defs/core_defs.yaml"
    type_def = "'FAILED_MESSAGE:\n  id: 8\n  fields:\n    dest_mod_id: MODULE_ID\n    reserved: short[3]\n    time_of_failure: double\n    msg_header: RTMA_MSG_HEADER'"


@pyrtma.message_def
class MDF_CONNECT(pyrtma.MessageData):
    _fields_ = [("logger_status", ctypes.c_short), ("daemon_status", ctypes.c_short)]
    type_id = 13
    type_name = "CONNECT"
    type_hash = 0x6F2E3CA5
    type_source = "core_defs/core_defs.yaml"
    type_def = "'CONNECT:\n  id: 13\n  fields:\n    logger_status: short\n    daemon_status: short'"


@pyrtma.message_def
class MDF_DISCONNECT(pyrtma.MessageData):
    _fields_ = []
    type_id = 14
    type_name = "DISCONNECT"
    type_hash = 0xD0126BF9
    type_source = "core_defs/core_defs.yaml"
    type_def = "'DISCONNECT:\n  id: 14\n  fields: null'"


@pyrtma.message_def
class MDF_SUBSCRIBE(pyrtma.MessageData):
    _fields_ = [("msg_type", MSG_TYPE)]
    type_id = 15
    type_name = "SUBSCRIBE"
    type_hash = 0xF5B437C8
    type_source = "core_defs/core_defs.yaml"
    type_def = "'SUBSCRIBE:\n  id: 15\n  fields:\n    msg_type: MSG_TYPE'"


@pyrtma.message_def
class MDF_UNSUBSCRIBE(pyrtma.MessageData):
    _fields_ = [("msg_type", MSG_TYPE)]
    type_id = 16
    type_name = "UNSUBSCRIBE"
    type_hash = 0x193FB9E0
    type_source = "core_defs/core_defs.yaml"
    type_def = "'UNSUBSCRIBE:\n  id: 16\n  fields:\n    msg_type: MSG_TYPE'"


@pyrtma.message_def
class MDF_MODULE_READY(pyrtma.MessageData):
    _fields_ = [("pid", ctypes.c_int)]
    type_id = 26
    type_name = "MODULE_READY"
    type_hash = 0x0DF81813
    type_source = "core_defs/core_defs.yaml"
    type_def = "'MODULE_READY:\n  id: 26\n  fields:\n    pid: int'"


@pyrtma.message_def
class MDF_LM_EXIT(pyrtma.MessageData):
    _fields_ = []
    type_id = 55
    type_name = "LM_EXIT"
    type_hash = 0x35DD547B
    type_source = "core_defs/core_defs.yaml"
    type_def = "'LM_EXIT:\n  id: 55\n  fields: null'"


@pyrtma.message_def
class MDF_SAVE_MESSAGE_LOG(pyrtma.MessageData):
    _fields_ = [("pathname", ctypes.c_char * 256), ("pathname_length", ctypes.c_int)]
    type_id = 56
    type_name = "SAVE_MESSAGE_LOG"
    type_hash = 0x515569E9
    type_source = "core_defs/core_defs.yaml"
    type_def = "'SAVE_MESSAGE_LOG:\n  id: 56\n  fields:\n    pathname: char[MAX_LOGGER_FILENAME_LENGTH]\n    pathname_length: int'"


@pyrtma.message_def
class MDF_MESSAGE_LOG_SAVED(pyrtma.MessageData):
    _fields_ = []
    type_id = 57
    type_name = "MESSAGE_LOG_SAVED"
    type_hash = 0x66E84AE5
    type_source = "core_defs/core_defs.yaml"
    type_def = "'MESSAGE_LOG_SAVED:\n  id: 57\n  fields: null'"


@pyrtma.message_def
class MDF_PAUSE_MESSAGE_LOGGING(pyrtma.MessageData):
    _fields_ = []
    type_id = 58
    type_name = "PAUSE_MESSAGE_LOGGING"
    type_hash = 0x20C1E922
    type_source = "core_defs/core_defs.yaml"
    type_def = "'PAUSE_MESSAGE_LOGGING:\n  id: 58\n  fields: null'"


@pyrtma.message_def
class MDF_RESUME_MESSAGE_LOGGING(pyrtma.MessageData):
    _fields_ = []
    type_id = 59
    type_name = "RESUME_MESSAGE_LOGGING"
    type_hash = 0x0D1A3E77
    type_source = "core_defs/core_defs.yaml"
    type_def = "'RESUME_MESSAGE_LOGGING:\n  id: 59\n  fields: null'"


@pyrtma.message_def
class MDF_RESET_MESSAGE_LOG(pyrtma.MessageData):
    _fields_ = []
    type_id = 60
    type_name = "RESET_MESSAGE_LOG"
    type_hash = 0x68EC4AAB
    type_source = "core_defs/core_defs.yaml"
    type_def = "'RESET_MESSAGE_LOG:\n  id: 60\n  fields: null'"


@pyrtma.message_def
class MDF_DUMP_MESSAGE_LOG(pyrtma.MessageData):
    _fields_ = []
    type_id = 61
    type_name = "DUMP_MESSAGE_LOG"
    type_hash = 0xF9D7E2BF
    type_source = "core_defs/core_defs.yaml"
    type_def = "'DUMP_MESSAGE_LOG:\n  id: 61\n  fields: null'"


@pyrtma.message_def
class MDF_TIMING_MESSAGE(pyrtma.MessageData):
    _fields_ = [
        ("timing", ctypes.c_ushort * 10000),
        ("ModulePID", ctypes.c_int * 200),
        ("send_time", ctypes.c_double),
    ]
    type_id = 80
    type_name = "TIMING_MESSAGE"
    type_hash = 0x3595C23E
    type_source = "core_defs/core_defs.yaml"
    type_def = "'TIMING_MESSAGE:\n  id: 80\n  fields:\n    timing: unsigned short[MAX_MESSAGE_TYPES]\n    ModulePID: int[MAX_MODULES]\n    send_time: double'"


@pyrtma.message_def
class MDF_FORCE_DISCONNECT(pyrtma.MessageData):
    _fields_ = [("mod_id", ctypes.c_int)]
    type_id = 82
    type_name = "FORCE_DISCONNECT"
    type_hash = 0xC37C54E8
    type_source = "core_defs/core_defs.yaml"
    type_def = "'FORCE_DISCONNECT:\n  id: 82\n  fields:\n    mod_id: int'"


@pyrtma.message_def
class MDF_PAUSE_SUBSCRIPTION(pyrtma.MessageData):
    _fields_ = [("msg_type", MSG_TYPE)]
    type_id = 85
    type_name = "PAUSE_SUBSCRIPTION"
    type_hash = 0x22338A6D
    type_source = "core_defs/core_defs.yaml"
    type_def = "'PAUSE_SUBSCRIPTION:\n  id: 85\n  fields:\n    msg_type: MSG_TYPE'"


@pyrtma.message_def
class MDF_RESUME_SUBSCRIPTION(pyrtma.MessageData):
    _fields_ = [("msg_type", MSG_TYPE)]
    type_id = 86
    type_name = "RESUME_SUBSCRIPTION"
    type_hash = 0xC56A97F2
    type_source = "core_defs/core_defs.yaml"
    type_def = "'RESUME_SUBSCRIPTION:\n  id: 86\n  fields:\n    msg_type: MSG_TYPE'"


@pyrtma.message_def
class MDF_LM_READY(pyrtma.MessageData):
    _fields_ = []
    type_id = 96
    type_name = "LM_READY"
    type_hash = 0x4863B960
    type_source = "core_defs/core_defs.yaml"
    type_def = "'LM_READY:\n  id: 96\n  fields: null'"


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


RTMA = _RTMA()
