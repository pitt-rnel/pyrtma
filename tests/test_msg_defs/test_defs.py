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
MJ_VR_MAX_MOCAP_COUNT = 32
MJ_VR_MAX_BODY_COUNT = 64
MJ_VR_MAX_MOTOR_COUNT = 32
MJ_VR_MAX_JOINT_COUNT = 64
MJ_VR_MAX_JOINT_DOF = 128
MJ_VR_MAX_CONTACT_COUNT = 32
MJ_VR_MAX_TENDON_COUNT = 32
MAX_SPIKE_SOURCES = 2
MAX_SPIKE_SOURCES_N256 = 1
MAX_SPIKE_CHANS_PER_SOURCE = 128
MAX_SPIKE_CHANS_PER_SOURCE_N256 = 256
MAX_COINCIDENT_SPIKES = 45
MAX_ANALOG_CHANS = 16
MAX_UNITS_PER_CHAN = 5
MAX_TOTAL_SPIKE_CHANS_PER_SOURCE = 640
MAX_TOTAL_SPIKE_CHANS_PER_SOURCE_N256 = 1280
MAX_TOTAL_SPIKE_CHANS = 1280
MAX_TOTAL_SPIKE_CHANS_N256 = 1280
LFPSAMPLES_PER_HEARTBEAT = 10
ANALOGSAMPLES_PER_HEARTBEAT = 10
RAW_COUNTS_PER_SAMPLE = 2
SAMPLE_LENGTH_MS = 20
SAMPLE_LENGTH = 0.02
SNIPPETS_PER_MESSAGE = 25
SAMPLES_PER_SNIPPET = 48
MAX_DIG_PER_SAMPLE = 10
MAX_DATAGLOVE_SENSORS = 18
NUM_DOMAINS = 6
MAX_COMMAND_DIMS = 30
MPL_RAW_PERCEPT_DIMS = 54
NUM_STIM_CHANS = 64
SHAM_STIM_CHANS = 32
MAX_STIM_CHANS_ON = 12
PULSE_TRAIN_SIZE = 101
MAX_CS_CONFIGS = 16
NUM_SPIKES_PER_STIM_MSG = 26
MAX_XIPP_EEG_HEADSTAGES = 2
MAX_XIPP_CHANS = 64
MAX_XIPP_ANALOG_CHANS = 32
XIPP_SAMPLES_PER_MSG = 20
MAX_MYO_EMG_CHANS = 8
MYO_SAMPLES_PER_MSG = 4
GRIP_DIMS_R = 1
GRIP_DIMS_L = 1
MAX_GRIP_DIMS = 9
MAX_GRIPPER_DIMS = 1
MAX_GRIPPER_JOINT_ANGLES = 5
MAX_GRIPPER_FORCES = 5
MJ_MAX_MOTOR = 1
MJ_MAX_JOINT = 5
MJ_MAX_CONTACT = 5
NoResult = -1
SuccessfulTrial = 1
BadTrial = 2
ManualProceed = 4
ManualFail = 8
HX_DEKA_LUKE_CONTACT_COUNT = 13
HX_LUKE_MOTOR_COUNT = 6
NUM_FINGERS = 3
NUM_SENSORS_PER_FINGER = 9
NUM_SENSORS_PALM = 11
NUM_TAKKTILE = 38
NUM_ENCODERS = 3
NUM_SERVOS = 4
NUM_DYNAMIXEL = 4
MECH_STIM_SINE = 1
MECH_STIM_RAMP_AND_HOLD = 2
DEKA_DOF_COUNT = 7
KUKA_DOF_COUNT = 7
PRENSILIA_DOF = 5
PRENSILIA_EXT_SENSORS = 7
TAG_LENGTH = 64
MPL_AT_ARM_EPV_FING_JV = 0
MPL_AT_ARM_EPV_FING_JP = 1
MPL_AT_ARM_JV_FING_JP = 2
MPL_AT_ALL_JV = 3
MPL_AT_ALL_JP = 4
MPL_AT_ARM_EPP_FING_JP = 5
TFD_FREQ_BINS = 20

# String Constants
DEFAULT_MM_IP = "localhost:7111"

# Type Aliases
MODULE_ID = ctypes.c_short


HOST_ID = ctypes.c_short


MSG_TYPE = ctypes.c_int


MSG_COUNT = ctypes.c_int


SPIKE_COUNT_DATA_TYPE = ctypes.c_ubyte


# Host IDs
LOCAL_HOST = 0
ALL_HOSTS = 32767

# Module IDs
MID_MESSAGE_MANAGER = 0
MID_QUICK_LOGGER = 5
MID_MUJOCO_VR_MODULE = 61
MID_JSTICK_COMMAND = 10
MID_COMBINER = 11
MID_CEREBUS = 12
MID_RAW_LOGGER = 16
MID_INPUT_TRANSFORM = 20
MID_RPPL_RECORD = 21
MID_CENTRAL = 22
MID_EXTRACTION = 30
MID_MYO = 31
MID_MECH_STIM_MODULE = 39
MID_MPL_CONTROL = 40
MID_GRIP_CONTROL = 41
MID_DEKA_CAN_MODULE = 42
MID_DEKA_ACI_RESPONSE = 43
MID_DEKA_DISPLAY = 44
MID_PSYCHTLBX = 46
MID_STIM_PRESENT = 48
MID_ACTIVE_ASSIST = 50
MID_KUKA_DISPLAY = 51
MID_ROBOTICS_FEEDBACK_INTEGRATOR = 52
MID_KUKA_INTERFACE_MODULE = 53
MID_KUKA_JOINT_COMMAND_DISPLAY = 54
MID_KUKA_DIAGNOSTICS = 55
MID_FORCE_PLATFORM = 58
MID_FORCE_PLATFORM_DISPLAY = 59
MID_MPL_FEEDBACK = 60
MID_AJA_CONTROL = 65
MID_SEAIOCONTROL = 66
MID_EXECUTIVE = 70
MID_COMMENT_MANAGER = 71
MID_FLIP_THAT_BUCKET_MESSENGER = 74
MID_VOLTAGE_MONITOR_GUI = 76
MID_VOLTAGE_MONITOR = 77
MID_ATIsensor = 78
MID_FOFIX = 79
MID_STIM_THRESH_GAME = 80
MID_MESSAGERATES = 81
MID_VISUAL_GRATING = 85
MID_BIASMODULE = 86
MID_CURSOR = 87
MID_RHR_COMMAND_MODULE = 88
MID_RHR_SENSOR_MODULE = 89
MID_SOUNDPLAYER = 90
MID_RFDISPLAY = 91
MID_RFACTIVITY = 92
MID_ImageDisplayer = 93
MID_FLIP_THAT_BUCKET = 94
MID_STIM_SAFETY_MODULE = 95
MID_SENSOR_STIM_TRANS_MODULE = 96
MID_CERESTIM_CONTROL = 97
MID_SENSE_TOUCH_INTERFACE = 98
MID_SENSOR_STIM_TRANSFORM_PY = 99

# Message Type IDs
MT_EXIT = 0
MT_KILL = 1
MT_ACKNOWLEDGE = 2
MT_CONNECT = 13
MT_DISCONNECT = 14
MT_SUBSCRIBE = 15
MT_UNSUBSCRIBE = 16
MT_PAUSE_SUBSCRIPTION = 85
MT_RESUME_SUBSCRIPTION = 86
MT_FAIL_SUBSCRIBE = 6
MT_FAILED_MESSAGE = 8
MT_FORCE_DISCONNECT = 82
MT_MODULE_READY = 26
MT_SAVE_MESSAGE_LOG = 56
MT_TIMING_MESSAGE = 80
MT_MUJOCO_VR_REQUEST_STATE = 4213
MT_MUJOCO_VR_REPLY_STATE = 4214
MT_MUJOCO_VR_MOCAP_MOVE = 4215
MT_MUJOCO_VR_MOTOR_MOVE = 4216
MT_MUJOCO_VR_REQUEST_MODEL_INFO = 4217
MT_MUJOCO_VR_REPLY_MODEL_INFO = 4218
MT_MUJOCO_VR_REQUEST_LINK_STATE = 4219
MT_MUJOCO_VR_REPLY_LINK_STATE = 4220
MT_MUJOCO_VR_LINK = 4221
MT_MUJOCO_VR_LINK_RESET = 4222
MT_MUJOCO_VR_FLOATBODY_MOVE = 4223
MT_MUJOCO_VR_RESET = 4224
MT_MUJOCO_VR_RELOAD = 4225
MT_MUJOCO_VR_LOAD_MODEL = 4226
MT_MUJOCO_VR_PAUSE = 4227
MT_MUJOCO_VR_RESUME = 4228
MT_MUJOCO_VR_MOTOR_CTRL = 4229
MT_MUJOCO_VR_MOTOR_CONFIG = 4230
MT_MUJOCO_VR_SET_RGBA = 4231
MT_MUJOCO_VR_MSG = 4232
MT_JSON_CONFIG = 1200
MT_FINISHED_COMMAND = 1700
MT_CONTROL_SPACE_FEEDBACK = 1701
MT_CONTROL_SPACE_COMMAND = 1702
MT_MPL_RAW_PERCEPT = 1703
MT_BIAS_COMMAND = 1704
MT_MPL_REBIASED_SENSORDATA = 1705
MT_CONTROL_SPACE_FEEDBACK_RHR_GRIPPER = 1706
MT_CONTROL_SPACE_POS_COMMAND = 1710
MT_MPL_SEGMENT_PERCEPTS = 1711
MT_WAM_FEEDBACK = 1712
MT_IMPEDANCE_COMMAND = 1713
MT_EXECUTIVE_CTRL = 1714
MT_CURSOR_FEEDBACK = 1720
MT_VISUAL_GRATING_BUILD = 1721
MT_VISUAL_GRATING_RESPONSE = 1722
MT_GRIP_COMMAND = 1730
MT_GRIP_FINISHED_COMMAND = 1731
MT_GRIPPER_FEEDBACK = 1732
MT_MUJOCO_SENSOR = 1733
MT_MUJOCO_CMD = 1734
MT_MUJOCO_MOVE = 1735
MT_MUJOCO_MSG = 1736
MT_MUJOCO_GHOST_COLOR = 1737
MT_MUJOCO_OBJMOVE = 1738
MT_OPENHAND_CMD = 1740
MT_OPENHAND_SENS = 1741
MT_PRENSILIA_SENS = 1742
MT_PRENSILIA_CMD = 1743
MT_TABLE_LOAD_CELLS = 1744
MT_REZERO_GRIPPER_SENSORS = 1745
MT_SINGLETACT_DATA = 1760
MT_GET_USER_RESPONSE = 1761
MT_USER_RESPONSE_L = 1762
MT_USER_RESPONSE_R = 1763
MT_RAW_SPIKECOUNT = 1800
MT_SPM_SPIKECOUNT = 1801
MT_SPIKE_SNIPPET = 1802
MT_RAW_CTSDATA = 1803
MT_SPM_CTSDATA = 1804
MT_REJECTED_SNIPPET = 1805
MT_RAW_DIGITAL_EVENT = 1806
MT_SPM_DIGITAL_EVENT = 1807
MT_STIM_SYNC_EVENT = 1808
MT_STIM_UPDATE_EVENT = 1809
MT_CENTRALRECORD = 1810
MT_RAW_ANALOGDATA = 1811
MT_SPM_ANALOGDATA = 1812
MT_RAW_SPIKECOUNT_N256 = 1815
MT_RAW_CTSDATA_N256 = 1816
MT_MECH_SYNC_EVENT = 1817
MT_SAMPLE_GENERATED = 1820
MT_XIPP_EMG_DATA_RAW = 1830
MT_MYO_EMG_DATA = 1831
MT_MYO_KIN_DATA = 1832
MT_INPUT_DOF_DATA = 1850
MT_DATAGLOVE = 1860
MT_OPTITRACK_RIGID_BODY = 1861
MT_TASK_STATE_CONFIG = 1900
MT_PHASE_RESULT = 1901
MT_EXTRACTION_RESPONSE = 1902
MT_NORMALIZATION_FACTOR = 1903
MT_TRIAL_METADATA = 1904
MT_EXTRACTION_REQUEST = 1905
MT_UPDATE_UNIT_STATE = 1906
MT_DISABLED_UNITS = 1907
MT_TRIAL_END = 1910
MT_REP_START = 1911
MT_REP_END = 1912
MT_EXEC_SCORE = 1913
MT_FLIP_THAT_BUCKET_DATA = 1914
MT_SET_START = 1915
MT_SET_END = 1916
MT_BLOCK_START = 1917
MT_BLOCK_END = 1918
MT_SET_METADATA = 1919
MT_EXEC_PAUSE = 1950
MT_EM_ADAPT_NOW = 2000
MT_EM_CONFIGURATION = 2001
MT_TDMS_CREATE = 2002
MT_RF_REPORT = 2003
MT_PICDISPLAY = 2004
MT_STIMDATA = 2005
MT_SEAIO_OUT = 2007
MT_ATIforcesensor = 2008
MT_TACTOR_CMD = 2009
MT_HSTLOG = 3000
MT_STIM_INTERVAL = 3001
MT_USER_SHOT_L = 3002
MT_USER_SHOT_R = 3003
MT_STIM_THRESH = 3004
MT_GAME_ROUND_INFO = 3005
MT_USER_SHOT = 3006
MT_GAME_HEARTBEAT_REQUEST = 3007
MT_GAME_HEARTBEAT_RESPONSE = 3008
MT_PLAYSOUND = 3100
MT_PLAYVIDEO = 3102
MT_START_TIMED_RECORDING = 3101
MT_AJA_CONFIG = 3200
MT_AJA_TIMECODE = 3201
MT_AJA_STATUS = 3202
MT_AJA_STATUS_REQUEST = 3203
MT_FOFIX_PROMPT = 3600
MT_FOFIX_INPUT = 3601
MT_FOFIX_MISSED = 3602
MT_FOFIX_STIM = 3603
MT_FOFIX_KEY = 3604
MT_CERESTIM_CONFIG_MODULE = 4000
MT_CERESTIM_CONFIG_CHAN_PRESAFETY = 4001
MT_CERESTIM_CONFIG_CHAN = 4002
MT_CERESTIM_ERROR = 4003
MT_CERESTIM_ALIVE = 4004
MT_CS_TRAIN_END = 4005
MT_CERESTIM_CONFIG_CHAN_PRESAFETY_ARBITRARY = 4006
MT_CERESTIM_CONFIG_CHAN_ARBITRARY = 4007
MT_CS_ARBITRARY_CLOSE = 4008
MT_STIM_VOLTAGE_MONITOR_DATA = 4009
MT_STIM_VOLTAGE_MONITOR_DIGITAL_DATA = 4010
MT_VOLTAGE_MONITOR_STATUS = 4011
MT_STIM_DUTYCYCLE_TIME = 4012
MT_STIM_TRIAL_DURATION = 4013
MT_CERESTIM_HEARTBEAT = 4014
MT_CERESTIM_HEARTBEAT_RQST = 4015
MT_CERESTIM_SAFETY_ALIVE = 4016
MT_CERESTIM_SAFETY_ALIVE_RQST = 4017
MT_NATURAL_RESPONSE = 4050
MT_DEPTH_RESPONSE = 4051
MT_PAIN_RESPONSE = 4052
MT_OVERALL_INTENSITY_RESPONSE = 4053
MT_OTHER_RESPONSE = 4054
MT_MECH_RESPONSE = 4055
MT_MOVE_RESPONSE = 4056
MT_TINGLE_RESPONSE = 4057
MT_TEMP_RESPONSE = 4058
MT_DIR_PIXEL_COORDS = 4059
MT_PIXEL_COORDS = 4060
MT_HOTSPOT_COORDS = 4061
MT_CLEAR_LINE = 4062
MT_CLEAR_HOTSPOT = 4063
MT_ADD_SENSATION = 4064
MT_SLIDER_DATA = 4065
MT_USER_DEFINED_STIM = 4067
MT_USER_BEHAVIOUR = 4068
MT_STOP_STIM = 4069
MT_PAUSE_TRIAL = 4070
MT_CST_LAMBDA = 4100
MT_CST_SETTINGS = 4101
MT_STIM_PRES_CONFIG = 4150
MT_STIM_PRES_PHASE_END = 4151
MT_STIM_PRESENT = 4152
MT_STIM_PRES_STATUS = 4153
MT_STIM_CONFIG_TYPE = 4154
MT_DEKA_ACI_RESPONSE = 4200
MT_DEKA_SENSOR = 4201
MT_DEKA_CAN_TOGGLE = 4202
MT_DEKA_CAN_GRIP_TOGGLE = 4203
MT_DEKA_CAN_EXIT = 4204
MT_DEKA_HAND_SENSOR = 4205
MT_DEKA_HAND_JSTICK_CMD = 4206
MT_RH_GRIPPER_SENSOR = 4207
MT_KUKA_JOINT_COMMAND = 4208
MT_KUKA_FEEDBACK = 4209
MT_KUKA_EXIT = 4210
MT_KUKA_PTP_JOINT = 4211
MT_KUKA_DEBUG = 4212
MT_VEML7700_SYNC = 4248
MT_VEML7700_DATA = 4249
MT_VEML7700_PING = 4250
MT_VEML7700_PONG = 4251
MT_VEML7700_START = 4252
MT_VEML7700_STOP = 4253
MT_VEML7700_RESET = 4254
MT_VEML7700_CONNECT = 4256
MT_MECH_STIM_CONFIGURE = 4260
MT_MECH_STIM_RESET = 4261
MT_MECH_STIM_STAGE = 4262
MT_MECH_STIM_WAITING = 4263
MT_MECH_STIM_TRIGGER = 4264
MT_MECH_STIM_CANCEL = 4265
MT_MECH_STIM_DONE = 4266
MT_MECH_STIM_ERROR = 4267
MT_UC_MECH_STIM_CONFIGURE = 4268
MT__RESERVED_004300 = 4300
MT__RESERVED_004360 = 4360
MT__RESERVED_004361 = 4361
MT__RESERVED_004362 = 4362
MT__RESERVED_004363 = 4363
MT__RESERVED_004364 = 4364
MT__RESERVED_004365 = 4365
MT__RESERVED_004366 = 4366
MT__RESERVED_004367 = 4367
MT__RESERVED_004368 = 4368
MT__RESERVED_004369 = 4369
MT__RESERVED_004370 = 4370
MT__RESERVED_004371 = 4371
MT__RESERVED_004372 = 4372
MT__RESERVED_004373 = 4373
MT__RESERVED_004374 = 4374
MT__RESERVED_004375 = 4375
MT__RESERVED_004376 = 4376
MT__RESERVED_004377 = 4377
MT__RESERVED_004378 = 4378


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


