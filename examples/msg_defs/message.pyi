import ctypes
import pyrtma

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
STR_SIZE: int = 32
LONG_STRING: int = 64

# String Constants
default_msg: str = "hello_world"

# Type Aliases
MODULE_ID = ctypes.c_short
HOST_ID = ctypes.c_short
MSG_TYPE = ctypes.c_int
MSG_COUNT = ctypes.c_int
AGE_TYPE = ctypes.c_int

# Host IDs
LOCAL_HOST: int = 0
ALL_HOSTS: int = 32767

# Module IDs
MID_MESSAGE_MANAGER: int = 0
MID_QUICK_LOGGER: int = 5
MID_PERSON_PUBLISHER: int = 213
MID_PERSON_SUBSCRIBER: int = 214

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
MT_PERSON_MESSAGE: int = 1234
MT_ANOTHER_EXAMPLE: int = 5678
MT_USER_SIGNAL: int = 2468
MT_PERSON_LIST: int = 1357
MT_EMPLOYEES: int = 1368
MT__RESERVED_001000: int = 1000
MT__RESERVED_001002: int = 1002
MT__RESERVED_001003: int = 1003
MT__RESERVED_001004: int = 1004
MT__RESERVED_001005: int = 1005
MT__RESERVED_001006: int = 1006
MT__RESERVED_001007: int = 1007
MT__RESERVED_001008: int = 1008
MT__RESERVED_001009: int = 1009
MT__RESERVED_001010: int = 1010
MT__RESERVED_001011: int = 1011
MT__RESERVED_001012: int = 1012

# Struct Definitions
class RTMA_MSG_HEADER(ctypes.Structure):
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

class TEST_STRUCT(ctypes.Structure):
    value_str: str
    value_int: int

# Message Definitions
class MDF_EXIT(pyrtma.MessageData):
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_KILL(pyrtma.MessageData):
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_ACKNOWLEDGE(pyrtma.MessageData):
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_FAIL_SUBSCRIBE(pyrtma.MessageData):
    mod_id: int
    reserved: int
    msg_type: int
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_FAILED_MESSAGE(pyrtma.MessageData):
    dest_mod_id: int
    reserved: ctypes.c_short * 3
    time_of_failure: float
    msg_header: RTMA_MSG_HEADER
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_CONNECT(pyrtma.MessageData):
    logger_status: int
    daemon_status: int
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_DISCONNECT(pyrtma.MessageData):
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_SUBSCRIBE(pyrtma.MessageData):
    msg_type: int
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_UNSUBSCRIBE(pyrtma.MessageData):
    msg_type: int
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_MODULE_READY(pyrtma.MessageData):
    pid: int
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_LM_EXIT(pyrtma.MessageData):
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_SAVE_MESSAGE_LOG(pyrtma.MessageData):
    pathname: str
    pathname_length: int
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_MESSAGE_LOG_SAVED(pyrtma.MessageData):
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_PAUSE_MESSAGE_LOGGING(pyrtma.MessageData):
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_RESUME_MESSAGE_LOGGING(pyrtma.MessageData):
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_RESET_MESSAGE_LOG(pyrtma.MessageData):
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_DUMP_MESSAGE_LOG(pyrtma.MessageData):
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_TIMING_MESSAGE(pyrtma.MessageData):
    timing: ctypes.c_ushort * 10000
    ModulePID: ctypes.c_int * 200
    send_time: float
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_FORCE_DISCONNECT(pyrtma.MessageData):
    mod_id: int
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_PAUSE_SUBSCRIPTION(pyrtma.MessageData):
    msg_type: int
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_RESUME_SUBSCRIPTION(pyrtma.MessageData):
    msg_type: int
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_LM_READY(pyrtma.MessageData):
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_PERSON_MESSAGE(pyrtma.MessageData):
    name: str
    age: int
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_ANOTHER_EXAMPLE(pyrtma.MessageData):
    value_struct: TEST_STRUCT
    value_float: float
    value_double: float
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_USER_SIGNAL(pyrtma.MessageData):
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_PERSON_LIST(pyrtma.MessageData):
    person: MDF_PERSON_MESSAGE * 32
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF_EMPLOYEES(pyrtma.MessageData):
    person: MDF_PERSON_MESSAGE * 32
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF__RESERVED_001000(pyrtma.MessageData):
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF__RESERVED_001002(pyrtma.MessageData):
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF__RESERVED_001003(pyrtma.MessageData):
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF__RESERVED_001004(pyrtma.MessageData):
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF__RESERVED_001005(pyrtma.MessageData):
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF__RESERVED_001006(pyrtma.MessageData):
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF__RESERVED_001007(pyrtma.MessageData):
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF__RESERVED_001008(pyrtma.MessageData):
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF__RESERVED_001009(pyrtma.MessageData):
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF__RESERVED_001010(pyrtma.MessageData):
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF__RESERVED_001011(pyrtma.MessageData):
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str

class MDF__RESERVED_001012(pyrtma.MessageData):
    type_id: int
    type_name: str
    type_hash: int
    type_source: str
    type_def: str
