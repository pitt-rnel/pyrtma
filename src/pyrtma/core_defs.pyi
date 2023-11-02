import ctypes
import pyrtma
from pyrtma.message import CArrayProxy

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

# Message Definitions
class MDF_EXIT(pyrtma.MessageData): ...
class MDF_KILL(pyrtma.MessageData): ...
class MDF_ACKNOWLEDGE(pyrtma.MessageData): ...

class MDF_FAIL_SUBSCRIBE(pyrtma.MessageData):
    mod_id: int
    reserved: int
    msg_type: int

class MDF_FAILED_MESSAGE(pyrtma.MessageData):
    dest_mod_id: int
    reserved: CArrayProxy[ctypes.c_short]  # length: 3
    time_of_failure: float
    msg_header: RTMA_MSG_HEADER

class MDF_CONNECT(pyrtma.MessageData):
    logger_status: int
    daemon_status: int

class MDF_DISCONNECT(pyrtma.MessageData): ...

class MDF_SUBSCRIBE(pyrtma.MessageData):
    msg_type: int

class MDF_UNSUBSCRIBE(pyrtma.MessageData):
    msg_type: int

class MDF_MODULE_READY(pyrtma.MessageData):
    pid: int

class MDF_LM_EXIT(pyrtma.MessageData): ...

class MDF_SAVE_MESSAGE_LOG(pyrtma.MessageData):
    pathname: str  # length: 256
    pathname_length: int

class MDF_MESSAGE_LOG_SAVED(pyrtma.MessageData): ...
class MDF_PAUSE_MESSAGE_LOGGING(pyrtma.MessageData): ...
class MDF_RESUME_MESSAGE_LOGGING(pyrtma.MessageData): ...
class MDF_RESET_MESSAGE_LOG(pyrtma.MessageData): ...
class MDF_DUMP_MESSAGE_LOG(pyrtma.MessageData): ...

class MDF_TIMING_MESSAGE(pyrtma.MessageData):
    timing: CArrayProxy[ctypes.c_ushort]  # length: 10000
    ModulePID: CArrayProxy[ctypes.c_int]  # length: 200
    send_time: float

class MDF_FORCE_DISCONNECT(pyrtma.MessageData):
    mod_id: int

class MDF_PAUSE_SUBSCRIPTION(pyrtma.MessageData):
    msg_type: int

class MDF_RESUME_SUBSCRIPTION(pyrtma.MessageData):
    msg_type: int

class MDF_LM_READY(pyrtma.MessageData): ...