class MJVR_MSG_HEADER(ctypes.Structure):
    _fields_ = [("serial_no", ctypes.c_int), ("sub_sample", ctypes.c_int)]


class MSG_HEADER(ctypes.Structure):
    _fields_ = [("serial_no", ctypes.c_int), ("sub_sample", ctypes.c_int)]


class SPIKE_SNIPPET_TYPE(ctypes.Structure):
    _fields_ = [
        ("source_index", ctypes.c_int),
        ("channel", ctypes.c_short),
        ("unit", ctypes.c_ubyte),
        ("reserved1", ctypes.c_ubyte),
        ("source_timestamp", ctypes.c_double),
        ("fPattern", ctypes.c_double * 3),
        ("nPeak", ctypes.c_short),
        ("nValley", ctypes.c_short),
        ("reserved2", ctypes.c_int),
        ("snippet", ctypes.c_short * 48),
    ]


class REJECTED_SNIPPET_TYPE(ctypes.Structure):
    _fields_ = [
        ("source_index", ctypes.c_int),
        ("channel", ctypes.c_short),
        ("unit", ctypes.c_ubyte),
        ("reserved1", ctypes.c_ubyte),
        ("source_timestamp", ctypes.c_double),
        ("fPattern", ctypes.c_double * 3),
        ("nPeak", ctypes.c_short),
        ("nValley", ctypes.c_short),
        ("rejectType", ctypes.c_int),
        ("snippet", ctypes.c_short * 48),
    ]


class DEKA_CAN_MSG(ctypes.Structure):
    _fields_ = [
        ("can_id", ctypes.c_uint),
        ("data", ctypes.c_ubyte * 8),
        ("padding", ctypes.c_int),
    ]


class RH_FINGER_DATA(ctypes.Structure):
    _fields_ = [
        ("proximal_angle", ctypes.c_float),
        ("distal_angle", ctypes.c_float),
        ("pressure", ctypes.c_float * 9),
        ("contact", ctypes.c_int * 9),
    ]


class DYNAMIXEL_INFO(ctypes.Structure):
    _fields_ = [
        ("joint_angle", ctypes.c_float * 4),
        ("raw_angle", ctypes.c_float * 4),
        ("velocity", ctypes.c_float * 4),
        ("load", ctypes.c_float * 4),
        ("voltage", ctypes.c_float * 4),
        ("temperature", ctypes.c_int * 4),
    ]


# Message Definitions
@pyrtma.message_def
class MDF_EXIT(pyrtma.MessageData):
    _fields_ = []
    type_id = 0
    type_name = "EXIT"
    type_hash = 0x095E0546
    type_source = "C:\\git\\pyrtma\\src\\pyrtma\\core_defs\\core_defs.yaml"


@pyrtma.message_def
class MDF_KILL(pyrtma.MessageData):
    _fields_ = []
    type_id = 1
    type_name = "KILL"
    type_hash = 0x82FC702D
    type_source = "C:\\git\\pyrtma\\src\\pyrtma\\core_defs\\core_defs.yaml"


@pyrtma.message_def
class MDF_ACKNOWLEDGE(pyrtma.MessageData):
    _fields_ = []
    type_id = 2
    type_name = "ACKNOWLEDGE"
    type_hash = 0xB725B581
    type_source = "C:\\git\\pyrtma\\src\\pyrtma\\core_defs\\core_defs.yaml"


@pyrtma.message_def
class MDF_CONNECT(pyrtma.MessageData):
    _fields_ = [("logger_status", ctypes.c_short), ("daemon_status", ctypes.c_short)]
    type_id = 13
    type_name = "CONNECT"
    type_hash = 0x6F2E3CA5
    type_source = "C:\\git\\pyrtma\\src\\pyrtma\\core_defs\\core_defs.yaml"


@pyrtma.message_def
class MDF_DISCONNECT(pyrtma.MessageData):
    _fields_ = []
    type_id = 14
    type_name = "DISCONNECT"
    type_hash = 0xD0126BF9
    type_source = "C:\\git\\pyrtma\\src\\pyrtma\\core_defs\\core_defs.yaml"


@pyrtma.message_def
class MDF_SUBSCRIBE(pyrtma.MessageData):
    _fields_ = [("msg_type", MSG_TYPE)]
    type_id = 15
    type_name = "SUBSCRIBE"
    type_hash = 0xF5B437C8
    type_source = "C:\\git\\pyrtma\\src\\pyrtma\\core_defs\\core_defs.yaml"


@pyrtma.message_def
class MDF_UNSUBSCRIBE(pyrtma.MessageData):
    _fields_ = [("msg_type", MSG_TYPE)]
    type_id = 16
    type_name = "UNSUBSCRIBE"
    type_hash = 0x193FB9E0
    type_source = "C:\\git\\pyrtma\\src\\pyrtma\\core_defs\\core_defs.yaml"


@pyrtma.message_def
class MDF_PAUSE_SUBSCRIPTION(pyrtma.MessageData):
    _fields_ = [("msg_type", MSG_TYPE)]
    type_id = 85
    type_name = "PAUSE_SUBSCRIPTION"
    type_hash = 0x22338A6D
    type_source = "C:\\git\\pyrtma\\src\\pyrtma\\core_defs\\core_defs.yaml"


@pyrtma.message_def
class MDF_RESUME_SUBSCRIPTION(pyrtma.MessageData):
    _fields_ = [("msg_type", MSG_TYPE)]
    type_id = 86
    type_name = "RESUME_SUBSCRIPTION"
    type_hash = 0xC56A97F2
    type_source = "C:\\git\\pyrtma\\src\\pyrtma\\core_defs\\core_defs.yaml"


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
    type_source = "C:\\git\\pyrtma\\src\\pyrtma\\core_defs\\core_defs.yaml"


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
    type_source = "C:\\git\\pyrtma\\src\\pyrtma\\core_defs\\core_defs.yaml"


@pyrtma.message_def
class MDF_FORCE_DISCONNECT(pyrtma.MessageData):
    _fields_ = [("mod_id", ctypes.c_int)]
    type_id = 82
    type_name = "FORCE_DISCONNECT"
    type_hash = 0xC37C54E8
    type_source = "C:\\git\\pyrtma\\src\\pyrtma\\core_defs\\core_defs.yaml"


@pyrtma.message_def
class MDF_MODULE_READY(pyrtma.MessageData):
    _fields_ = [("pid", ctypes.c_int)]
    type_id = 26
    type_name = "MODULE_READY"
    type_hash = 0x0DF81813
    type_source = "C:\\git\\pyrtma\\src\\pyrtma\\core_defs\\core_defs.yaml"


@pyrtma.message_def
class MDF_SAVE_MESSAGE_LOG(pyrtma.MessageData):
    _fields_ = [("pathname", ctypes.c_char * 256), ("pathname_length", ctypes.c_int)]
    type_id = 56
    type_name = "SAVE_MESSAGE_LOG"
    type_hash = 0x515569E9
    type_source = "C:\\git\\pyrtma\\src\\pyrtma\\core_defs\\core_defs.yaml"


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
    type_source = "C:\\git\\pyrtma\\src\\pyrtma\\core_defs\\core_defs.yaml"


@pyrtma.message_def
class MDF_MUJOCO_VR_REQUEST_STATE(pyrtma.MessageData):
    _fields_ = [("header", MJVR_MSG_HEADER)]
    type_id = 4213
    type_name = "MUJOCO_VR_REQUEST_STATE"
    type_hash = 0xA905B1EA
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs_2.yaml"


@pyrtma.message_def
class MDF_MUJOCO_VR_REPLY_STATE(pyrtma.MessageData):
    _fields_ = [
        ("header", MJVR_MSG_HEADER),
        ("requester_MID", ctypes.c_int),
        ("reserved", ctypes.c_int),
        ("sim_time", ctypes.c_double),
        ("body_position", ctypes.c_double * 192),
        ("body_orientation", ctypes.c_double * 256),
        ("motor_ctrltype", ctypes.c_int * 32),
        ("motor_position", ctypes.c_double * 32),
        ("motor_velocity", ctypes.c_double * 32),
        ("joint_position", ctypes.c_double * 128),
        ("joint_velocity", ctypes.c_double * 128),
        ("joint_torque", ctypes.c_double * 128),
        ("contact", ctypes.c_double * 32),
    ]
    type_id = 4214
    type_name = "MUJOCO_VR_REPLY_STATE"
    type_hash = 0x7CFFFFFF
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs_2.yaml"


@pyrtma.message_def
class MDF_MUJOCO_VR_MOCAP_MOVE(pyrtma.MessageData):
    _fields_ = [
        ("header", MJVR_MSG_HEADER),
        ("num_id", ctypes.c_int),
        ("padding", ctypes.c_int),
        ("id", ctypes.c_int * 32),
        ("position", ctypes.c_double * 96),
        ("orientation", ctypes.c_double * 128),
    ]
    type_id = 4215
    type_name = "MUJOCO_VR_MOCAP_MOVE"
    type_hash = 0x9374BF04
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs_2.yaml"


@pyrtma.message_def
class MDF_MUJOCO_VR_MOTOR_MOVE(pyrtma.MessageData):
    _fields_ = [
        ("header", MJVR_MSG_HEADER),
        ("num_id", ctypes.c_int),
        ("padding", ctypes.c_int),
        ("id", ctypes.c_int * 32),
        ("position", ctypes.c_double * 32),
    ]
    type_id = 4216
    type_name = "MUJOCO_VR_MOTOR_MOVE"
    type_hash = 0x0752D258
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs_2.yaml"


@pyrtma.message_def
class MDF_MUJOCO_VR_REQUEST_MODEL_INFO(pyrtma.MessageData):
    _fields_ = [("header", MJVR_MSG_HEADER)]
    type_id = 4217
    type_name = "MUJOCO_VR_REQUEST_MODEL_INFO"
    type_hash = 0xDB6CFB78
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs_2.yaml"


@pyrtma.message_def
class MDF_MUJOCO_VR_REPLY_MODEL_INFO(pyrtma.MessageData):
    _fields_ = [
        ("header", MJVR_MSG_HEADER),
        ("requester_MID", ctypes.c_int),
        ("reserved", ctypes.c_int),
        ("model_file", ctypes.c_char * 512),
        ("sim_time", ctypes.c_double),
        ("nq", ctypes.c_int),
        ("nv", ctypes.c_int),
        ("num_body", ctypes.c_int),
        ("num_mocap", ctypes.c_int),
        ("num_float", ctypes.c_int),
        ("num_motor", ctypes.c_int),
        ("num_joint", ctypes.c_int),
        ("num_contact", ctypes.c_int),
        ("num_tendon", ctypes.c_int),
        ("reserved1", ctypes.c_int),
        ("body_id", ctypes.c_int * 64),
        ("mocap_id", ctypes.c_int * 32),
        ("float_id", ctypes.c_int * 32),
        ("motor_id", ctypes.c_int * 32),
        ("joint_id", ctypes.c_int * 64),
        ("contact_id", ctypes.c_int * 32),
        ("tendon_id", ctypes.c_int * 32),
        ("joint_type", ctypes.c_int * 64),
        ("max_motor_limits", ctypes.c_double * 32),
        ("min_motor_limits", ctypes.c_double * 32),
        ("body_names", ctypes.c_char * 1024),
        ("mocap_names", ctypes.c_char * 1024),
        ("float_names", ctypes.c_char * 1024),
        ("motor_names", ctypes.c_char * 1024),
        ("joint_names", ctypes.c_char * 1024),
        ("contact_names", ctypes.c_char * 1024),
        ("tendon_names", ctypes.c_char * 1024),
    ]
    type_id = 4218
    type_name = "MUJOCO_VR_REPLY_MODEL_INFO"
    type_hash = 0x1FE455A2
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs_2.yaml"


@pyrtma.message_def
class MDF_MUJOCO_VR_REQUEST_LINK_STATE(pyrtma.MessageData):
    _fields_ = [("header", MJVR_MSG_HEADER)]
    type_id = 4219
    type_name = "MUJOCO_VR_REQUEST_LINK_STATE"
    type_hash = 0x617B3B37
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs_2.yaml"


@pyrtma.message_def
class MDF_MUJOCO_VR_REPLY_LINK_STATE(pyrtma.MessageData):
    _fields_ = [
        ("header", MJVR_MSG_HEADER),
        ("requester_MID", ctypes.c_int),
        ("reserved", ctypes.c_int),
        ("nlink", ctypes.c_int),
        ("nfloat", ctypes.c_int),
        ("body_linkid", ctypes.c_int * 64),
        ("link_followerid", ctypes.c_int * 64),
        ("link_leaderid", ctypes.c_int * 64),
        ("link_active", ctypes.c_char * 64),
        ("link_rpos", ctypes.c_double * 192),
        ("link_quat_leader", ctypes.c_double * 256),
        ("link_quat_follower", ctypes.c_double * 256),
    ]
    type_id = 4220
    type_name = "MUJOCO_VR_REPLY_LINK_STATE"
    type_hash = 0x4D3317C3
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs_2.yaml"


@pyrtma.message_def
class MDF_MUJOCO_VR_LINK(pyrtma.MessageData):
    _fields_ = [
        ("header", MJVR_MSG_HEADER),
        ("num_links", ctypes.c_int),
        ("padding", ctypes.c_int),
        ("follower_id", ctypes.c_int * 32),
        ("leader_id", ctypes.c_int * 32),
    ]
    type_id = 4221
    type_name = "MUJOCO_VR_LINK"
    type_hash = 0xFA259BC4
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs_2.yaml"


@pyrtma.message_def
class MDF_MUJOCO_VR_LINK_RESET(pyrtma.MessageData):
    _fields_ = [
        ("header", MJVR_MSG_HEADER),
        ("num_links", ctypes.c_int),
        ("padding", ctypes.c_int),
        ("follower_id", ctypes.c_int * 32),
    ]
    type_id = 4222
    type_name = "MUJOCO_VR_LINK_RESET"
    type_hash = 0xD0F43398
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs_2.yaml"


@pyrtma.message_def
class MDF_MUJOCO_VR_FLOATBODY_MOVE(pyrtma.MessageData):
    _fields_ = [
        ("header", MJVR_MSG_HEADER),
        ("num_id", ctypes.c_int),
        ("padding", ctypes.c_int),
        ("float_body_id", ctypes.c_int * 32),
        ("position", ctypes.c_double * 96),
        ("orientation", ctypes.c_double * 128),
        ("disable_link", ctypes.c_char * 32),
    ]
    type_id = 4223
    type_name = "MUJOCO_VR_FLOATBODY_MOVE"
    type_hash = 0xE6FD9F69
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs_2.yaml"


@pyrtma.message_def
class MDF_MUJOCO_VR_RESET(pyrtma.MessageData):
    _fields_ = []
    type_id = 4224
    type_name = "MUJOCO_VR_RESET"
    type_hash = 0x4101EAB6
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs_2.yaml"


@pyrtma.message_def
class MDF_MUJOCO_VR_RELOAD(pyrtma.MessageData):
    _fields_ = []
    type_id = 4225
    type_name = "MUJOCO_VR_RELOAD"
    type_hash = 0xDB7FF347
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs_2.yaml"


@pyrtma.message_def
class MDF_MUJOCO_VR_LOAD_MODEL(pyrtma.MessageData):
    _fields_ = [("model_filename", ctypes.c_char * 512)]
    type_id = 4226
    type_name = "MUJOCO_VR_LOAD_MODEL"
    type_hash = 0x843D2212
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs_2.yaml"


@pyrtma.message_def
class MDF_MUJOCO_VR_PAUSE(pyrtma.MessageData):
    _fields_ = []
    type_id = 4227
    type_name = "MUJOCO_VR_PAUSE"
    type_hash = 0x45911E30
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs_2.yaml"


@pyrtma.message_def
class MDF_MUJOCO_VR_RESUME(pyrtma.MessageData):
    _fields_ = []
    type_id = 4228
    type_name = "MUJOCO_VR_RESUME"
    type_hash = 0xF06DB61E
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs_2.yaml"


