"""pyrtma._core

Core RTMA message definitions and functions"""
import ctypes
import json
import random
import string

from dataclasses import dataclass
from collections import ChainMap
from typing import Type, ClassVar, Optional, Any, Dict, ChainMap, List

from .constants import *


core_msg_defs: Dict[int, Type["MessageData"]] = {}
user_msg_defs: Dict[int, Type["MessageData"]] = {}

msg_defs: ChainMap[int, Type["MessageData"]] = ChainMap(core_msg_defs, user_msg_defs)


def msg_def(msg_cls, *args, **kwargs):
    """Decorator to add user message definitions."""
    user_msg_defs[msg_cls.type_id] = msg_cls
    return msg_cls


def core_def(msg_cls, *args, **kwargs):
    """Decorator to add core message definitions."""
    core_msg_defs[msg_cls.type_id] = msg_cls
    return msg_cls


def print_ctype_array(arr):
    """expand and print ctype arrays"""
    max_len = 20
    arr_len = len(arr)
    str = "{"
    for i in range(0, min(arr_len, max_len)):
        str += f"{arr[i]}, "
    if arr_len > max_len:
        str += "...}"
    else:
        str = str[:-2] + "}"
    return str


def _create_ftype_map(obj: "MessageData"):
    super(MessageData, obj).__setattr__(
        "_ftype_map",
        {k: v for k, v in super(MessageData, obj).__getattribute__("_fields_")},
    )


def _random_str(length) -> str:
    return "".join(random.choice(string.printable) for _ in range(length))


def _random_int_array(length: int, min: int = 0, max: int = 9) -> List[int]:
    return [random.randint(min, max) for _ in range(length)]


def _random_float_array(length) -> List[float]:
    return [random.random() for _ in range(length)]


def _random_byte_array(length) -> bytes:
    return bytes([random.randint(0, 255) for _ in range(length)])


def _random_struct(obj):
    for name, ftype in obj._fields_:
        if issubclass(ftype, ctypes.Structure):
            setattr(obj, name, _random_struct(getattr(obj, name)))
        elif issubclass(ftype, ctypes.Array):
            length = ftype._length_
            etype = ftype._type_
            if issubclass(etype, ctypes.Structure):
                for i in range(length):
                    getattr(obj, name)[i] = _random_struct(getattr(obj, name)[i])
            elif etype is ctypes.c_char:
                setattr(obj, name, _random_str(length))
            elif etype is ctypes.c_ubyte:
                getattr(obj, name)[:] = _random_byte_array(length)
            elif etype is ctypes.c_int8:
                getattr(obj, name)[:] = _random_int_array(
                    length, min=-(2**7), max=2**7 - 1
                )
            elif etype is ctypes.c_uint8:
                getattr(obj, name)[:] = _random_int_array(length, min=0, max=2**8 - 1)
            elif etype in (ctypes.c_short, ctypes.c_int16):
                getattr(obj, name)[:] = _random_int_array(
                    length, min=-(2**15), max=2**15 - 1
                )
            elif etype in (ctypes.c_ushort, ctypes.c_uint16):
                getattr(obj, name)[:] = _random_int_array(
                    length, min=0, max=2**16 - 1
                )
            elif etype in (ctypes.c_int, ctypes.c_long, ctypes.c_int32):
                getattr(obj, name)[:] = _random_int_array(
                    length, min=-(2**31), max=2**31 - 1
                )
            elif etype in (ctypes.c_uint, ctypes.c_ulong, ctypes.c_uint32):
                getattr(obj, name)[:] = _random_int_array(
                    length, min=0, max=2**32 - 1
                )
            elif etype in (ctypes.c_longlong, ctypes.c_int64):
                getattr(obj, name)[:] = _random_int_array(
                    length, min=-(2**63), max=2**63 - 1
                )
            elif etype in (ctypes.c_ulonglong, ctypes.c_uint64):
                getattr(obj, name)[:] = _random_int_array(
                    length, min=0, max=2**64 - 1
                )
            elif etype is ctypes.c_float:
                getattr(obj, name)[:] = _random_float_array(length)
            elif etype is ctypes.c_double:
                getattr(obj, name)[:] = _random_float_array(length)
        elif ftype is ctypes.c_char:
            setattr(obj, name, _random_str(1))
        elif ftype is ctypes.c_ubyte:
            setattr(obj, name, random.randint(0, 255))
        elif ftype is ctypes.c_int8:
            setattr(obj, name, random.randint(-(2**7), 2**7 - 1))
        elif ftype is ctypes.c_uint8:
            setattr(obj, name, random.randint(0, 2**8 - 1))
        elif ftype in (ctypes.c_short, ctypes.c_int16):
            setattr(obj, name, random.randint(-(2**15), 2**15 - 1))
        elif ftype in (ctypes.c_ushort, ctypes.c_uint16):
            setattr(obj, name, random.randint(0, 2**16 - 1))
        elif ftype in (ctypes.c_int, ctypes.c_long, ctypes.c_int32):
            setattr(obj, name, random.randint(-(2**31), 2**31 - 1))
        elif ftype in (ctypes.c_uint, ctypes.c_ulong, ctypes.c_uint32):
            setattr(obj, name, random.randint(0, 2**32 - 1))
        elif ftype in (ctypes.c_longlong, ctypes.c_int64):
            setattr(obj, name, random.randint(-(2**63), 2**63 - 1))
        elif ftype in (ctypes.c_ulonglong, ctypes.c_uint64):
            setattr(obj, name, random.randint(0, 2**64 - 1))
        elif ftype is ctypes.c_float:
            setattr(obj, name, random.random())
        elif ftype is ctypes.c_double:
            setattr(obj, name, random.random())

    return obj


