"""pyrtma.constants module

This module is deprecated and included for backwards compatilibity with pyrtma 1.2.3
Constants have been moved to pyrtma.core_defs
"""

from .core_defs import (
    MAX_MODULES,
    DYN_MOD_ID_START,
    MAX_HOSTS,
    MAX_MESSAGE_TYPES,
    MIN_STREAM_TYPE,
    MAX_TIMERS,
    MAX_INTERNAL_TIMERS,
    MAX_RTMA_MSG_TYPE,
    MAX_RTMA_MODULE_ID,
    MAX_LOGGER_FILENAME_LENGTH,
    MAX_CONTIGUOUS_MESSAGE_DATA,
    ALL_MESSAGE_TYPES,
    MODULE_ID,
    HOST_ID,
    MSG_TYPE,
    MSG_COUNT,
    LOCAL_HOST,
    ALL_HOSTS,
    MID_MESSAGE_MANAGER,
    MID_QUICK_LOGGER,
    MT_EXIT,
    MT_KILL,
    MT_ACKNOWLEDGE,
    MT_FAIL_SUBSCRIBE,
    MT_FAILED_MESSAGE,
    MT_CONNECT,
    MT_DISCONNECT,
    MT_SUBSCRIBE,
    MT_UNSUBSCRIBE,
    MT_PAUSE_SUBSCRIPTION,
    MT_RESUME_SUBSCRIPTION,
    MT_SAVE_MESSAGE_LOG,
    MT_MESSAGE_LOG_SAVED,
    MT_FORCE_DISCONNECT,
    MT_MODULE_READY,
    MT_TIMING_MESSAGE,
)

from warnings import warn

warn(
    "pyrtma.constants module is deprecated and has been replaced by pyrtma.core_defs",
    FutureWarning,
)

HID_LOCAL_HOST = LOCAL_HOST
HID_ALL_HOSTS = ALL_HOSTS

# DEPRECATED MIDS
MID_COMMAND_MODULE = 1
MID_APPLICATION_MODULE = 2
MID_NETWORK_RELAY = 3
MID_STATUS_MODULE = 4
MID_QUICKLOGGER = MID_QUICK_LOGGER

# DEPRECATED MTs
MT_PAUSE_MESSAGE_LOGGING = 58  # not fully implemented
MT_RESUME_MESSAGE_LOGGING = 59  # not fully implemented
MT_RESET_MESSAGE_LOG = 60  # un-deprecate?
MT_DUMP_MESSAGE_LOG = 61  # un-deprecate?