@pyrtma.message_def
class MDF_MUJOCO_VR_MOTOR_CTRL(pyrtma.MessageData):
    _fields_ = [
        ("header", MJVR_MSG_HEADER),
        ("num_id", ctypes.c_int),
        ("padding", ctypes.c_int),
        ("id", ctypes.c_int * 32),
        ("ctrl", ctypes.c_double * 32),
    ]
    type_id = 4229
    type_name = "MUJOCO_VR_MOTOR_CTRL"
    type_hash = 0x859E58EF
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs_2.yaml"


@pyrtma.message_def
class MDF_MUJOCO_VR_MOTOR_CONFIG(pyrtma.MessageData):
    _fields_ = [
        ("header", MJVR_MSG_HEADER),
        ("num_id", ctypes.c_int),
        ("padding", ctypes.c_int),
        ("id", ctypes.c_int * 32),
        ("type", ctypes.c_int * 32),
        ("k_p", ctypes.c_double * 32),
        ("k_i", ctypes.c_double * 32),
        ("k_d", ctypes.c_double * 32),
        ("setpt", ctypes.c_double * 32),
    ]
    type_id = 4230
    type_name = "MUJOCO_VR_MOTOR_CONFIG"
    type_hash = 0x39277972
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs_2.yaml"


@pyrtma.message_def
class MDF_MUJOCO_VR_SET_RGBA(pyrtma.MessageData):
    _fields_ = [
        ("header", MJVR_MSG_HEADER),
        ("type", ctypes.c_int),
        ("id", ctypes.c_int),
        ("rgba", ctypes.c_float * 4),
    ]
    type_id = 4231
    type_name = "MUJOCO_VR_SET_RGBA"
    type_hash = 0xB4A5AF8C
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs_2.yaml"


@pyrtma.message_def
class MDF_MUJOCO_VR_MSG(pyrtma.MessageData):
    _fields_ = [("message", ctypes.c_char * 256), ("position", ctypes.c_int)]
    type_id = 4232
    type_name = "MUJOCO_VR_MSG"
    type_hash = 0x91B7BC32
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs_2.yaml"


