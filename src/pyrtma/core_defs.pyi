import ctypes
import pyrtma

# Type Aliases
MODULE_ID = ctypes.c_short
HOST_ID = ctypes.c_short
MSG_TYPE = ctypes.c_int
MSG_COUNT = ctypes.c_int

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