def _json_decode(obj, data):
    for name, ftype in obj._fields_:
        if issubclass(ftype, ctypes.Structure):
            _json_decode(getattr(obj, name), data[name])
        elif issubclass(ftype, ctypes.Array):
            if issubclass(ftype._type_, ctypes.Structure):
                for i, elem in enumerate(getattr(obj, name)):
                    _json_decode(elem, data[name][i])
            elif ftype._type_ is ctypes.c_char:
                setattr(obj, name, data[name])
            else:
                getattr(obj, name)[:] = data[name]
        else:
            setattr(obj, name, data[name])


class RTMAJSONEncoder(json.JSONEncoder):
    """JSONEncoder object used to convert MessageData to json

    Example:
        data = json.dumps(msg, cls=pyrtma.encoding.RTMAJSONEncoder)
    """

    def default(self, o: Any) -> Any:
        if isinstance(o, Message):
            return dict(header=o.header, data=o.data)

        if isinstance(o, MessageData):
            d = {}
            d.update({k: getattr(o, k) for k, _ in getattr(o, ("_fields_"))})
            return d

        if issubclass(o.__class__, ctypes.Structure):
            return {k: getattr(o, k) for k, _ in getattr(o, ("_fields_"))}

        if isinstance(o, ctypes.Array):
            return list(o)

        if isinstance(o, bytes):
            return [int(x) for x in o]

        return super().default(o)


# TODO: Make this class abstract
class MessageData(ctypes.Structure):
    type_id: ClassVar[int] = -1
    type_name: ClassVar[str] = ""
    type_hash: int
    type_src: str

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _create_ftype_map(self)

    @classmethod
    def from_random(cls):
        obj = _random_struct(cls())
        return obj

    @classmethod
    def from_buffer(cls, source, offset=0):
        obj = type(cls).from_buffer(cls, source, offset)
        _create_ftype_map(obj)
        return obj

    @classmethod
    def from_buffer_copy(cls, source, offset=0):
        obj = type(cls).from_buffer_copy(cls, source, offset)
        _create_ftype_map(obj)
        return obj

    @property
    def size(self) -> int:
        return ctypes.sizeof(self)

    @property
    def buffer(self):
        return memoryview(self)

    def pretty_print(self, add_tabs=0):
        str = "\t" * add_tabs + f"{type(self).__name__}:"
        for field_name, field_type in self._fields_:
            val = getattr(self, field_name)
            class_name = type(val).__name__
            # expand arrays
            if hasattr(val, "__len__"):
                val = print_ctype_array(val)
            str += f"\n" + "\t" * (add_tabs + 1) + f"{field_name} = ({class_name}){val}"
        return str

    def hexdump(self, length=16, sep=" "):
        src = bytes(self)
        FILTER = "".join(
            [(len(repr(chr(x))) == 3) and chr(x) or sep for x in range(256)]
        )
        for c in range(0, len(src), length):
            chars = src[c : c + length]
            hex_ = " ".join(["{:02x}".format(x) for x in chars])
            if len(hex_) > 24:
                hex_ = "{} {}".format(hex_[:24], hex_[24:])
            printable = "".join(
                ["{}".format((x <= 127 and FILTER[x]) or sep) for x in chars]
            )
            print(
                "{0:08x}  {1:{2}s} |{3:{4}s}|".format(
                    c, hex_, length * 3, printable, length
                )
            )

    def __str__(self):
        return self.pretty_print()

    def __eq__(self, other: "MessageData") -> bool:
        if type(self) != type(other):
            raise TypeError(f"Can not compare {type(other)} to {type(self)}.")

        return bytes(self) == bytes(other)

    def __getattribute__(self, name: str) -> Any:
        value = super().__getattribute__(name)
        try:
            # This is a workaround for nested messages. _ftype_map should exist for
            # for other cases.
            ftype = super().__getattribute__("_ftype_map").get(name)
        except AttributeError:
            # Create map if it doesn't exist
            _create_ftype_map(self)
            ftype = super().__getattribute__("_ftype_map").get(name)

        # Check attribute is not a struct field
        if ftype is None:
            return value

        # Automatically decode char types to a string
        if ftype is ctypes.c_char:
            return value.decode()
        elif issubclass(ftype, ctypes.Array) and ftype._type_ is ctypes.c_char:
            return value.decode()
        else:
            return value

    def __setattr__(self, name: str, value: Any) -> None:
        try:
            ftype = super().__getattribute__("_ftype_map").get(name)
        except AttributeError:
            # Create map if it doesn't exist
            _create_ftype_map(self)
            ftype = super().__getattribute__("_ftype_map").get(name)

        # Automatically encode a string value to bytes
        if ftype is ctypes.c_char:
            if isinstance(value, str):
                value = value.encode()
        elif issubclass(ftype, ctypes.Array) and ftype._type_ is ctypes.c_char:
            if isinstance(value, str):
                value = value.encode()

        super().__setattr__(name, value)

    def to_json(self, minify: bool = False, **kwargs) -> str:
        if minify:
            return json.dumps(
                self, cls=RTMAJSONEncoder, separators=(",", ":"), **kwargs
            )

        else:
            return json.dumps(self, cls=RTMAJSONEncoder, indent=2, **kwargs)

    @classmethod
    def from_dict(cls, data):
        obj = cls()
        _json_decode(obj, data)
        return obj

    @classmethod
    def from_json(cls, s):
        obj = cls.from_dict(json.loads(s))
        return obj