@pyrtma.message_def
class MDF_JSON_CONFIG(pyrtma.MessageData):
    _fields_ = [
        ("src", ctypes.c_int),
        ("dest", ctypes.c_int),
        ("json_config", ctypes.c_char * 256),
    ]
    type_id = 1200
    type_name = "JSON_CONFIG"
    type_hash = 0x66BE0697
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_FINISHED_COMMAND(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("command", ctypes.c_double * 30),
        ("stiffness", ctypes.c_double * 54),
        ("src", ctypes.c_int),
        ("reserved", ctypes.c_int),
    ]
    type_id = 1700
    type_name = "FINISHED_COMMAND"
    type_hash = 0xDC700A4E
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_CONTROL_SPACE_FEEDBACK(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("position", ctypes.c_double * 30),
        ("velocity", ctypes.c_double * 30),
    ]
    type_id = 1701
    type_name = "CONTROL_SPACE_FEEDBACK"
    type_hash = 0x33E67B66
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_CONTROL_SPACE_COMMAND(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("command", ctypes.c_double * 30),
        ("dZ", ctypes.c_double * 9),
        ("src", ctypes.c_int),
        ("actual_pos", ctypes.c_int),
    ]
    type_id = 1702
    type_name = "CONTROL_SPACE_COMMAND"
    type_hash = 0xA477D468
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_MPL_RAW_PERCEPT(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("position", ctypes.c_double * 54),
        ("velocity", ctypes.c_double * 54),
        ("torque", ctypes.c_double * 54),
        ("temperature", ctypes.c_double * 54),
    ]
    type_id = 1703
    type_name = "MPL_RAW_PERCEPT"
    type_hash = 0x7CF55E81
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_BIAS_COMMAND(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("command", ctypes.c_double * 30),
        ("dZ", ctypes.c_double * 9),
        ("src", ctypes.c_int),
        ("reserved", ctypes.c_int),
    ]
    type_id = 1704
    type_name = "BIAS_COMMAND"
    type_hash = 0xD150FE3E
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_MPL_REBIASED_SENSORDATA(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("torque", ctypes.c_double * 54),
        ("ind_force", ctypes.c_double * 14),
        ("mid_force", ctypes.c_double * 14),
        ("rng_force", ctypes.c_double * 14),
        ("lit_force", ctypes.c_double * 14),
        ("thb_force", ctypes.c_double * 14),
        ("contacts", ctypes.c_short * 16),
    ]
    type_id = 1705
    type_name = "MPL_REBIASED_SENSORDATA"
    type_hash = 0x66BD4B53
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_CONTROL_SPACE_FEEDBACK_RHR_GRIPPER(pyrtma.MessageData):
    _fields_ = []
    type_id = 1706
    type_name = "CONTROL_SPACE_FEEDBACK_RHR_GRIPPER"
    type_hash = 0x2DFE82B1
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_CONTROL_SPACE_POS_COMMAND(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("command", ctypes.c_double * 30),
        ("src", ctypes.c_int),
        ("reserved", ctypes.c_int),
    ]
    type_id = 1710
    type_name = "CONTROL_SPACE_POS_COMMAND"
    type_hash = 0x2356D92E
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_MPL_SEGMENT_PERCEPTS(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("ind_force", ctypes.c_double * 14),
        ("mid_force", ctypes.c_double * 14),
        ("rng_force", ctypes.c_double * 14),
        ("lit_force", ctypes.c_double * 14),
        ("thb_force", ctypes.c_double * 14),
        ("ind_accel", ctypes.c_double * 3),
        ("mid_accel", ctypes.c_double * 3),
        ("rng_accel", ctypes.c_double * 3),
        ("lit_accel", ctypes.c_double * 3),
        ("thb_accel", ctypes.c_double * 3),
        ("contacts", ctypes.c_short * 16),
    ]
    type_id = 1711
    type_name = "MPL_SEGMENT_PERCEPTS"
    type_hash = 0xE35431B7
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_WAM_FEEDBACK(pyrtma.MessageData):
    _fields_ = [("position", ctypes.c_double * 7), ("velocity", ctypes.c_double * 7)]
    type_id = 1712
    type_name = "WAM_FEEDBACK"
    type_hash = 0x7AC8375A
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_IMPEDANCE_COMMAND(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("stiffness", ctypes.c_double * 54),
        ("src", ctypes.c_int),
        ("reserved", ctypes.c_int),
    ]
    type_id = 1713
    type_name = "IMPEDANCE_COMMAND"
    type_hash = 0x76BAA4D5
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_EXECUTIVE_CTRL(pyrtma.MessageData):
    _fields_ = [
        ("proceed", ctypes.c_short),
        ("fail", ctypes.c_short),
        ("reserved", ctypes.c_int),
    ]
    type_id = 1714
    type_name = "EXECUTIVE_CTRL"
    type_hash = 0x51B3116C
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_CURSOR_FEEDBACK(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("torque", ctypes.c_double * 54),
        ("ind_force", ctypes.c_double * 14),
        ("mid_force", ctypes.c_double * 14),
        ("rng_force", ctypes.c_double * 14),
        ("lit_force", ctypes.c_double * 14),
        ("thb_force", ctypes.c_double * 14),
        ("contacts", ctypes.c_short * 16),
    ]
    type_id = 1720
    type_name = "CURSOR_FEEDBACK"
    type_hash = 0xDD4FB481
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_VISUAL_GRATING_BUILD(pyrtma.MessageData):
    _fields_ = [
        ("grating_visibility", ctypes.c_short),
        ("stimulation_on", ctypes.c_short),
        ("trial_set", ctypes.c_short),
        ("presentation", ctypes.c_short),
        ("increment_block", ctypes.c_short),
        ("wait_response", ctypes.c_short),
        ("reserved", ctypes.c_short),
    ]
    type_id = 1721
    type_name = "VISUAL_GRATING_BUILD"
    type_hash = 0xAFE0B860
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_VISUAL_GRATING_RESPONSE(pyrtma.MessageData):
    _fields_ = [
        ("channel", ctypes.c_short),
        ("session_num", ctypes.c_short),
        ("set_num", ctypes.c_short),
        ("block_num", ctypes.c_short),
        ("trial_num", ctypes.c_short),
        ("block_ID", ctypes.c_short),
        ("DELTA_reference_frequency", ctypes.c_short),
        ("response", ctypes.c_short),
        ("ICMS_reference_frequency", ctypes.c_float),
        ("ICMS_reference_amplitude", ctypes.c_float),
        ("ICMS_frequency_1", ctypes.c_float),
        ("ICMS_frequency_2", ctypes.c_float),
        ("ICMS_amplitude_1", ctypes.c_float),
        ("ICMS_amplitude_2", ctypes.c_float),
        ("VIS_reference_frequency", ctypes.c_float),
        ("VIS_reference_amplitude", ctypes.c_float),
        ("VIS_frequency_1", ctypes.c_float),
        ("VIS_frequency_2", ctypes.c_float),
        ("VIS_amplitude_1", ctypes.c_float),
        ("VIS_amplitude_2", ctypes.c_float),
    ]
    type_id = 1722
    type_name = "VISUAL_GRATING_RESPONSE"
    type_hash = 0xEC3B454D
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_GRIP_COMMAND(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("grip_pos", ctypes.c_double * 1),
        ("velocity", ctypes.c_double * 1),
        ("force", ctypes.c_double * 1),
        ("impedance", ctypes.c_double * 1),
        ("controlMask", ctypes.c_short * 4),
        ("src", ctypes.c_int),
        ("reserved", ctypes.c_int),
    ]
    type_id = 1730
    type_name = "GRIP_COMMAND"
    type_hash = 0xBF72EDD9
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_GRIP_FINISHED_COMMAND(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("grip_pos", ctypes.c_double * 1),
        ("velocity", ctypes.c_double * 1),
        ("force", ctypes.c_double * 1),
        ("impedance", ctypes.c_double * 1),
        ("controlMask", ctypes.c_short * 4),
        ("effector", ctypes.c_char * 64),
    ]
    type_id = 1731
    type_name = "GRIP_FINISHED_COMMAND"
    type_hash = 0xCF816219
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_GRIPPER_FEEDBACK(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("grip_pos", ctypes.c_double * 1),
        ("velocity", ctypes.c_double * 1),
        ("force", ctypes.c_double * 5),
        ("effector", ctypes.c_char * 64),
    ]
    type_id = 1732
    type_name = "GRIPPER_FEEDBACK"
    type_hash = 0x04151851
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_MUJOCO_SENSOR(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("motor_pos", ctypes.c_double * 32),
        ("motor_vel", ctypes.c_double * 32),
        ("motor_torque", ctypes.c_double * 32),
        ("joint_pos", ctypes.c_double * 64),
        ("joint_vel", ctypes.c_double * 64),
        ("contact", ctypes.c_double * 32),
    ]
    type_id = 1733
    type_name = "MUJOCO_SENSOR"
    type_hash = 0x039A0342
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_MUJOCO_CMD(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("ref_pos", ctypes.c_double * 1),
        ("ref_vel", ctypes.c_double * 1),
        ("gain_pos", ctypes.c_double * 1),
        ("gain_vel", ctypes.c_double * 1),
        ("ref_pos_enabled", ctypes.c_short),
        ("ref_vel_enabled", ctypes.c_short),
        ("gain_pos_enabled", ctypes.c_short),
        ("gain_vel_enabled", ctypes.c_short),
    ]
    type_id = 1734
    type_name = "MUJOCO_CMD"
    type_hash = 0x2EDC7184
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_MUJOCO_MOVE(pyrtma.MessageData):
    _fields_ = [
        ("mocap_id", ctypes.c_uint),
        ("link_objects", ctypes.c_uint),
        ("pos", ctypes.c_double * 3),
    ]
    type_id = 1735
    type_name = "MUJOCO_MOVE"
    type_hash = 0xAE45F2C1
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_MUJOCO_MSG(pyrtma.MessageData):
    _fields_ = [("message", ctypes.c_char * 256), ("position", ctypes.c_int)]
    type_id = 1736
    type_name = "MUJOCO_MSG"
    type_hash = 0xC30E46BD
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_MUJOCO_GHOST_COLOR(pyrtma.MessageData):
    _fields_ = [("color_id", ctypes.c_double)]
    type_id = 1737
    type_name = "MUJOCO_GHOST_COLOR"
    type_hash = 0x17B273A2
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_MUJOCO_OBJMOVE(pyrtma.MessageData):
    _fields_ = [
        ("obj_id", ctypes.c_uint),
        ("padding", ctypes.c_int),
        ("pos", ctypes.c_double * 3),
        ("orientation", ctypes.c_double * 3),
    ]
    type_id = 1738
    type_name = "MUJOCO_OBJMOVE"
    type_hash = 0x79C166D4
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_OPENHAND_CMD(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("motor_sp", ctypes.c_ushort * 2),
        ("reserved1", ctypes.c_ushort * 2),
        ("mode", ctypes.c_ubyte),
        ("reserved2", ctypes.c_ubyte * 3),
    ]
    type_id = 1740
    type_name = "OPENHAND_CMD"
    type_hash = 0xCCE31B3F
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_OPENHAND_SENS(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("motor_pos", ctypes.c_ushort),
        ("force", ctypes.c_ushort),
    ]
    type_id = 1741
    type_name = "OPENHAND_SENS"
    type_hash = 0xAA0EFA7A
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_PRENSILIA_SENS(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("stream_type", ctypes.c_ushort),
        ("current", ctypes.c_ushort * 5),
        ("position", ctypes.c_ushort * 5),
        ("external", ctypes.c_ushort * 7),
        ("tension", ctypes.c_ushort * 5),
        ("reserved", ctypes.c_ushort),
    ]
    type_id = 1742
    type_name = "PRENSILIA_SENS"
    type_hash = 0x51634D58
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_PRENSILIA_CMD(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("mode", ctypes.c_short * 5),
        ("command", ctypes.c_short * 5),
    ]
    type_id = 1743
    type_name = "PRENSILIA_CMD"
    type_hash = 0x49B7B23A
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_TABLE_LOAD_CELLS(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("left_plate", ctypes.c_double * 4),
        ("left_plate_mean", ctypes.c_double),
        ("center_plate", ctypes.c_double * 4),
        ("center_plate_mean", ctypes.c_double),
        ("right_plate", ctypes.c_double * 4),
        ("right_plate_mean", ctypes.c_double),
    ]
    type_id = 1744
    type_name = "TABLE_LOAD_CELLS"
    type_hash = 0x193EBC3C
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_REZERO_GRIPPER_SENSORS(pyrtma.MessageData):
    _fields_ = []
    type_id = 1745
    type_name = "REZERO_GRIPPER_SENSORS"
    type_hash = 0x8A1D75FD
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_SINGLETACT_DATA(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("raw_analog", ctypes.c_int * 3),
        ("padding", ctypes.c_int),
        ("force", ctypes.c_double * 3),
    ]
    type_id = 1760
    type_name = "SINGLETACT_DATA"
    type_hash = 0xBBE040C8
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_GET_USER_RESPONSE(pyrtma.MessageData):
    _fields_ = []
    type_id = 1761
    type_name = "GET_USER_RESPONSE"
    type_hash = 0xBA8BF5D0
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_USER_RESPONSE_L(pyrtma.MessageData):
    _fields_ = []
    type_id = 1762
    type_name = "USER_RESPONSE_L"
    type_hash = 0xBEC98D42
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_USER_RESPONSE_R(pyrtma.MessageData):
    _fields_ = []
    type_id = 1763
    type_name = "USER_RESPONSE_R"
    type_hash = 0x5C5E79E3
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_RAW_SPIKECOUNT(pyrtma.MessageData):
    _fields_ = [
        ("source_index", ctypes.c_int),
        ("reserved", ctypes.c_int),
        ("source_timestamp", ctypes.c_double),
        ("count_interval", ctypes.c_double),
        ("counts", ctypes.c_ubyte * 640),
    ]
    type_id = 1800
    type_name = "RAW_SPIKECOUNT"
    type_hash = 0xFE0B9C40
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_SPM_SPIKECOUNT(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("source_timestamp", ctypes.c_double * 2),
        ("count_interval", ctypes.c_double),
        ("counts", SPIKE_COUNT_DATA_TYPE * 1280),
    ]
    type_id = 1801
    type_name = "SPM_SPIKECOUNT"
    type_hash = 0x2A978201
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_SPIKE_SNIPPET(pyrtma.MessageData):
    _fields_ = [("ss", SPIKE_SNIPPET_TYPE * 25)]
    type_id = 1802
    type_name = "SPIKE_SNIPPET"
    type_hash = 0x29C42FA4
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_RAW_CTSDATA(pyrtma.MessageData):
    _fields_ = [
        ("source_index", ctypes.c_int),
        ("num_chans_enabled", ctypes.c_int),
        ("source_timestamp", ctypes.c_double),
        ("data", ctypes.c_short * 1280),
    ]
    type_id = 1803
    type_name = "RAW_CTSDATA"
    type_hash = 0x6C2F79C9
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_SPM_CTSDATA(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("source_timestamp", ctypes.c_double * 2),
        ("data", ctypes.c_short * 5120),
    ]
    type_id = 1804
    type_name = "SPM_CTSDATA"
    type_hash = 0x064717F9
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_REJECTED_SNIPPET(pyrtma.MessageData):
    _fields_ = [("rs", REJECTED_SNIPPET_TYPE * 25)]
    type_id = 1805
    type_name = "REJECTED_SNIPPET"
    type_hash = 0xC469DD13
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_RAW_DIGITAL_EVENT(pyrtma.MessageData):
    _fields_ = [
        ("source_index", ctypes.c_int),
        ("channel", ctypes.c_int),
        ("source_timestamp", ctypes.c_double),
        ("data", ctypes.c_uint * 2),
    ]
    type_id = 1806
    type_name = "RAW_DIGITAL_EVENT"
    type_hash = 0x0FE8F4BE
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_SPM_DIGITAL_EVENT(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("source_index", ctypes.c_int * 10),
        ("source_timestamp", ctypes.c_double * 2),
        ("byte0", ctypes.c_ushort * 10),
        ("byte1", ctypes.c_ushort * 10),
        ("num_events", ctypes.c_int),
        ("reserved", ctypes.c_int),
    ]
    type_id = 1807
    type_name = "SPM_DIGITAL_EVENT"
    type_hash = 0x9DCEAACE
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_STIM_SYNC_EVENT(pyrtma.MessageData):
    _fields_ = [
        ("source_index", ctypes.c_int),
        ("channel", ctypes.c_int),
        ("source_timestamp", ctypes.c_double),
        ("data", ctypes.c_uint),
        ("reserved", ctypes.c_int),
    ]
    type_id = 1808
    type_name = "STIM_SYNC_EVENT"
    type_hash = 0x5CA0E471
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_STIM_UPDATE_EVENT(pyrtma.MessageData):
    _fields_ = [
        ("source_index", ctypes.c_int),
        ("channel", ctypes.c_int),
        ("source_timestamp", ctypes.c_double),
        ("data", ctypes.c_uint),
        ("reserved", ctypes.c_int),
    ]
    type_id = 1809
    type_name = "STIM_UPDATE_EVENT"
    type_hash = 0x8FDD49AC
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_CENTRALRECORD(pyrtma.MessageData):
    _fields_ = [
        ("pathname", ctypes.c_char * 256),
        ("subjectID", ctypes.c_char * 128),
        ("record", ctypes.c_uint),
        ("reserved", ctypes.c_uint),
    ]
    type_id = 1810
    type_name = "CENTRALRECORD"
    type_hash = 0xCCBD685C
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_RAW_ANALOGDATA(pyrtma.MessageData):
    _fields_ = [
        ("source_index", ctypes.c_int),
        ("num_chans_enabled", ctypes.c_int),
        ("source_timestamp", ctypes.c_double),
        ("data", ctypes.c_short * 160),
    ]
    type_id = 1811
    type_name = "RAW_ANALOGDATA"
    type_hash = 0x74D7D50E
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_SPM_ANALOGDATA(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("source_timestamp", ctypes.c_double * 2),
        ("data", ctypes.c_short * 640),
    ]
    type_id = 1812
    type_name = "SPM_ANALOGDATA"
    type_hash = 0xB95489A0
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_RAW_SPIKECOUNT_N256(pyrtma.MessageData):
    _fields_ = [
        ("source_index", ctypes.c_int),
        ("reserved", ctypes.c_int),
        ("source_timestamp", ctypes.c_double),
        ("count_interval", ctypes.c_double),
        ("counts", ctypes.c_ubyte * 1280),
    ]
    type_id = 1815
    type_name = "RAW_SPIKECOUNT_N256"
    type_hash = 0xA22828C4
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_RAW_CTSDATA_N256(pyrtma.MessageData):
    _fields_ = [
        ("source_index", ctypes.c_int),
        ("num_chans_enabled", ctypes.c_int),
        ("source_timestamp", ctypes.c_double),
        ("data", ctypes.c_short * 2560),
    ]
    type_id = 1816
    type_name = "RAW_CTSDATA_N256"
    type_hash = 0x774EEA69
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_MECH_SYNC_EVENT(pyrtma.MessageData):
    _fields_ = [
        ("source_index", ctypes.c_int),
        ("channel", ctypes.c_int),
        ("source_timestamp", ctypes.c_double),
        ("data", ctypes.c_uint),
        ("reserved", ctypes.c_int),
    ]
    type_id = 1817
    type_name = "MECH_SYNC_EVENT"
    type_hash = 0x8C95C514
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_SAMPLE_GENERATED(pyrtma.MessageData):
    _fields_ = [("header", MSG_HEADER), ("source_timestamp", ctypes.c_double * 2)]
    type_id = 1820
    type_name = "SAMPLE_GENERATED"
    type_hash = 0x8251D87A
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_XIPP_EMG_DATA_RAW(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("num_chans_per_headstage", ctypes.c_int * 2),
        ("source_timestamp", ctypes.c_uint * 20),
        ("data", ctypes.c_float * 1280),
    ]
    type_id = 1830
    type_name = "XIPP_EMG_DATA_RAW"
    type_hash = 0xEE31A079
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_MYO_EMG_DATA(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("source_timestamp", ctypes.c_ulonglong * 4),
        ("data", ctypes.c_int * 32),
    ]
    type_id = 1831
    type_name = "MYO_EMG_DATA"
    type_hash = 0xEBD682DA
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_MYO_KIN_DATA(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("source_timestamp", ctypes.c_ulonglong),
        ("orientation", ctypes.c_float * 4),
        ("gyroscope", ctypes.c_float * 3),
        ("acceleration", ctypes.c_float * 3),
    ]
    type_id = 1832
    type_name = "MYO_KIN_DATA"
    type_hash = 0x8EB71C1E
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_INPUT_DOF_DATA(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("tag", ctypes.c_char * 64),
        ("dof_vals", ctypes.c_double * 30),
    ]
    type_id = 1850
    type_name = "INPUT_DOF_DATA"
    type_hash = 0x62E1C089
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_DATAGLOVE(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("tag", ctypes.c_char * 64),
        ("raw_vals", ctypes.c_double * 18),
        ("calib_vals", ctypes.c_double * 18),
        ("gesture", ctypes.c_int),
        ("glovetype", ctypes.c_int),
        ("hand", ctypes.c_int),
        ("reserved", ctypes.c_int),
    ]
    type_id = 1860
    type_name = "DATAGLOVE"
    type_hash = 0xEBA13DD4
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_OPTITRACK_RIGID_BODY(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("ID", ctypes.c_int),
        ("reserved", ctypes.c_int),
        ("pos", ctypes.c_double * 3),
        ("orient", ctypes.c_double * 3),
        ("timestamp", ctypes.c_double),
        ("name", ctypes.c_char * 128),
    ]
    type_id = 1861
    type_name = "OPTITRACK_RIGID_BODY"
    type_hash = 0x249F100E
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_TASK_STATE_CONFIG(pyrtma.MessageData):
    _fields_ = [
        ("state_name", ctypes.c_char * 128),
        ("target", ctypes.c_double * 30),
        ("active_assist_weight", ctypes.c_double * 6),
        ("brain_control_weight", ctypes.c_double * 6),
        ("passive_assist_weight", ctypes.c_double * 6),
        ("jstick_control_weight", ctypes.c_double * 6),
        ("gain", ctypes.c_double * 6),
        ("threshold", ctypes.c_double * 6),
        ("force_targ", ctypes.c_double * 9),
        ("dZ_gain", ctypes.c_double),
        ("force_thresh", ctypes.c_double),
        ("active_override", ctypes.c_int * 30),
        ("use_for_calib", ctypes.c_int),
        ("result_code", ctypes.c_int),
        ("stim_enable", ctypes.c_int),
        ("force_calib", ctypes.c_int),
        ("targ_set", ctypes.c_int),
        ("targ_idx", ctypes.c_int),
        ("gripperControlMask", ctypes.c_short * 4),
    ]
    type_id = 1900
    type_name = "TASK_STATE_CONFIG"
    type_hash = 0xEF302FEB
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_PHASE_RESULT(pyrtma.MessageData):
    _fields_ = [
        ("state_name", ctypes.c_char * 128),
        ("target", ctypes.c_double * 30),
        ("active_assist_weight", ctypes.c_double * 6),
        ("brain_control_weight", ctypes.c_double * 6),
        ("passive_assist_weight", ctypes.c_double * 6),
        ("jstick_control_weight", ctypes.c_double * 6),
        ("gain", ctypes.c_double * 6),
        ("threshold", ctypes.c_double * 6),
        ("force_targ", ctypes.c_double * 9),
        ("dZ_gain", ctypes.c_double),
        ("force_thresh", ctypes.c_double),
        ("active_override", ctypes.c_int * 30),
        ("use_for_calib", ctypes.c_int),
        ("result_code", ctypes.c_int),
        ("stim_enable", ctypes.c_int),
        ("force_calib", ctypes.c_int),
        ("targ_set", ctypes.c_int),
        ("targ_idx", ctypes.c_int),
        ("gripperControlMask", ctypes.c_short * 4),
    ]
    type_id = 1901
    type_name = "PHASE_RESULT"
    type_hash = 0xA4DBF676
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_EXTRACTION_RESPONSE(pyrtma.MessageData):
    _fields_ = [
        ("src", ctypes.c_int),
        ("decoder_type", ctypes.c_char * 128),
        ("decoder_loc", ctypes.c_char * 256),
    ]
    type_id = 1902
    type_name = "EXTRACTION_RESPONSE"
    type_hash = 0xE59BDBC9
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_NORMALIZATION_FACTOR(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("factor", ctypes.c_double),
        ("length", ctypes.c_double),
    ]
    type_id = 1903
    type_name = "NORMALIZATION_FACTOR"
    type_hash = 0xF1331A30
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_TRIAL_METADATA(pyrtma.MessageData):
    _fields_ = [
        ("session_num", ctypes.c_int),
        ("set_num", ctypes.c_int),
        ("block_num", ctypes.c_int),
        ("trial_num", ctypes.c_int),
        ("session_type", ctypes.c_char * 128),
        ("subject_id", ctypes.c_char * 64),
    ]
    type_id = 1904
    type_name = "TRIAL_METADATA"
    type_hash = 0x7B840F7E
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_EXTRACTION_REQUEST(pyrtma.MessageData):
    _fields_ = []
    type_id = 1905
    type_name = "EXTRACTION_REQUEST"
    type_hash = 0xC5E9A882
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_UPDATE_UNIT_STATE(pyrtma.MessageData):
    _fields_ = [("unit_idx", ctypes.c_int), ("enabled", ctypes.c_int)]
    type_id = 1906
    type_name = "UPDATE_UNIT_STATE"
    type_hash = 0x572242D2
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_DISABLED_UNITS(pyrtma.MessageData):
    _fields_ = [("header", MSG_HEADER), ("disabled_units", ctypes.c_ubyte * 1280)]
    type_id = 1907
    type_name = "DISABLED_UNITS"
    type_hash = 0x45A88747
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_TRIAL_END(pyrtma.MessageData):
    _fields_ = []
    type_id = 1910
    type_name = "TRIAL_END"
    type_hash = 0xE939AEEE
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_REP_START(pyrtma.MessageData):
    _fields_ = [("rep_num", ctypes.c_int), ("reserved", ctypes.c_int)]
    type_id = 1911
    type_name = "REP_START"
    type_hash = 0x3577491D
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_REP_END(pyrtma.MessageData):
    _fields_ = []
    type_id = 1912
    type_name = "REP_END"
    type_hash = 0xC5A8C883
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_EXEC_SCORE(pyrtma.MessageData):
    _fields_ = [("passed", ctypes.c_int), ("failed", ctypes.c_int)]
    type_id = 1913
    type_name = "EXEC_SCORE"
    type_hash = 0x89AF766F
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_FLIP_THAT_BUCKET_DATA(pyrtma.MessageData):
    _fields_ = [("state_name", ctypes.c_char * 128), ("state_value", ctypes.c_double)]
    type_id = 1914
    type_name = "FLIP_THAT_BUCKET_DATA"
    type_hash = 0x2F8BE5C6
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_SET_START(pyrtma.MessageData):
    _fields_ = [
        ("session_num", ctypes.c_int),
        ("set_num", ctypes.c_int),
        ("session_type", ctypes.c_char * 128),
        ("subject_id", ctypes.c_char * 64),
    ]
    type_id = 1915
    type_name = "SET_START"
    type_hash = 0x7AED5960
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_SET_END(pyrtma.MessageData):
    _fields_ = [
        ("session_num", ctypes.c_int),
        ("set_num", ctypes.c_int),
        ("session_type", ctypes.c_char * 128),
        ("subject_id", ctypes.c_char * 64),
    ]
    type_id = 1916
    type_name = "SET_END"
    type_hash = 0x2296961E
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_BLOCK_START(pyrtma.MessageData):
    _fields_ = [("block_num", ctypes.c_int)]
    type_id = 1917
    type_name = "BLOCK_START"
    type_hash = 0x4D2D21A9
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_BLOCK_END(pyrtma.MessageData):
    _fields_ = []
    type_id = 1918
    type_name = "BLOCK_END"
    type_hash = 0x32334BDE
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_SET_METADATA(pyrtma.MessageData):
    _fields_ = [
        ("session_id", ctypes.c_int),
        ("num_blocks", ctypes.c_int),
        ("num_trials", ctypes.c_int),
        ("stim_trigger", ctypes.c_int),
        ("subject_response", ctypes.c_int),
        ("reserved", ctypes.c_int),
        ("session_type", ctypes.c_char * 128),
        ("subject_id", ctypes.c_char * 64),
        ("data_path", ctypes.c_char * 128),
    ]
    type_id = 1919
    type_name = "SET_METADATA"
    type_hash = 0xD1CE6C27
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_EXEC_PAUSE(pyrtma.MessageData):
    _fields_ = [("pause", ctypes.c_int), ("reserved", ctypes.c_int)]
    type_id = 1950
    type_name = "EXEC_PAUSE"
    type_hash = 0x9BC79432
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_EM_ADAPT_NOW(pyrtma.MessageData):
    _fields_ = []
    type_id = 2000
    type_name = "EM_ADAPT_NOW"
    type_hash = 0xF4C724CE
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_EM_CONFIGURATION(pyrtma.MessageData):
    _fields_ = [
        ("type", ctypes.c_int),
        ("reserved", ctypes.c_int),
        ("data", ctypes.c_char * 256),
    ]
    type_id = 2001
    type_name = "EM_CONFIGURATION"
    type_hash = 0x1B33A091
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_TDMS_CREATE(pyrtma.MessageData):
    _fields_ = [
        ("pathname", ctypes.c_char * 256),
        ("pathname_length", ctypes.c_int),
        ("reserved", ctypes.c_int),
    ]
    type_id = 2002
    type_name = "TDMS_CREATE"
    type_hash = 0xC871D6ED
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_RF_REPORT(pyrtma.MessageData):
    _fields_ = [
        ("handp", ctypes.c_char * 48),
        ("handd", ctypes.c_char * 18),
        ("head", ctypes.c_char * 13),
        ("arms", ctypes.c_char * 20),
        ("padding", ctypes.c_char),
        ("tag", ctypes.c_int),
        ("flipframe", ctypes.c_int),
    ]
    type_id = 2003
    type_name = "RF_REPORT"
    type_hash = 0xC38B43D7
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_PICDISPLAY(pyrtma.MessageData):
    _fields_ = [("filename", ctypes.c_char * 256), ("timer", ctypes.c_double)]
    type_id = 2004
    type_name = "PICDISPLAY"
    type_hash = 0x80770904
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_STIMDATA(pyrtma.MessageData):
    _fields_ = [
        ("ConfigID", ctypes.c_double * 12),
        ("Vmax", ctypes.c_double * 12),
        ("Vmin", ctypes.c_double * 12),
        ("interphase", ctypes.c_double * 12),
    ]
    type_id = 2005
    type_name = "STIMDATA"
    type_hash = 0x3A3217BC
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_SEAIO_OUT(pyrtma.MessageData):
    _fields_ = [("bit", ctypes.c_int), ("value", ctypes.c_int)]
    type_id = 2007
    type_name = "SEAIO_OUT"
    type_hash = 0x82125073
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_ATIforcesensor(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("Fx", ctypes.c_double),
        ("Fy", ctypes.c_double),
        ("Fz", ctypes.c_double),
        ("Tz", ctypes.c_double),
        ("Tx", ctypes.c_double),
        ("Ty", ctypes.c_double),
    ]
    type_id = 2008
    type_name = "ATIforcesensor"
    type_hash = 0x75ACD4A0
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_TACTOR_CMD(pyrtma.MessageData):
    _fields_ = []
    type_id = 2009
    type_name = "TACTOR_CMD"
    type_hash = 0x94F231B3
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_HSTLOG(pyrtma.MessageData):
    _fields_ = [
        ("len", ctypes.c_int),
        ("reserved", ctypes.c_int),
        ("log", ctypes.c_char * 512),
    ]
    type_id = 3000
    type_name = "HSTLOG"
    type_hash = 0x04BAE81E
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_STIM_INTERVAL(pyrtma.MessageData):
    _fields_ = [("interval", ctypes.c_int)]
    type_id = 3001
    type_name = "STIM_INTERVAL"
    type_hash = 0x8EBA9820
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_USER_SHOT_L(pyrtma.MessageData):
    _fields_ = []
    type_id = 3002
    type_name = "USER_SHOT_L"
    type_hash = 0xCE9EB33E
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_USER_SHOT_R(pyrtma.MessageData):
    _fields_ = []
    type_id = 3003
    type_name = "USER_SHOT_R"
    type_hash = 0xF6E9E29A
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_STIM_THRESH(pyrtma.MessageData):
    _fields_ = [
        ("threshold", ctypes.c_double),
        ("channel", ctypes.c_int),
        ("reserved", ctypes.c_int),
    ]
    type_id = 3004
    type_name = "STIM_THRESH"
    type_hash = 0x25D0436B
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_GAME_ROUND_INFO(pyrtma.MessageData):
    _fields_ = [("num_intervals", ctypes.c_int), ("stim_interval", ctypes.c_int)]
    type_id = 3005
    type_name = "GAME_ROUND_INFO"
    type_hash = 0x3C98BC4C
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_USER_SHOT(pyrtma.MessageData):
    _fields_ = [("interval", ctypes.c_int)]
    type_id = 3006
    type_name = "USER_SHOT"
    type_hash = 0x21ADC5B1
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_GAME_HEARTBEAT_REQUEST(pyrtma.MessageData):
    _fields_ = []
    type_id = 3007
    type_name = "GAME_HEARTBEAT_REQUEST"
    type_hash = 0xE5EEBD52
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_GAME_HEARTBEAT_RESPONSE(pyrtma.MessageData):
    _fields_ = []
    type_id = 3008
    type_name = "GAME_HEARTBEAT_RESPONSE"
    type_hash = 0x3DE2B158
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_PLAYSOUND(pyrtma.MessageData):
    _fields_ = [("filename", ctypes.c_char * 256)]
    type_id = 3100
    type_name = "PLAYSOUND"
    type_hash = 0xEF86C9A0
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_PLAYVIDEO(pyrtma.MessageData):
    _fields_ = [("filename", ctypes.c_char * 256)]
    type_id = 3102
    type_name = "PLAYVIDEO"
    type_hash = 0xD690550B
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_START_TIMED_RECORDING(pyrtma.MessageData):
    _fields_ = [("start_command", ctypes.c_double)]
    type_id = 3101
    type_name = "START_TIMED_RECORDING"
    type_hash = 0xC33E869C
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_AJA_CONFIG(pyrtma.MessageData):
    _fields_ = [
        ("record", ctypes.c_int),
        ("stop", ctypes.c_int),
        ("filename", ctypes.c_char * 256),
    ]
    type_id = 3200
    type_name = "AJA_CONFIG"
    type_hash = 0x54F3974A
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_AJA_TIMECODE(pyrtma.MessageData):
    _fields_ = [("header", MSG_HEADER), ("timecode", ctypes.c_char * 128)]
    type_id = 3201
    type_name = "AJA_TIMECODE"
    type_hash = 0x7096CAEC
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_AJA_STATUS(pyrtma.MessageData):
    _fields_ = [
        ("status", ctypes.c_int),
        ("reserved", ctypes.c_int),
        ("clipname", ctypes.c_char * 256),
    ]
    type_id = 3202
    type_name = "AJA_STATUS"
    type_hash = 0x0FBFD360
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_AJA_STATUS_REQUEST(pyrtma.MessageData):
    _fields_ = []
    type_id = 3203
    type_name = "AJA_STATUS_REQUEST"
    type_hash = 0x31F5B0EF
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_FOFIX_PROMPT(pyrtma.MessageData):
    _fields_ = [
        ("note", ctypes.c_int),
        ("length", ctypes.c_int),
        ("target_time", ctypes.c_double),
        ("game_time", ctypes.c_double),
    ]
    type_id = 3600
    type_name = "FOFIX_PROMPT"
    type_hash = 0x7E937D27
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_FOFIX_INPUT(pyrtma.MessageData):
    _fields_ = [
        ("notes_strummed", ctypes.c_int * 5),
        ("reserved", ctypes.c_short),
        ("hit_note", ctypes.c_short),
        ("game_time", ctypes.c_double),
    ]
    type_id = 3601
    type_name = "FOFIX_INPUT"
    type_hash = 0x85EA0A37
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_FOFIX_MISSED(pyrtma.MessageData):
    _fields_ = [
        ("note", ctypes.c_int),
        ("reserved", ctypes.c_int),
        ("target_time", ctypes.c_double),
        ("game_time", ctypes.c_double),
    ]
    type_id = 3602
    type_name = "FOFIX_MISSED"
    type_hash = 0xF261D00B
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_FOFIX_STIM(pyrtma.MessageData):
    _fields_ = [("note", ctypes.c_int), ("condition", ctypes.c_int)]
    type_id = 3603
    type_name = "FOFIX_STIM"
    type_hash = 0x25236BD2
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_FOFIX_KEY(pyrtma.MessageData):
    _fields_ = [("note", ctypes.c_int), ("enabled", ctypes.c_int)]
    type_id = 3604
    type_name = "FOFIX_KEY"
    type_hash = 0xF4BAAED3
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_CERESTIM_CONFIG_MODULE(pyrtma.MessageData):
    _fields_ = [
        ("configID", ctypes.c_int * 16),
        ("amp1", ctypes.c_int * 16),
        ("amp2", ctypes.c_int * 16),
        ("frequency", ctypes.c_int * 16),
        ("num_modules", ctypes.c_int),
        ("afcf", ctypes.c_int),
        ("width1", ctypes.c_int),
        ("width2", ctypes.c_int),
        ("interphase", ctypes.c_int),
    ]
    type_id = 4000
    type_name = "CERESTIM_CONFIG_MODULE"
    type_hash = 0x5C5AB75C
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_CERESTIM_CONFIG_CHAN_PRESAFETY(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("stop", ctypes.c_int),
        ("numChans", ctypes.c_int),
        ("channel", ctypes.c_int * 64),
        ("pattern", ctypes.c_int * 64),
        ("reps", ctypes.c_int),
        ("pause_t", ctypes.c_float),
    ]
    type_id = 4001
    type_name = "CERESTIM_CONFIG_CHAN_PRESAFETY"
    type_hash = 0x657E8EA3
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_CERESTIM_CONFIG_CHAN(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("stop", ctypes.c_int),
        ("numChans", ctypes.c_int),
        ("channel", ctypes.c_int * 12),
        ("pattern", ctypes.c_int * 12),
        ("reps", ctypes.c_int),
        ("pause_t", ctypes.c_float),
    ]
    type_id = 4002
    type_name = "CERESTIM_CONFIG_CHAN"
    type_hash = 0x3C5AA623
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_CERESTIM_ERROR(pyrtma.MessageData):
    _fields_ = [("error", ctypes.c_int), ("config", ctypes.c_int)]
    type_id = 4003
    type_name = "CERESTIM_ERROR"
    type_hash = 0x4DBE506F
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_CERESTIM_ALIVE(pyrtma.MessageData):
    _fields_ = []
    type_id = 4004
    type_name = "CERESTIM_ALIVE"
    type_hash = 0x5C38CB13
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_CS_TRAIN_END(pyrtma.MessageData):
    _fields_ = []
    type_id = 4005
    type_name = "CS_TRAIN_END"
    type_hash = 0x3BE6B63C
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_CERESTIM_CONFIG_CHAN_PRESAFETY_ARBITRARY(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("stop", ctypes.c_int),
        ("numChans", ctypes.c_int),
        ("channel", ctypes.c_int * 64),
        ("pattern", ctypes.c_int * 64),
        ("reps", ctypes.c_int),
        ("reserved", ctypes.c_int),
        ("pathname", ctypes.c_char * 256),
        ("pathlength", ctypes.c_int),
    ]
    type_id = 4006
    type_name = "CERESTIM_CONFIG_CHAN_PRESAFETY_ARBITRARY"
    type_hash = 0xF7683A07
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_CERESTIM_CONFIG_CHAN_ARBITRARY(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("stop", ctypes.c_int),
        ("pathname", ctypes.c_char * 256),
        ("pathlength", ctypes.c_int),
        ("pulselength", ctypes.c_int),
    ]
    type_id = 4007
    type_name = "CERESTIM_CONFIG_CHAN_ARBITRARY"
    type_hash = 0xDFEF8BB0
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_CS_ARBITRARY_CLOSE(pyrtma.MessageData):
    _fields_ = []
    type_id = 4008
    type_name = "CS_ARBITRARY_CLOSE"
    type_hash = 0x62BAB05E
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_STIM_VOLTAGE_MONITOR_DATA(pyrtma.MessageData):
    _fields_ = [
        ("sample_rate", ctypes.c_int),
        ("pulse_count", ctypes.c_int),
        ("daq_channel", ctypes.c_int * 26),
        ("array_channel", ctypes.c_int * 26),
        ("daq_timestamp", ctypes.c_double * 26),
        ("voltage", ctypes.c_float * 2600),
        ("interphase", ctypes.c_float * 26),
        ("Vmax", ctypes.c_float * 26),
        ("Vmin", ctypes.c_float * 26),
    ]
    type_id = 4009
    type_name = "STIM_VOLTAGE_MONITOR_DATA"
    type_hash = 0xCEF055CC
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_STIM_VOLTAGE_MONITOR_DIGITAL_DATA(pyrtma.MessageData):
    _fields_ = [
        ("stim_sync_event", ctypes.c_float * 30),
        ("stim_param_event", ctypes.c_float * 5),
        ("padding", ctypes.c_float),
        ("spm_daq_delta_t", ctypes.c_double),
    ]
    type_id = 4010
    type_name = "STIM_VOLTAGE_MONITOR_DIGITAL_DATA"
    type_hash = 0x1DBB26B3
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_VOLTAGE_MONITOR_STATUS(pyrtma.MessageData):
    _fields_ = [("msg_length", ctypes.c_int), ("msg", ctypes.c_char * 1024)]
    type_id = 4011
    type_name = "VOLTAGE_MONITOR_STATUS"
    type_hash = 0xD8DEB26E
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_STIM_DUTYCYCLE_TIME(pyrtma.MessageData):
    _fields_ = [("dutycycle_time", ctypes.c_double)]
    type_id = 4012
    type_name = "STIM_DUTYCYCLE_TIME"
    type_hash = 0x13E7C64A
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_STIM_TRIAL_DURATION(pyrtma.MessageData):
    _fields_ = [("trial_duration", ctypes.c_double)]
    type_id = 4013
    type_name = "STIM_TRIAL_DURATION"
    type_hash = 0x526EDF6A
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_CERESTIM_HEARTBEAT(pyrtma.MessageData):
    _fields_ = [("type", ctypes.c_int)]
    type_id = 4014
    type_name = "CERESTIM_HEARTBEAT"
    type_hash = 0xC3BDCC1E
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_CERESTIM_HEARTBEAT_RQST(pyrtma.MessageData):
    _fields_ = []
    type_id = 4015
    type_name = "CERESTIM_HEARTBEAT_RQST"
    type_hash = 0x2B0A6017
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_CERESTIM_SAFETY_ALIVE(pyrtma.MessageData):
    _fields_ = []
    type_id = 4016
    type_name = "CERESTIM_SAFETY_ALIVE"
    type_hash = 0x399AAF24
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_CERESTIM_SAFETY_ALIVE_RQST(pyrtma.MessageData):
    _fields_ = []
    type_id = 4017
    type_name = "CERESTIM_SAFETY_ALIVE_RQST"
    type_hash = 0xCDA394A5
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_NATURAL_RESPONSE(pyrtma.MessageData):
    _fields_ = [("a", ctypes.c_double)]
    type_id = 4050
    type_name = "NATURAL_RESPONSE"
    type_hash = 0x275F91D6
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_DEPTH_RESPONSE(pyrtma.MessageData):
    _fields_ = [
        ("idx", ctypes.c_int),
        ("enabled", ctypes.c_int),
        ("depth", ctypes.c_char * 256),
    ]
    type_id = 4051
    type_name = "DEPTH_RESPONSE"
    type_hash = 0x185093C9
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_PAIN_RESPONSE(pyrtma.MessageData):
    _fields_ = [("a", ctypes.c_double)]
    type_id = 4052
    type_name = "PAIN_RESPONSE"
    type_hash = 0x6A633F6E
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_OVERALL_INTENSITY_RESPONSE(pyrtma.MessageData):
    _fields_ = [("a", ctypes.c_double)]
    type_id = 4053
    type_name = "OVERALL_INTENSITY_RESPONSE"
    type_hash = 0xFA9BABCB
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_OTHER_RESPONSE(pyrtma.MessageData):
    _fields_ = [
        ("enabled", ctypes.c_int),
        ("reserved", ctypes.c_int),
        ("a", ctypes.c_double),
    ]
    type_id = 4054
    type_name = "OTHER_RESPONSE"
    type_hash = 0xA1E76823
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_MECH_RESPONSE(pyrtma.MessageData):
    _fields_ = [
        ("idx", ctypes.c_int),
        ("enabled", ctypes.c_int),
        ("a", ctypes.c_double),
        ("quality", ctypes.c_char * 256),
    ]
    type_id = 4055
    type_name = "MECH_RESPONSE"
    type_hash = 0xB62F923D
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_MOVE_RESPONSE(pyrtma.MessageData):
    _fields_ = [
        ("idx", ctypes.c_int),
        ("enabled", ctypes.c_int),
        ("a", ctypes.c_double),
        ("quality", ctypes.c_char * 256),
    ]
    type_id = 4056
    type_name = "MOVE_RESPONSE"
    type_hash = 0x53835705
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_TINGLE_RESPONSE(pyrtma.MessageData):
    _fields_ = [
        ("idx", ctypes.c_int),
        ("enabled", ctypes.c_int),
        ("a", ctypes.c_double),
        ("quality", ctypes.c_char * 256),
    ]
    type_id = 4057
    type_name = "TINGLE_RESPONSE"
    type_hash = 0xB6A8C7F5
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_TEMP_RESPONSE(pyrtma.MessageData):
    _fields_ = [("a", ctypes.c_double), ("quality", ctypes.c_char * 256)]
    type_id = 4058
    type_name = "TEMP_RESPONSE"
    type_hash = 0x140B73C5
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_DIR_PIXEL_COORDS(pyrtma.MessageData):
    _fields_ = [
        ("img", ctypes.c_char * 32),
        ("moreMsgs", ctypes.c_int),
        ("reserved", ctypes.c_int),
        ("pixels", ctypes.c_float * 64),
    ]
    type_id = 4059
    type_name = "DIR_PIXEL_COORDS"
    type_hash = 0x5F0A710E
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_PIXEL_COORDS(pyrtma.MessageData):
    _fields_ = [
        ("img", ctypes.c_char * 32),
        ("moreMsgs", ctypes.c_int),
        ("reserved", ctypes.c_int),
        ("pixels", ctypes.c_float * 64),
    ]
    type_id = 4060
    type_name = "PIXEL_COORDS"
    type_hash = 0x1393BA61
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_HOTSPOT_COORDS(pyrtma.MessageData):
    _fields_ = [
        ("img", ctypes.c_char * 128),
        ("x", ctypes.c_double),
        ("y", ctypes.c_double),
    ]
    type_id = 4061
    type_name = "HOTSPOT_COORDS"
    type_hash = 0xEB94C2BF
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_CLEAR_LINE(pyrtma.MessageData):
    _fields_ = [("img", ctypes.c_char * 256)]
    type_id = 4062
    type_name = "CLEAR_LINE"
    type_hash = 0x8A0D6C36
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_CLEAR_HOTSPOT(pyrtma.MessageData):
    _fields_ = [("img", ctypes.c_char * 256)]
    type_id = 4063
    type_name = "CLEAR_HOTSPOT"
    type_hash = 0x660462A8
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_ADD_SENSATION(pyrtma.MessageData):
    _fields_ = []
    type_id = 4064
    type_name = "ADD_SENSATION"
    type_hash = 0xEE9958C1
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_SLIDER_DATA(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("type", ctypes.c_int),
        ("channel", ctypes.c_int),
        ("value", ctypes.c_int),
        ("time", ctypes.c_int),
    ]
    type_id = 4065
    type_name = "SLIDER_DATA"
    type_hash = 0xB50721B2
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_USER_DEFINED_STIM(pyrtma.MessageData):
    _fields_ = [
        ("frequency", ctypes.c_int),
        ("amplitude", ctypes.c_int * 3),
        ("channel", ctypes.c_int * 3),
    ]
    type_id = 4067
    type_name = "USER_DEFINED_STIM"
    type_hash = 0xA2E9E802
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_USER_BEHAVIOUR(pyrtma.MessageData):
    _fields_ = [
        ("current_trial", ctypes.c_int),
        ("current_screen", ctypes.c_char * 256),
        ("current_object", ctypes.c_char * 256),
        ("left_canvas", ctypes.c_int * 2),
        ("right_canvas", ctypes.c_int * 2),
        ("frequency", ctypes.c_int),
        ("freq_choice", ctypes.c_int),
        ("bio", ctypes.c_int),
        ("drag", ctypes.c_int),
        ("amplitude", ctypes.c_int * 3),
        ("satisfaction", ctypes.c_int),
        ("certainty", ctypes.c_int),
        ("chosen_object", ctypes.c_char * 256),
        ("object_quest", ctypes.c_int * 6),
        ("affective_quest", ctypes.c_int * 5),
    ]
    type_id = 4068
    type_name = "USER_BEHAVIOUR"
    type_hash = 0xF4E606FB
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_STOP_STIM(pyrtma.MessageData):
    _fields_ = [("stop_stim", ctypes.c_int)]
    type_id = 4069
    type_name = "STOP_STIM"
    type_hash = 0xEC132898
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_PAUSE_TRIAL(pyrtma.MessageData):
    _fields_ = [("pause_trial", ctypes.c_int)]
    type_id = 4070
    type_name = "PAUSE_TRIAL"
    type_hash = 0xC7EEB83C
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_CST_LAMBDA(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("lambda", ctypes.c_float),
        ("k", ctypes.c_int),
        ("cursor_pos", ctypes.c_double),
    ]
    type_id = 4100
    type_name = "CST_LAMBDA"
    type_hash = 0x0F51DCE7
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_CST_SETTINGS(pyrtma.MessageData):
    _fields_ = [
        ("sweep_rate", ctypes.c_double),
        ("vis_bins", ctypes.c_int),
        ("stim_bins", ctypes.c_int),
    ]
    type_id = 4101
    type_name = "CST_SETTINGS"
    type_hash = 0x2BF099F4
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_STIM_PRES_CONFIG(pyrtma.MessageData):
    _fields_ = [("filename", ctypes.c_char * 256), ("randomization", ctypes.c_int)]
    type_id = 4150
    type_name = "STIM_PRES_CONFIG"
    type_hash = 0x768880BF
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_STIM_PRES_PHASE_END(pyrtma.MessageData):
    _fields_ = [("phase_rep_end", ctypes.c_int)]
    type_id = 4151
    type_name = "STIM_PRES_PHASE_END"
    type_hash = 0xC90A3F28
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_STIM_PRESENT(pyrtma.MessageData):
    _fields_ = [
        ("stim_filename", ctypes.c_char * 256),
        ("stim_state_name", ctypes.c_char * 256),
        ("stim_display_time", ctypes.c_double),
        ("stim_start_delay", ctypes.c_double),
    ]
    type_id = 4152
    type_name = "STIM_PRESENT"
    type_hash = 0x0F4965CB
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_STIM_PRES_STATUS(pyrtma.MessageData):
    _fields_ = [("pause_resume", ctypes.c_int), ("stop", ctypes.c_int)]
    type_id = 4153
    type_name = "STIM_PRES_STATUS"
    type_hash = 0x4984FDFE
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_STIM_CONFIG_TYPE(pyrtma.MessageData):
    _fields_ = [("stim_configtype", ctypes.c_char * 128)]
    type_id = 4154
    type_name = "STIM_CONFIG_TYPE"
    type_hash = 0xC7513C8A
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_DEKA_ACI_RESPONSE(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("ACI_1", DEKA_CAN_MSG),
        ("ACI_2", DEKA_CAN_MSG),
        ("ACI_3", DEKA_CAN_MSG),
    ]
    type_id = 4200
    type_name = "DEKA_ACI_RESPONSE"
    type_hash = 0x5D5CEA8F
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_DEKA_SENSOR(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("position_msg_1", DEKA_CAN_MSG),
        ("position_msg_2", DEKA_CAN_MSG),
        ("motor_pos", ctypes.c_double * 7),
        ("motor_current", ctypes.c_double * 7),
        ("mode", ctypes.c_int),
        ("sync", ctypes.c_int),
        ("grip", ctypes.c_int),
        ("padding", ctypes.c_int),
    ]
    type_id = 4201
    type_name = "DEKA_SENSOR"
    type_hash = 0xFC372CE8
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_DEKA_CAN_TOGGLE(pyrtma.MessageData):
    _fields_ = [("toggle", ctypes.c_int), ("padding", ctypes.c_int)]
    type_id = 4202
    type_name = "DEKA_CAN_TOGGLE"
    type_hash = 0x9851DB7D
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_DEKA_CAN_GRIP_TOGGLE(pyrtma.MessageData):
    _fields_ = [("toggle", ctypes.c_int), ("padding", ctypes.c_int)]
    type_id = 4203
    type_name = "DEKA_CAN_GRIP_TOGGLE"
    type_hash = 0x90C549B4
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_DEKA_CAN_EXIT(pyrtma.MessageData):
    _fields_ = [("exit", ctypes.c_int), ("padding", ctypes.c_int)]
    type_id = 4204
    type_name = "DEKA_CAN_EXIT"
    type_hash = 0x57F16F40
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_DEKA_HAND_SENSOR(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("position_msg_1", DEKA_CAN_MSG),
        ("position_msg_2", DEKA_CAN_MSG),
        ("force_msg_1", DEKA_CAN_MSG),
        ("force_msg_2", DEKA_CAN_MSG),
        ("force_msg_3", DEKA_CAN_MSG),
        ("motor_pos", ctypes.c_double * 6),
        ("contact", ctypes.c_double * 13),
        ("mode", ctypes.c_int),
        ("status", ctypes.c_int * 13),
        ("sync", ctypes.c_int),
        ("grip", ctypes.c_int),
    ]
    type_id = 4205
    type_name = "DEKA_HAND_SENSOR"
    type_hash = 0x941D6442
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_DEKA_HAND_JSTICK_CMD(pyrtma.MessageData):
    _fields_ = [("header", MSG_HEADER), ("ref_vel", ctypes.c_double * 6)]
    type_id = 4206
    type_name = "DEKA_HAND_JSTICK_CMD"
    type_hash = 0x38E6EAFB
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_RH_GRIPPER_SENSOR(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("finger_1", RH_FINGER_DATA),
        ("finger_2", RH_FINGER_DATA),
        ("finger_3", RH_FINGER_DATA),
        ("motor_info", DYNAMIXEL_INFO),
    ]
    type_id = 4207
    type_name = "RH_GRIPPER_SENSOR"
    type_hash = 0xE143ACF4
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_KUKA_JOINT_COMMAND(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("joint_dest", ctypes.c_double * 7),
        ("err_move_mode", ctypes.c_int),
        ("err_input_cap", ctypes.c_int * 6),
        ("err_cart_wall_eef", ctypes.c_int * 6),
        ("err_cart_wall_arm", ctypes.c_int * 6),
        ("err_jpos_stop", ctypes.c_int * 3),
    ]
    type_id = 4208
    type_name = "KUKA_JOINT_COMMAND"
    type_hash = 0x44C06DEC
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_KUKA_FEEDBACK(pyrtma.MessageData):
    _fields_ = [
        ("header", MSG_HEADER),
        ("time", ctypes.c_double),
        ("joint_pos", ctypes.c_double * 7),
        ("cart_pos", ctypes.c_double * 3),
        ("cart_angle", ctypes.c_double * 3),
        ("cart_pos_vel", ctypes.c_double * 3),
        ("cart_rot_vel", ctypes.c_double * 3),
        ("cart_force", ctypes.c_double * 3),
        ("cart_torque", ctypes.c_double * 3),
        ("dest_delta_t", ctypes.c_double),
        ("mode", ctypes.c_int),
        ("reserved", ctypes.c_int),
    ]
    type_id = 4209
    type_name = "KUKA_FEEDBACK"
    type_hash = 0x800E739A
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_KUKA_EXIT(pyrtma.MessageData):
    _fields_ = [("exit", ctypes.c_int), ("padding", ctypes.c_int)]
    type_id = 4210
    type_name = "KUKA_EXIT"
    type_hash = 0x762B7D36
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_KUKA_PTP_JOINT(pyrtma.MessageData):
    _fields_ = [("joint_pos", ctypes.c_double * 7)]
    type_id = 4211
    type_name = "KUKA_PTP_JOINT"
    type_hash = 0xBAFE0DDF
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_KUKA_DEBUG(pyrtma.MessageData):
    _fields_ = [("joint_pos", ctypes.c_double * 7)]
    type_id = 4212
    type_name = "KUKA_DEBUG"
    type_hash = 0x951FCE38
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_VEML7700_SYNC(pyrtma.MessageData):
    _fields_ = [("timestamp", ctypes.c_ulong), ("sync_idx", ctypes.c_ulong)]
    type_id = 4248
    type_name = "VEML7700_SYNC"
    type_hash = 0xFC1F71EB
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_VEML7700_DATA(pyrtma.MessageData):
    _fields_ = [
        ("timestamp", ctypes.c_ulong),
        ("sample_id", ctypes.c_ulong),
        ("lux", ctypes.c_float),
    ]
    type_id = 4249
    type_name = "VEML7700_DATA"
    type_hash = 0xA8A9380A
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_VEML7700_PING(pyrtma.MessageData):
    _fields_ = []
    type_id = 4250
    type_name = "VEML7700_PING"
    type_hash = 0x3FFA1271
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_VEML7700_PONG(pyrtma.MessageData):
    _fields_ = []
    type_id = 4251
    type_name = "VEML7700_PONG"
    type_hash = 0x4998A3D5
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_VEML7700_START(pyrtma.MessageData):
    _fields_ = []
    type_id = 4252
    type_name = "VEML7700_START"
    type_hash = 0xF328CE11
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_VEML7700_STOP(pyrtma.MessageData):
    _fields_ = []
    type_id = 4253
    type_name = "VEML7700_STOP"
    type_hash = 0x38498A38
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_VEML7700_RESET(pyrtma.MessageData):
    _fields_ = []
    type_id = 4254
    type_name = "VEML7700_RESET"
    type_hash = 0x4F76EBAB
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_VEML7700_CONNECT(pyrtma.MessageData):
    _fields_ = []
    type_id = 4256
    type_name = "VEML7700_CONNECT"
    type_hash = 0xE46F8AA5
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_MECH_STIM_CONFIGURE(pyrtma.MessageData):
    _fields_ = [
        ("source", ctypes.c_int),
        ("length", ctypes.c_int),
        ("str", ctypes.c_char * 1024),
    ]
    type_id = 4260
    type_name = "MECH_STIM_CONFIGURE"
    type_hash = 0x88972740
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_MECH_STIM_RESET(pyrtma.MessageData):
    _fields_ = []
    type_id = 4261
    type_name = "MECH_STIM_RESET"
    type_hash = 0xDD701D58
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_MECH_STIM_STAGE(pyrtma.MessageData):
    _fields_ = []
    type_id = 4262
    type_name = "MECH_STIM_STAGE"
    type_hash = 0xCCB8239B
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_MECH_STIM_WAITING(pyrtma.MessageData):
    _fields_ = []
    type_id = 4263
    type_name = "MECH_STIM_WAITING"
    type_hash = 0x620383B4
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_MECH_STIM_TRIGGER(pyrtma.MessageData):
    _fields_ = []
    type_id = 4264
    type_name = "MECH_STIM_TRIGGER"
    type_hash = 0x73F7880C
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_MECH_STIM_CANCEL(pyrtma.MessageData):
    _fields_ = []
    type_id = 4265
    type_name = "MECH_STIM_CANCEL"
    type_hash = 0x8B50F7E0
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_MECH_STIM_DONE(pyrtma.MessageData):
    _fields_ = []
    type_id = 4266
    type_name = "MECH_STIM_DONE"
    type_hash = 0x803D4ECA
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_MECH_STIM_ERROR(pyrtma.MessageData):
    _fields_ = []
    type_id = 4267
    type_name = "MECH_STIM_ERROR"
    type_hash = 0x5518C5D1
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF_UC_MECH_STIM_CONFIGURE(pyrtma.MessageData):
    _fields_ = [
        ("amp", ctypes.c_double),
        ("speed", ctypes.c_double),
        ("offset", ctypes.c_double),
        ("phase", ctypes.c_double),
        ("duration", ctypes.c_double),
        ("type", ctypes.c_int),
        ("padding", ctypes.c_int),
    ]
    type_id = 4268
    type_name = "UC_MECH_STIM_CONFIGURE"
    type_hash = 0x273BC481
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF__RESERVED_004300(pyrtma.MessageData):
    _fields_ = []
    type_id = 4300
    type_name = "_RESERVED_004300"
    type_hash = 0xCE2B74C1
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF__RESERVED_004360(pyrtma.MessageData):
    _fields_ = []
    type_id = 4360
    type_name = "_RESERVED_004360"
    type_hash = 0xA4288CBE
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF__RESERVED_004361(pyrtma.MessageData):
    _fields_ = []
    type_id = 4361
    type_name = "_RESERVED_004361"
    type_hash = 0xCA551012
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF__RESERVED_004362(pyrtma.MessageData):
    _fields_ = []
    type_id = 4362
    type_name = "_RESERVED_004362"
    type_hash = 0x1FB4158D
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF__RESERVED_004363(pyrtma.MessageData):
    _fields_ = []
    type_id = 4363
    type_name = "_RESERVED_004363"
    type_hash = 0x6A1BE0D0
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF__RESERVED_004364(pyrtma.MessageData):
    _fields_ = []
    type_id = 4364
    type_name = "_RESERVED_004364"
    type_hash = 0xC0CA6671
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF__RESERVED_004365(pyrtma.MessageData):
    _fields_ = []
    type_id = 4365
    type_name = "_RESERVED_004365"
    type_hash = 0x862615BB
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF__RESERVED_004366(pyrtma.MessageData):
    _fields_ = []
    type_id = 4366
    type_name = "_RESERVED_004366"
    type_hash = 0xA703073C
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF__RESERVED_004367(pyrtma.MessageData):
    _fields_ = []
    type_id = 4367
    type_name = "_RESERVED_004367"
    type_hash = 0x442ABB7F
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF__RESERVED_004368(pyrtma.MessageData):
    _fields_ = []
    type_id = 4368
    type_name = "_RESERVED_004368"
    type_hash = 0x8CD5099C
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF__RESERVED_004369(pyrtma.MessageData):
    _fields_ = []
    type_id = 4369
    type_name = "_RESERVED_004369"
    type_hash = 0xC91AF2B3
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF__RESERVED_004370(pyrtma.MessageData):
    _fields_ = []
    type_id = 4370
    type_name = "_RESERVED_004370"
    type_hash = 0x1A8E353C
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF__RESERVED_004371(pyrtma.MessageData):
    _fields_ = []
    type_id = 4371
    type_name = "_RESERVED_004371"
    type_hash = 0x09248DD4
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF__RESERVED_004372(pyrtma.MessageData):
    _fields_ = []
    type_id = 4372
    type_name = "_RESERVED_004372"
    type_hash = 0x9880225F
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF__RESERVED_004373(pyrtma.MessageData):
    _fields_ = []
    type_id = 4373
    type_name = "_RESERVED_004373"
    type_hash = 0xA9E362D1
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF__RESERVED_004374(pyrtma.MessageData):
    _fields_ = []
    type_id = 4374
    type_name = "_RESERVED_004374"
    type_hash = 0xF76E2A3C
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF__RESERVED_004375(pyrtma.MessageData):
    _fields_ = []
    type_id = 4375
    type_name = "_RESERVED_004375"
    type_hash = 0xB01FBB58
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF__RESERVED_004376(pyrtma.MessageData):
    _fields_ = []
    type_id = 4376
    type_name = "_RESERVED_004376"
    type_hash = 0xC4D255ED
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF__RESERVED_004377(pyrtma.MessageData):
    _fields_ = []
    type_id = 4377
    type_name = "_RESERVED_004377"
    type_hash = 0x5DB1542A
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


@pyrtma.message_def
class MDF__RESERVED_004378(pyrtma.MessageData):
    _fields_ = []
    type_id = 4378
    type_name = "_RESERVED_004378"
    type_hash = 0xD323D536
    type_source = "C:\\git\\pyrtma\\tests\\test_msg_defs\\test_defs.yaml"


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
    MJ_VR_MAX_MOCAP_COUNT = 32
    MJ_VR_MAX_BODY_COUNT = 64
    MJ_VR_MAX_MOTOR_COUNT = 32
    MJ_VR_MAX_JOINT_COUNT = 64
    MJ_VR_MAX_JOINT_DOF = 128
    MJ_VR_MAX_CONTACT_COUNT = 32
    MJ_VR_MAX_TENDON_COUNT = 32
    MAX_SPIKE_SOURCES = 2
    MAX_SPIKE_SOURCES_N256 = 1
    MAX_SPIKE_CHANS_PER_SOURCE = 128
    MAX_SPIKE_CHANS_PER_SOURCE_N256 = 256
    MAX_COINCIDENT_SPIKES = 45
    MAX_ANALOG_CHANS = 16
    MAX_UNITS_PER_CHAN = 5
    MAX_TOTAL_SPIKE_CHANS_PER_SOURCE = 640
    MAX_TOTAL_SPIKE_CHANS_PER_SOURCE_N256 = 1280
    MAX_TOTAL_SPIKE_CHANS = 1280
    MAX_TOTAL_SPIKE_CHANS_N256 = 1280
    LFPSAMPLES_PER_HEARTBEAT = 10
    ANALOGSAMPLES_PER_HEARTBEAT = 10
    RAW_COUNTS_PER_SAMPLE = 2
    SAMPLE_LENGTH_MS = 20
    SAMPLE_LENGTH = 0.02
    SNIPPETS_PER_MESSAGE = 25
    SAMPLES_PER_SNIPPET = 48
    MAX_DIG_PER_SAMPLE = 10
    MAX_DATAGLOVE_SENSORS = 18
    NUM_DOMAINS = 6
    MAX_COMMAND_DIMS = 30
    MPL_RAW_PERCEPT_DIMS = 54
    NUM_STIM_CHANS = 64
    SHAM_STIM_CHANS = 32
    MAX_STIM_CHANS_ON = 12
    PULSE_TRAIN_SIZE = 101
    MAX_CS_CONFIGS = 16
    NUM_SPIKES_PER_STIM_MSG = 26
    MAX_XIPP_EEG_HEADSTAGES = 2
    MAX_XIPP_CHANS = 64
    MAX_XIPP_ANALOG_CHANS = 32
    XIPP_SAMPLES_PER_MSG = 20
    MAX_MYO_EMG_CHANS = 8
    MYO_SAMPLES_PER_MSG = 4
    GRIP_DIMS_R = 1
    GRIP_DIMS_L = 1
    MAX_GRIP_DIMS = 9
    MAX_GRIPPER_DIMS = 1
    MAX_GRIPPER_JOINT_ANGLES = 5
    MAX_GRIPPER_FORCES = 5
    MJ_MAX_MOTOR = 1
    MJ_MAX_JOINT = 5
    MJ_MAX_CONTACT = 5
    NoResult = -1
    SuccessfulTrial = 1
    BadTrial = 2
    ManualProceed = 4
    ManualFail = 8
    HX_DEKA_LUKE_CONTACT_COUNT = 13
    HX_LUKE_MOTOR_COUNT = 6
    NUM_FINGERS = 3
    NUM_SENSORS_PER_FINGER = 9
    NUM_SENSORS_PALM = 11
    NUM_TAKKTILE = 38
    NUM_ENCODERS = 3
    NUM_SERVOS = 4
    NUM_DYNAMIXEL = 4
    MECH_STIM_SINE = 1
    MECH_STIM_RAMP_AND_HOLD = 2
    DEKA_DOF_COUNT = 7
    KUKA_DOF_COUNT = 7
    PRENSILIA_DOF = 5
    PRENSILIA_EXT_SENSORS = 7
    TAG_LENGTH = 64
    MPL_AT_ARM_EPV_FING_JV = 0
    MPL_AT_ARM_EPV_FING_JP = 1
    MPL_AT_ARM_JV_FING_JP = 2
    MPL_AT_ALL_JV = 3
    MPL_AT_ALL_JP = 4
    MPL_AT_ARM_EPP_FING_JP = 5
    TFD_FREQ_BINS = 20
    DEFAULT_MM_IP = "localhost:7111"