class MessageHeader(ctypes.Structure):
    _fields_ = [
        ("msg_type", ctypes.c_int),
        ("msg_count", ctypes.c_int),
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

    @property
    def size(self) -> int:
        return ctypes.sizeof(self)

    @property
    def buffer(self):
        return memoryview(self)

    def pretty_print(self, add_tabs=0):
        str = "\t" * add_tabs + f"{type(self).__name__}:"
        for field_name, field_type in self._fields_:
            val = getattr(self, field_name)
            class_name = type(val).__name__
            # expand arrays
            if hasattr(val, "__len__"):
                val = print_ctype_array(val)
            str += f"\n" + "\t" * (add_tabs + 1) + f"{field_name} = ({class_name}){val}"
        return str

    @property
    def get_data(self) -> Type[MessageData]:
        return msg_defs[self.msg_type]

    def to_json(self, minify: bool = False, **kwargs) -> str:
        if minify:
            return json.dumps(
                self, cls=RTMAJSONEncoder, separators=(",", ":"), **kwargs
            )
        else:
            return json.dumps(self, cls=RTMAJSONEncoder, indent=2, **kwargs)

    @classmethod
    def from_dict(cls, data):
        obj = cls()
        _json_decode(obj, data)
        return obj

    @classmethod
    def from_json(cls, s):
        obj = cls.from_dict(json.loads(s))
        return obj

    def __eq__(self, other: "MessageHeader") -> bool:
        if type(self) != type(other):
            raise TypeError(f"Can not compare {type(other)} to {type(self)}.")

        return bytes(self) == bytes(other)


class TimeCodeMessageHeader(MessageHeader):
    _fields_ = [
        ("utc_seconds", ctypes.c_uint),
        ("utc_fraction", ctypes.c_uint),
    ]


def get_header_cls(timecode: bool = False) -> Type[MessageHeader]:
    if timecode:
        return TimeCodeMessageHeader
    else:
        return MessageHeader


@dataclass
class Message:
    header: MessageHeader
    data: MessageData

    @property
    def type_id(self) -> int:
        return self.data.type_id

    @property
    def name(self) -> str:
        return self.data.type_name

    def __eq__(self, other: "Message") -> bool:
        return self.header == other.header and self.data == other.data

    def pretty_print(self, add_tabs=0):
        return (
            self.header.pretty_print(add_tabs) + "\n" + self.data.pretty_print(add_tabs)
        )

    def to_json(self, minify: bool = False, **kwargs) -> str:
        if minify:
            return json.dumps(
                self, cls=RTMAJSONEncoder, separators=(",", ":"), **kwargs
            )
        else:
            return json.dumps(self, cls=RTMAJSONEncoder, indent=2, **kwargs)

    @classmethod
    def from_json(cls, s: str):
        # Convert json string to dict
        d = json.loads(s)

        # Decode header segment
        hdr_cls = get_header_cls()
        hdr = hdr_cls.from_dict(d["header"])

        # Decode message data segment
        msg_cls = msg_defs[hdr.msg_type]
        msg_data = msg_cls.from_dict(d["data"])

        obj = cls(hdr, msg_data)

        return obj


# START OF RTMA INTERNAL MESSAGE DEFINITIONS
@core_def
class EXIT(MessageData):
    _fields_ = []
    type_id: ClassVar[int] = MT_EXIT
    type_name: ClassVar[str] = "EXIT"


@core_def
class KILL(MessageData):
    _fields_ = []
    type_id: ClassVar[int] = MT_KILL
    type_name: ClassVar[str] = "KILL"


@core_def
class ACKNOWLEDGE(MessageData):
    _fields_ = []
    type_id: ClassVar[int] = MT_ACKNOWLEDGE
    type_name: ClassVar[str] = "ACKNOWLEDGE"


@core_def
class CONNECT(MessageData):
    _fields_ = [("logger_status", ctypes.c_short), ("daemon_status", ctypes.c_short)]
    type_id: ClassVar[int] = MT_CONNECT
    type_name: ClassVar[str] = "CONNECT"


@core_def
class DISCONNECT(MessageData):
    _fields_ = []
    type_id: ClassVar[int] = MT_DISCONNECT
    type_name: ClassVar[str] = "DISCONNECT"


@core_def
class SUBSCRIBE(MessageData):
    _fields_ = [("msg_type", MSG_TYPE)]
    type_id: ClassVar[int] = MT_SUBSCRIBE
    type_name: ClassVar[str] = "SUBSCRIBE"


@core_def
class UNSUBSCRIBE(MessageData):
    _fields_ = [("msg_type", MSG_TYPE)]
    type_id: ClassVar[int] = MT_UNSUBSCRIBE
    type_name: ClassVar[str] = "UNSUBSCRIBE"


@core_def
class PAUSE_SUBSCRIPTION(MessageData):
    _fields_ = [("msg_type", MSG_TYPE)]
    type_id: ClassVar[int] = MT_PAUSE_SUBSCRIPTION
    type_name: ClassVar[str] = "PAUSE_SUBSCRIPTION"


@core_def
class RESUME_SUBSCRIPTION(MessageData):
    _fields_ = [("msg_type", MSG_TYPE)]
    type_id: ClassVar[int] = MT_RESUME_SUBSCRIPTION
    type_name: ClassVar[str] = "RESUME_SUBSCRIPTION"


@core_def
class FAIL_SUBSCRIBE(MessageData):
    _fields_ = [
        ("mod_id", MODULE_ID),
        ("reserved", ctypes.c_short),
        ("msg_type", MSG_TYPE),
    ]
    type_id: ClassVar[int] = MT_FAIL_SUBSCRIBE
    type_name: ClassVar[str] = "FAIL_SUBSCRIBE"


@core_def
class FAILED_MESSAGE(MessageData):
    _fields_ = [
        ("dest_mod_id", MODULE_ID),
        ("reserved", ctypes.c_short * 3),
        ("time_of_failure", ctypes.c_double),
        ("msg_header", MessageHeader),
    ]
    type_id: ClassVar[int] = MT_FAILED_MESSAGE
    type_name: ClassVar[str] = "FAILED_MESSAGE"


@core_def
class FORCE_DISCONNECT(MessageData):
    _fields_ = [("mod_id", ctypes.c_int)]
    type_id: ClassVar[int] = MT_FORCE_DISCONNECT
    type_name: ClassVar[str] = "FORCE_DISCONNECT"


@core_def
class MODULE_READY(MessageData):
    _fields_ = [("pid", ctypes.c_int)]
    type_id: ClassVar[int] = MT_MODULE_READY
    type_name: ClassVar[str] = "MODULE_READY"


@core_def
class SAVE_MESSAGE_LOG(MessageData):
    _fields_ = [
        ("pathname", ctypes.c_char * MAX_LOGGER_FILENAME_LENGTH),
        ("pathname_length", ctypes.c_int),
    ]
    type_id: ClassVar[int] = MT_SAVE_MESSAGE_LOG
    type_name: ClassVar[str] = "SAVE_MESSAGE_LOG"


@core_def
class TIMING_MESSAGE(MessageData):
    _fields_ = [
        ("timing", ctypes.c_ushort * MAX_MESSAGE_TYPES),
        ("ModulePID", ctypes.c_int * MAX_MODULES),
        ("send_time", ctypes.c_double),
    ]
    type_id: ClassVar[int] = MT_TIMING_MESSAGE
    type_name: ClassVar[str] = "TIMING_MESSAGE"


def AddMessage(msg_type_id: int, msg_cls: Type[MessageData]):
    """Add a user message definition to the RTMA module"""
    msg_defs.maps[1][msg_type_id] = msg_cls