class _HID:
    LOCAL_HOST = 0
    ALL_HOSTS = 32767


class _MID:
    MESSAGE_MANAGER = 0
    QUICK_LOGGER = 5
    MUJOCO_VR_MODULE = 61
    JSTICK_COMMAND = 10
    COMBINER = 11
    CEREBUS = 12
    RAW_LOGGER = 16
    INPUT_TRANSFORM = 20
    RPPL_RECORD = 21
    CENTRAL = 22
    EXTRACTION = 30
    MYO = 31
    MECH_STIM_MODULE = 39
    MPL_CONTROL = 40
    GRIP_CONTROL = 41
    DEKA_CAN_MODULE = 42
    DEKA_ACI_RESPONSE = 43
    DEKA_DISPLAY = 44
    PSYCHTLBX = 46
    STIM_PRESENT = 48
    ACTIVE_ASSIST = 50
    KUKA_DISPLAY = 51
    ROBOTICS_FEEDBACK_INTEGRATOR = 52
    KUKA_INTERFACE_MODULE = 53
    KUKA_JOINT_COMMAND_DISPLAY = 54
    KUKA_DIAGNOSTICS = 55
    FORCE_PLATFORM = 58
    FORCE_PLATFORM_DISPLAY = 59
    MPL_FEEDBACK = 60
    AJA_CONTROL = 65
    SEAIOCONTROL = 66
    EXECUTIVE = 70
    COMMENT_MANAGER = 71
    FLIP_THAT_BUCKET_MESSENGER = 74
    VOLTAGE_MONITOR_GUI = 76
    VOLTAGE_MONITOR = 77
    ATIsensor = 78
    FOFIX = 79
    STIM_THRESH_GAME = 80
    MESSAGERATES = 81
    VISUAL_GRATING = 85
    BIASMODULE = 86
    CURSOR = 87
    RHR_COMMAND_MODULE = 88
    RHR_SENSOR_MODULE = 89
    SOUNDPLAYER = 90
    RFDISPLAY = 91
    RFACTIVITY = 92
    ImageDisplayer = 93
    FLIP_THAT_BUCKET = 94
    STIM_SAFETY_MODULE = 95
    SENSOR_STIM_TRANS_MODULE = 96
    CERESTIM_CONTROL = 97
    SENSE_TOUCH_INTERFACE = 98
    SENSOR_STIM_TRANSFORM_PY = 99


class _aliases:
    MODULE_ID = MODULE_ID
    HOST_ID = HOST_ID
    MSG_TYPE = MSG_TYPE
    MSG_COUNT = MSG_COUNT
    SPIKE_COUNT_DATA_TYPE = SPIKE_COUNT_DATA_TYPE


class _SDF:
    RTMA_MSG_HEADER = RTMA_MSG_HEADER
    MJVR_MSG_HEADER = MJVR_MSG_HEADER
    MSG_HEADER = MSG_HEADER
    SPIKE_SNIPPET_TYPE = SPIKE_SNIPPET_TYPE
    REJECTED_SNIPPET_TYPE = REJECTED_SNIPPET_TYPE
    DEKA_CAN_MSG = DEKA_CAN_MSG
    RH_FINGER_DATA = RH_FINGER_DATA
    DYNAMIXEL_INFO = DYNAMIXEL_INFO


class _MT:
    EXIT = 0
    KILL = 1
    ACKNOWLEDGE = 2
    CONNECT = 13
    DISCONNECT = 14
    SUBSCRIBE = 15
    UNSUBSCRIBE = 16
    PAUSE_SUBSCRIPTION = 85
    RESUME_SUBSCRIPTION = 86
    FAIL_SUBSCRIBE = 6
    FAILED_MESSAGE = 8
    FORCE_DISCONNECT = 82
    MODULE_READY = 26
    SAVE_MESSAGE_LOG = 56
    TIMING_MESSAGE = 80
    MUJOCO_VR_REQUEST_STATE = 4213
    MUJOCO_VR_REPLY_STATE = 4214
    MUJOCO_VR_MOCAP_MOVE = 4215
    MUJOCO_VR_MOTOR_MOVE = 4216
    MUJOCO_VR_REQUEST_MODEL_INFO = 4217
    MUJOCO_VR_REPLY_MODEL_INFO = 4218
    MUJOCO_VR_REQUEST_LINK_STATE = 4219
    MUJOCO_VR_REPLY_LINK_STATE = 4220
    MUJOCO_VR_LINK = 4221
    MUJOCO_VR_LINK_RESET = 4222
    MUJOCO_VR_FLOATBODY_MOVE = 4223
    MUJOCO_VR_RESET = 4224
    MUJOCO_VR_RELOAD = 4225
    MUJOCO_VR_LOAD_MODEL = 4226
    MUJOCO_VR_PAUSE = 4227
    MUJOCO_VR_RESUME = 4228
    MUJOCO_VR_MOTOR_CTRL = 4229
    MUJOCO_VR_MOTOR_CONFIG = 4230
    MUJOCO_VR_SET_RGBA = 4231
    MUJOCO_VR_MSG = 4232
    JSON_CONFIG = 1200
    FINISHED_COMMAND = 1700
    CONTROL_SPACE_FEEDBACK = 1701
    CONTROL_SPACE_COMMAND = 1702
    MPL_RAW_PERCEPT = 1703
    BIAS_COMMAND = 1704
    MPL_REBIASED_SENSORDATA = 1705
    CONTROL_SPACE_FEEDBACK_RHR_GRIPPER = 1706
    CONTROL_SPACE_POS_COMMAND = 1710
    MPL_SEGMENT_PERCEPTS = 1711
    WAM_FEEDBACK = 1712
    IMPEDANCE_COMMAND = 1713
    EXECUTIVE_CTRL = 1714
    CURSOR_FEEDBACK = 1720
    VISUAL_GRATING_BUILD = 1721
    VISUAL_GRATING_RESPONSE = 1722
    GRIP_COMMAND = 1730
    GRIP_FINISHED_COMMAND = 1731
    GRIPPER_FEEDBACK = 1732
    MUJOCO_SENSOR = 1733
    MUJOCO_CMD = 1734
    MUJOCO_MOVE = 1735
    MUJOCO_MSG = 1736
    MUJOCO_GHOST_COLOR = 1737
    MUJOCO_OBJMOVE = 1738
    OPENHAND_CMD = 1740
    OPENHAND_SENS = 1741
    PRENSILIA_SENS = 1742
    PRENSILIA_CMD = 1743
    TABLE_LOAD_CELLS = 1744
    REZERO_GRIPPER_SENSORS = 1745
    SINGLETACT_DATA = 1760
    GET_USER_RESPONSE = 1761
    USER_RESPONSE_L = 1762
    USER_RESPONSE_R = 1763
    RAW_SPIKECOUNT = 1800
    SPM_SPIKECOUNT = 1801
    SPIKE_SNIPPET = 1802
    RAW_CTSDATA = 1803
    SPM_CTSDATA = 1804
    REJECTED_SNIPPET = 1805
    RAW_DIGITAL_EVENT = 1806
    SPM_DIGITAL_EVENT = 1807
    STIM_SYNC_EVENT = 1808
    STIM_UPDATE_EVENT = 1809
    CENTRALRECORD = 1810
    RAW_ANALOGDATA = 1811
    SPM_ANALOGDATA = 1812
    RAW_SPIKECOUNT_N256 = 1815
    RAW_CTSDATA_N256 = 1816
    MECH_SYNC_EVENT = 1817
    SAMPLE_GENERATED = 1820
    XIPP_EMG_DATA_RAW = 1830
    MYO_EMG_DATA = 1831
    MYO_KIN_DATA = 1832
    INPUT_DOF_DATA = 1850
    DATAGLOVE = 1860
    OPTITRACK_RIGID_BODY = 1861
    TASK_STATE_CONFIG = 1900
    PHASE_RESULT = 1901
    EXTRACTION_RESPONSE = 1902
    NORMALIZATION_FACTOR = 1903
    TRIAL_METADATA = 1904
    EXTRACTION_REQUEST = 1905
    UPDATE_UNIT_STATE = 1906
    DISABLED_UNITS = 1907
    TRIAL_END = 1910
    REP_START = 1911
    REP_END = 1912
    EXEC_SCORE = 1913
    FLIP_THAT_BUCKET_DATA = 1914
    SET_START = 1915
    SET_END = 1916
    BLOCK_START = 1917
    BLOCK_END = 1918
    SET_METADATA = 1919
    EXEC_PAUSE = 1950
    EM_ADAPT_NOW = 2000
    EM_CONFIGURATION = 2001
    TDMS_CREATE = 2002
    RF_REPORT = 2003
    PICDISPLAY = 2004
    STIMDATA = 2005
    SEAIO_OUT = 2007
    ATIforcesensor = 2008
    TACTOR_CMD = 2009
    HSTLOG = 3000
    STIM_INTERVAL = 3001
    USER_SHOT_L = 3002
    USER_SHOT_R = 3003
    STIM_THRESH = 3004
    GAME_ROUND_INFO = 3005
    USER_SHOT = 3006
    GAME_HEARTBEAT_REQUEST = 3007
    GAME_HEARTBEAT_RESPONSE = 3008
    PLAYSOUND = 3100
    PLAYVIDEO = 3102
    START_TIMED_RECORDING = 3101
    AJA_CONFIG = 3200
    AJA_TIMECODE = 3201
    AJA_STATUS = 3202
    AJA_STATUS_REQUEST = 3203
    FOFIX_PROMPT = 3600
    FOFIX_INPUT = 3601
    FOFIX_MISSED = 3602
    FOFIX_STIM = 3603
    FOFIX_KEY = 3604
    CERESTIM_CONFIG_MODULE = 4000
    CERESTIM_CONFIG_CHAN_PRESAFETY = 4001
    CERESTIM_CONFIG_CHAN = 4002
    CERESTIM_ERROR = 4003
    CERESTIM_ALIVE = 4004
    CS_TRAIN_END = 4005
    CERESTIM_CONFIG_CHAN_PRESAFETY_ARBITRARY = 4006
    CERESTIM_CONFIG_CHAN_ARBITRARY = 4007
    CS_ARBITRARY_CLOSE = 4008
    STIM_VOLTAGE_MONITOR_DATA = 4009
    STIM_VOLTAGE_MONITOR_DIGITAL_DATA = 4010
    VOLTAGE_MONITOR_STATUS = 4011
    STIM_DUTYCYCLE_TIME = 4012
    STIM_TRIAL_DURATION = 4013
    CERESTIM_HEARTBEAT = 4014
    CERESTIM_HEARTBEAT_RQST = 4015
    CERESTIM_SAFETY_ALIVE = 4016
    CERESTIM_SAFETY_ALIVE_RQST = 4017
    NATURAL_RESPONSE = 4050
    DEPTH_RESPONSE = 4051
    PAIN_RESPONSE = 4052
    OVERALL_INTENSITY_RESPONSE = 4053
    OTHER_RESPONSE = 4054
    MECH_RESPONSE = 4055
    MOVE_RESPONSE = 4056
    TINGLE_RESPONSE = 4057
    TEMP_RESPONSE = 4058
    DIR_PIXEL_COORDS = 4059
    PIXEL_COORDS = 4060
    HOTSPOT_COORDS = 4061
    CLEAR_LINE = 4062
    CLEAR_HOTSPOT = 4063
    ADD_SENSATION = 4064
    SLIDER_DATA = 4065
    USER_DEFINED_STIM = 4067
    USER_BEHAVIOUR = 4068
    STOP_STIM = 4069
    PAUSE_TRIAL = 4070
    CST_LAMBDA = 4100
    CST_SETTINGS = 4101
    STIM_PRES_CONFIG = 4150
    STIM_PRES_PHASE_END = 4151
    STIM_PRESENT = 4152
    STIM_PRES_STATUS = 4153
    STIM_CONFIG_TYPE = 4154
    DEKA_ACI_RESPONSE = 4200
    DEKA_SENSOR = 4201
    DEKA_CAN_TOGGLE = 4202
    DEKA_CAN_GRIP_TOGGLE = 4203
    DEKA_CAN_EXIT = 4204
    DEKA_HAND_SENSOR = 4205
    DEKA_HAND_JSTICK_CMD = 4206
    RH_GRIPPER_SENSOR = 4207
    KUKA_JOINT_COMMAND = 4208
    KUKA_FEEDBACK = 4209
    KUKA_EXIT = 4210
    KUKA_PTP_JOINT = 4211
    KUKA_DEBUG = 4212
    VEML7700_SYNC = 4248
    VEML7700_DATA = 4249
    VEML7700_PING = 4250
    VEML7700_PONG = 4251
    VEML7700_START = 4252
    VEML7700_STOP = 4253
    VEML7700_RESET = 4254
    VEML7700_CONNECT = 4256
    MECH_STIM_CONFIGURE = 4260
    MECH_STIM_RESET = 4261
    MECH_STIM_STAGE = 4262
    MECH_STIM_WAITING = 4263
    MECH_STIM_TRIGGER = 4264
    MECH_STIM_CANCEL = 4265
    MECH_STIM_DONE = 4266
    MECH_STIM_ERROR = 4267
    UC_MECH_STIM_CONFIGURE = 4268
    _RESERVED_004300 = 4300
    _RESERVED_004360 = 4360
    _RESERVED_004361 = 4361
    _RESERVED_004362 = 4362
    _RESERVED_004363 = 4363
    _RESERVED_004364 = 4364
    _RESERVED_004365 = 4365
    _RESERVED_004366 = 4366
    _RESERVED_004367 = 4367
    _RESERVED_004368 = 4368
    _RESERVED_004369 = 4369
    _RESERVED_004370 = 4370
    _RESERVED_004371 = 4371
    _RESERVED_004372 = 4372
    _RESERVED_004373 = 4373
    _RESERVED_004374 = 4374
    _RESERVED_004375 = 4375
    _RESERVED_004376 = 4376
    _RESERVED_004377 = 4377
    _RESERVED_004378 = 4378


class _MDF:
    EXIT = MDF_EXIT
    KILL = MDF_KILL
    ACKNOWLEDGE = MDF_ACKNOWLEDGE
    CONNECT = MDF_CONNECT
    DISCONNECT = MDF_DISCONNECT
    SUBSCRIBE = MDF_SUBSCRIBE
    UNSUBSCRIBE = MDF_UNSUBSCRIBE
    PAUSE_SUBSCRIPTION = MDF_PAUSE_SUBSCRIPTION
    RESUME_SUBSCRIPTION = MDF_RESUME_SUBSCRIPTION
    FAIL_SUBSCRIBE = MDF_FAIL_SUBSCRIBE
    FAILED_MESSAGE = MDF_FAILED_MESSAGE
    FORCE_DISCONNECT = MDF_FORCE_DISCONNECT
    MODULE_READY = MDF_MODULE_READY
    SAVE_MESSAGE_LOG = MDF_SAVE_MESSAGE_LOG
    TIMING_MESSAGE = MDF_TIMING_MESSAGE
    MUJOCO_VR_REQUEST_STATE = MDF_MUJOCO_VR_REQUEST_STATE
    MUJOCO_VR_REPLY_STATE = MDF_MUJOCO_VR_REPLY_STATE
    MUJOCO_VR_MOCAP_MOVE = MDF_MUJOCO_VR_MOCAP_MOVE
    MUJOCO_VR_MOTOR_MOVE = MDF_MUJOCO_VR_MOTOR_MOVE
    MUJOCO_VR_REQUEST_MODEL_INFO = MDF_MUJOCO_VR_REQUEST_MODEL_INFO
    MUJOCO_VR_REPLY_MODEL_INFO = MDF_MUJOCO_VR_REPLY_MODEL_INFO
    MUJOCO_VR_REQUEST_LINK_STATE = MDF_MUJOCO_VR_REQUEST_LINK_STATE
    MUJOCO_VR_REPLY_LINK_STATE = MDF_MUJOCO_VR_REPLY_LINK_STATE
    MUJOCO_VR_LINK = MDF_MUJOCO_VR_LINK
    MUJOCO_VR_LINK_RESET = MDF_MUJOCO_VR_LINK_RESET
    MUJOCO_VR_FLOATBODY_MOVE = MDF_MUJOCO_VR_FLOATBODY_MOVE
    MUJOCO_VR_RESET = MDF_MUJOCO_VR_RESET
    MUJOCO_VR_RELOAD = MDF_MUJOCO_VR_RELOAD
    MUJOCO_VR_LOAD_MODEL = MDF_MUJOCO_VR_LOAD_MODEL
    MUJOCO_VR_PAUSE = MDF_MUJOCO_VR_PAUSE
    MUJOCO_VR_RESUME = MDF_MUJOCO_VR_RESUME
    MUJOCO_VR_MOTOR_CTRL = MDF_MUJOCO_VR_MOTOR_CTRL
    MUJOCO_VR_MOTOR_CONFIG = MDF_MUJOCO_VR_MOTOR_CONFIG
    MUJOCO_VR_SET_RGBA = MDF_MUJOCO_VR_SET_RGBA
    MUJOCO_VR_MSG = MDF_MUJOCO_VR_MSG
    JSON_CONFIG = MDF_JSON_CONFIG
    FINISHED_COMMAND = MDF_FINISHED_COMMAND
    CONTROL_SPACE_FEEDBACK = MDF_CONTROL_SPACE_FEEDBACK
    CONTROL_SPACE_COMMAND = MDF_CONTROL_SPACE_COMMAND
    MPL_RAW_PERCEPT = MDF_MPL_RAW_PERCEPT
    BIAS_COMMAND = MDF_BIAS_COMMAND
    MPL_REBIASED_SENSORDATA = MDF_MPL_REBIASED_SENSORDATA
    CONTROL_SPACE_FEEDBACK_RHR_GRIPPER = MDF_CONTROL_SPACE_FEEDBACK_RHR_GRIPPER
    CONTROL_SPACE_POS_COMMAND = MDF_CONTROL_SPACE_POS_COMMAND
    MPL_SEGMENT_PERCEPTS = MDF_MPL_SEGMENT_PERCEPTS
    WAM_FEEDBACK = MDF_WAM_FEEDBACK
    IMPEDANCE_COMMAND = MDF_IMPEDANCE_COMMAND
    EXECUTIVE_CTRL = MDF_EXECUTIVE_CTRL
    CURSOR_FEEDBACK = MDF_CURSOR_FEEDBACK
    VISUAL_GRATING_BUILD = MDF_VISUAL_GRATING_BUILD
    VISUAL_GRATING_RESPONSE = MDF_VISUAL_GRATING_RESPONSE
    GRIP_COMMAND = MDF_GRIP_COMMAND
    GRIP_FINISHED_COMMAND = MDF_GRIP_FINISHED_COMMAND
    GRIPPER_FEEDBACK = MDF_GRIPPER_FEEDBACK
    MUJOCO_SENSOR = MDF_MUJOCO_SENSOR
    MUJOCO_CMD = MDF_MUJOCO_CMD
    MUJOCO_MOVE = MDF_MUJOCO_MOVE
    MUJOCO_MSG = MDF_MUJOCO_MSG
    MUJOCO_GHOST_COLOR = MDF_MUJOCO_GHOST_COLOR
    MUJOCO_OBJMOVE = MDF_MUJOCO_OBJMOVE
    OPENHAND_CMD = MDF_OPENHAND_CMD
    OPENHAND_SENS = MDF_OPENHAND_SENS
    PRENSILIA_SENS = MDF_PRENSILIA_SENS
    PRENSILIA_CMD = MDF_PRENSILIA_CMD
    TABLE_LOAD_CELLS = MDF_TABLE_LOAD_CELLS
    REZERO_GRIPPER_SENSORS = MDF_REZERO_GRIPPER_SENSORS
    SINGLETACT_DATA = MDF_SINGLETACT_DATA
    GET_USER_RESPONSE = MDF_GET_USER_RESPONSE
    USER_RESPONSE_L = MDF_USER_RESPONSE_L
    USER_RESPONSE_R = MDF_USER_RESPONSE_R
    RAW_SPIKECOUNT = MDF_RAW_SPIKECOUNT
    SPM_SPIKECOUNT = MDF_SPM_SPIKECOUNT
    SPIKE_SNIPPET = MDF_SPIKE_SNIPPET
    RAW_CTSDATA = MDF_RAW_CTSDATA
    SPM_CTSDATA = MDF_SPM_CTSDATA
    REJECTED_SNIPPET = MDF_REJECTED_SNIPPET
    RAW_DIGITAL_EVENT = MDF_RAW_DIGITAL_EVENT
    SPM_DIGITAL_EVENT = MDF_SPM_DIGITAL_EVENT
    STIM_SYNC_EVENT = MDF_STIM_SYNC_EVENT
    STIM_UPDATE_EVENT = MDF_STIM_UPDATE_EVENT
    CENTRALRECORD = MDF_CENTRALRECORD
    RAW_ANALOGDATA = MDF_RAW_ANALOGDATA
    SPM_ANALOGDATA = MDF_SPM_ANALOGDATA
    RAW_SPIKECOUNT_N256 = MDF_RAW_SPIKECOUNT_N256
    RAW_CTSDATA_N256 = MDF_RAW_CTSDATA_N256
    MECH_SYNC_EVENT = MDF_MECH_SYNC_EVENT
    SAMPLE_GENERATED = MDF_SAMPLE_GENERATED
    XIPP_EMG_DATA_RAW = MDF_XIPP_EMG_DATA_RAW
    MYO_EMG_DATA = MDF_MYO_EMG_DATA
    MYO_KIN_DATA = MDF_MYO_KIN_DATA
    INPUT_DOF_DATA = MDF_INPUT_DOF_DATA
    DATAGLOVE = MDF_DATAGLOVE
    OPTITRACK_RIGID_BODY = MDF_OPTITRACK_RIGID_BODY
    TASK_STATE_CONFIG = MDF_TASK_STATE_CONFIG
    PHASE_RESULT = MDF_PHASE_RESULT
    EXTRACTION_RESPONSE = MDF_EXTRACTION_RESPONSE
    NORMALIZATION_FACTOR = MDF_NORMALIZATION_FACTOR
    TRIAL_METADATA = MDF_TRIAL_METADATA
    EXTRACTION_REQUEST = MDF_EXTRACTION_REQUEST
    UPDATE_UNIT_STATE = MDF_UPDATE_UNIT_STATE
    DISABLED_UNITS = MDF_DISABLED_UNITS
    TRIAL_END = MDF_TRIAL_END
    REP_START = MDF_REP_START
    REP_END = MDF_REP_END
    EXEC_SCORE = MDF_EXEC_SCORE
    FLIP_THAT_BUCKET_DATA = MDF_FLIP_THAT_BUCKET_DATA
    SET_START = MDF_SET_START
    SET_END = MDF_SET_END
    BLOCK_START = MDF_BLOCK_START
    BLOCK_END = MDF_BLOCK_END
    SET_METADATA = MDF_SET_METADATA
    EXEC_PAUSE = MDF_EXEC_PAUSE
    EM_ADAPT_NOW = MDF_EM_ADAPT_NOW
    EM_CONFIGURATION = MDF_EM_CONFIGURATION
    TDMS_CREATE = MDF_TDMS_CREATE
    RF_REPORT = MDF_RF_REPORT
    PICDISPLAY = MDF_PICDISPLAY
    STIMDATA = MDF_STIMDATA
    SEAIO_OUT = MDF_SEAIO_OUT
    ATIforcesensor = MDF_ATIforcesensor
    TACTOR_CMD = MDF_TACTOR_CMD
    HSTLOG = MDF_HSTLOG
    STIM_INTERVAL = MDF_STIM_INTERVAL
    USER_SHOT_L = MDF_USER_SHOT_L
    USER_SHOT_R = MDF_USER_SHOT_R
    STIM_THRESH = MDF_STIM_THRESH
    GAME_ROUND_INFO = MDF_GAME_ROUND_INFO
    USER_SHOT = MDF_USER_SHOT
    GAME_HEARTBEAT_REQUEST = MDF_GAME_HEARTBEAT_REQUEST
    GAME_HEARTBEAT_RESPONSE = MDF_GAME_HEARTBEAT_RESPONSE
    PLAYSOUND = MDF_PLAYSOUND
    PLAYVIDEO = MDF_PLAYVIDEO
    START_TIMED_RECORDING = MDF_START_TIMED_RECORDING
    AJA_CONFIG = MDF_AJA_CONFIG
    AJA_TIMECODE = MDF_AJA_TIMECODE
    AJA_STATUS = MDF_AJA_STATUS
    AJA_STATUS_REQUEST = MDF_AJA_STATUS_REQUEST
    FOFIX_PROMPT = MDF_FOFIX_PROMPT
    FOFIX_INPUT = MDF_FOFIX_INPUT
    FOFIX_MISSED = MDF_FOFIX_MISSED
    FOFIX_STIM = MDF_FOFIX_STIM
    FOFIX_KEY = MDF_FOFIX_KEY
    CERESTIM_CONFIG_MODULE = MDF_CERESTIM_CONFIG_MODULE
    CERESTIM_CONFIG_CHAN_PRESAFETY = MDF_CERESTIM_CONFIG_CHAN_PRESAFETY
    CERESTIM_CONFIG_CHAN = MDF_CERESTIM_CONFIG_CHAN
    CERESTIM_ERROR = MDF_CERESTIM_ERROR
    CERESTIM_ALIVE = MDF_CERESTIM_ALIVE
    CS_TRAIN_END = MDF_CS_TRAIN_END
    CERESTIM_CONFIG_CHAN_PRESAFETY_ARBITRARY = (
        MDF_CERESTIM_CONFIG_CHAN_PRESAFETY_ARBITRARY
    )
    CERESTIM_CONFIG_CHAN_ARBITRARY = MDF_CERESTIM_CONFIG_CHAN_ARBITRARY
    CS_ARBITRARY_CLOSE = MDF_CS_ARBITRARY_CLOSE
    STIM_VOLTAGE_MONITOR_DATA = MDF_STIM_VOLTAGE_MONITOR_DATA
    STIM_VOLTAGE_MONITOR_DIGITAL_DATA = MDF_STIM_VOLTAGE_MONITOR_DIGITAL_DATA
    VOLTAGE_MONITOR_STATUS = MDF_VOLTAGE_MONITOR_STATUS
    STIM_DUTYCYCLE_TIME = MDF_STIM_DUTYCYCLE_TIME
    STIM_TRIAL_DURATION = MDF_STIM_TRIAL_DURATION
    CERESTIM_HEARTBEAT = MDF_CERESTIM_HEARTBEAT
    CERESTIM_HEARTBEAT_RQST = MDF_CERESTIM_HEARTBEAT_RQST
    CERESTIM_SAFETY_ALIVE = MDF_CERESTIM_SAFETY_ALIVE
    CERESTIM_SAFETY_ALIVE_RQST = MDF_CERESTIM_SAFETY_ALIVE_RQST
    NATURAL_RESPONSE = MDF_NATURAL_RESPONSE
    DEPTH_RESPONSE = MDF_DEPTH_RESPONSE
    PAIN_RESPONSE = MDF_PAIN_RESPONSE
    OVERALL_INTENSITY_RESPONSE = MDF_OVERALL_INTENSITY_RESPONSE
    OTHER_RESPONSE = MDF_OTHER_RESPONSE
    MECH_RESPONSE = MDF_MECH_RESPONSE
    MOVE_RESPONSE = MDF_MOVE_RESPONSE
    TINGLE_RESPONSE = MDF_TINGLE_RESPONSE
    TEMP_RESPONSE = MDF_TEMP_RESPONSE
    DIR_PIXEL_COORDS = MDF_DIR_PIXEL_COORDS
    PIXEL_COORDS = MDF_PIXEL_COORDS
    HOTSPOT_COORDS = MDF_HOTSPOT_COORDS
    CLEAR_LINE = MDF_CLEAR_LINE
    CLEAR_HOTSPOT = MDF_CLEAR_HOTSPOT
    ADD_SENSATION = MDF_ADD_SENSATION
    SLIDER_DATA = MDF_SLIDER_DATA
    USER_DEFINED_STIM = MDF_USER_DEFINED_STIM
    USER_BEHAVIOUR = MDF_USER_BEHAVIOUR
    STOP_STIM = MDF_STOP_STIM
    PAUSE_TRIAL = MDF_PAUSE_TRIAL
    CST_LAMBDA = MDF_CST_LAMBDA
    CST_SETTINGS = MDF_CST_SETTINGS
    STIM_PRES_CONFIG = MDF_STIM_PRES_CONFIG
    STIM_PRES_PHASE_END = MDF_STIM_PRES_PHASE_END
    STIM_PRESENT = MDF_STIM_PRESENT
    STIM_PRES_STATUS = MDF_STIM_PRES_STATUS
    STIM_CONFIG_TYPE = MDF_STIM_CONFIG_TYPE
    DEKA_ACI_RESPONSE = MDF_DEKA_ACI_RESPONSE
    DEKA_SENSOR = MDF_DEKA_SENSOR
    DEKA_CAN_TOGGLE = MDF_DEKA_CAN_TOGGLE
    DEKA_CAN_GRIP_TOGGLE = MDF_DEKA_CAN_GRIP_TOGGLE
    DEKA_CAN_EXIT = MDF_DEKA_CAN_EXIT
    DEKA_HAND_SENSOR = MDF_DEKA_HAND_SENSOR
    DEKA_HAND_JSTICK_CMD = MDF_DEKA_HAND_JSTICK_CMD
    RH_GRIPPER_SENSOR = MDF_RH_GRIPPER_SENSOR
    KUKA_JOINT_COMMAND = MDF_KUKA_JOINT_COMMAND
    KUKA_FEEDBACK = MDF_KUKA_FEEDBACK
    KUKA_EXIT = MDF_KUKA_EXIT
    KUKA_PTP_JOINT = MDF_KUKA_PTP_JOINT
    KUKA_DEBUG = MDF_KUKA_DEBUG
    VEML7700_SYNC = MDF_VEML7700_SYNC
    VEML7700_DATA = MDF_VEML7700_DATA
    VEML7700_PING = MDF_VEML7700_PING
    VEML7700_PONG = MDF_VEML7700_PONG
    VEML7700_START = MDF_VEML7700_START
    VEML7700_STOP = MDF_VEML7700_STOP
    VEML7700_RESET = MDF_VEML7700_RESET
    VEML7700_CONNECT = MDF_VEML7700_CONNECT
    MECH_STIM_CONFIGURE = MDF_MECH_STIM_CONFIGURE
    MECH_STIM_RESET = MDF_MECH_STIM_RESET
    MECH_STIM_STAGE = MDF_MECH_STIM_STAGE
    MECH_STIM_WAITING = MDF_MECH_STIM_WAITING
    MECH_STIM_TRIGGER = MDF_MECH_STIM_TRIGGER
    MECH_STIM_CANCEL = MDF_MECH_STIM_CANCEL
    MECH_STIM_DONE = MDF_MECH_STIM_DONE
    MECH_STIM_ERROR = MDF_MECH_STIM_ERROR
    UC_MECH_STIM_CONFIGURE = MDF_UC_MECH_STIM_CONFIGURE
    _RESERVED_004300 = MDF__RESERVED_004300
    _RESERVED_004360 = MDF__RESERVED_004360
    _RESERVED_004361 = MDF__RESERVED_004361
    _RESERVED_004362 = MDF__RESERVED_004362
    _RESERVED_004363 = MDF__RESERVED_004363
    _RESERVED_004364 = MDF__RESERVED_004364
    _RESERVED_004365 = MDF__RESERVED_004365
    _RESERVED_004366 = MDF__RESERVED_004366
    _RESERVED_004367 = MDF__RESERVED_004367
    _RESERVED_004368 = MDF__RESERVED_004368
    _RESERVED_004369 = MDF__RESERVED_004369
    _RESERVED_004370 = MDF__RESERVED_004370
    _RESERVED_004371 = MDF__RESERVED_004371
    _RESERVED_004372 = MDF__RESERVED_004372
    _RESERVED_004373 = MDF__RESERVED_004373
    _RESERVED_004374 = MDF__RESERVED_004374
    _RESERVED_004375 = MDF__RESERVED_004375
    _RESERVED_004376 = MDF__RESERVED_004376
    _RESERVED_004377 = MDF__RESERVED_004377
    _RESERVED_004378 = MDF__RESERVED_004378


class _RTMA:
    constants = _constants
    HID = _HID
    MID = _MID
    aliases = _aliases
    MT = _MT
    MDF = _MDF
    SDF = _SDF


RTMA = _RTMA()
