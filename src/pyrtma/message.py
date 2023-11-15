"""pyrtma.messaage: RTMA message classes"""
from __future__ import annotations
import json
import ctypes

from typing import Type, Any, ClassVar, Dict, TypeVar
from dataclasses import dataclass

from .utils.print import print_ctype_array, hexdump
from .utils.random import _random_struct

__all__ = [
    "Message",
    "MessageHeader",
    "TimeCodeMessageHeader",
    "MessageData",
    "get_header_cls",
    "msg_defs",
    "message_def",
    "msg_def",  # deprecated
    "RTMAMessageError",
    "UnknownMessageType",
    "JSONDecodingError",
    "InvalidMessageDefinition",
]

# Main Map of all internal message types
msg_defs: Dict[int, Type[MessageData]] = {}


class RTMAMessageError(Exception):
    """Base exception for message errors."""

    pass


class UnknownMessageType(RTMAMessageError):
    """Raised when there is no message definition."""

    pass


class JSONDecodingError(RTMAMessageError):
    """Raised when there is an error decoding a message from json."""

    pass


class InvalidMessageDefinition(RTMAMessageError):
    """Raised when there is message definition is out of sync with sent data."""

    pass


def message_def(msg_cls: Type[MessageData], *args, **kwargs) -> Type[MessageData]:
    """Decorator to add user message definitions."""
    msg_defs[msg_cls.type_id] = msg_cls
    return msg_cls


# backwards compatibility: deprecated name
msg_def = message_def


# Type Aliases
MODULE_ID = ctypes.c_short


HOST_ID = ctypes.c_short


MSG_TYPE = ctypes.c_int


MSG_COUNT = ctypes.c_int


MB = TypeVar("MB", bound="_MessageBase")


# "abstract" base class for MessageHeader and MessageData
class _MessageBase(ctypes.Structure):
    @property
    def size(self) -> int:
        return ctypes.sizeof(self)

    def pretty_print(self, add_tabs=0) -> str:
        str = "\t" * add_tabs + f"{type(self).__name__}:"
        for field_name, field_type in self._fields_:
            val = getattr(self, field_name)
            class_name = field_type.__name__
            # expand arrays
            if hasattr(val, "__len__"):
                if hasattr(val, "_type_"):
                    class_name = val._type_.__name__
                val = print_ctype_array(val)
            str += f"\n" + "\t" * (add_tabs + 1) + f"{field_name} = ({class_name}){val}"
        return str

    def hexdump(self, length=16, sep=" "):
        hexdump(bytes(self), length, sep)

    def to_json(self, minify: bool = False, **kwargs) -> str:
        if minify:
            return json.dumps(
                self, cls=RTMAJSONEncoder, separators=(",", ":"), **kwargs
            )
        else:
            return json.dumps(self, cls=RTMAJSONEncoder, indent=2, **kwargs)

    def get_field_raw(self, name: str) -> bytes:
        """return copy of raw bytes for ctypes field 'name'"""
        meta = getattr(type(self), f"_{name}")
        if name not in [x[0] for x in self._fields_]:
            if isinstance(self, MessageData):
                error_str = f"{name} is not a field of message type {self.type_name}"
            elif isinstance(self, MessageHeader):
                error_str = f"{name} is not a field of message header"
            else:
                error_str = f"{name} is not a field"
            raise KeyError(error_str)
        else:
            offset = meta.offset
            sz = meta.size

        return bytes(memoryview(self).cast("c")[offset : offset + sz])

    @classmethod
    def from_dict(cls: Type[MB], data) -> MB:
        obj = cls()
        try:
            _json_decode(obj, data)
            return obj
        except Exception as e:
            if issubclass(cls, MessageHeader):
                error_str = f"Unable to decode MessageHeader object from {data}."
            elif issubclass(cls, MessageData):
                error_str = f"Unable to decode {obj.type_name} from {data}."
            else:
                error_str = "Unable to construct class"

            raise JSONDecodingError(error_str)

    @classmethod
    def from_json(cls: Type[MB], s) -> MB:
        obj = cls.from_dict(json.loads(s))
        return obj

    @classmethod
    def from_random(cls: Type[MB]) -> MB:
        obj = _random_struct(cls())
        return obj

    def __str__(self) -> str:
        return self.pretty_print()

    def __eq__(self, other: _MessageBase) -> bool:
        if type(self) != type(other):
            return False

        return bytes(self) == bytes(other)


class _RTMA_MSG_HEADER(_MessageBase):
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


class MessageHeader(_RTMA_MSG_HEADER):
    @property
    def version(self) -> int:
        return self.reserved

    @version.setter
    def version(self, value: int):
        self.reserved = value

    @property
    def get_data(self) -> Type[MessageData]:
        try:
            return msg_defs[self.msg_type]
        except KeyError as e:
            raise UnknownMessageType(
                f"There is no message definition associated with id:{self.msg_type}"
            ) from e


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


class MessageData(_MessageBase):
    type_id: ClassVar[int] = -1
    type_name: ClassVar[str] = ""
    type_hash: ClassVar[int]
    type_source: ClassVar[str] = ""
    type_def: ClassVar[str] = ""

    @property
    def type_size(self) -> int:
        return ctypes.sizeof(self)


    @classmethod
    def from_random(cls) -> MessageData:
        obj = _random_struct(cls())
        return obj

    @classmethod
    def copy(cls, s: MessageData):
        return cls.from_buffer_copy(s)


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

    def __eq__(self, other: Message) -> bool:
        return self.header == other.header and self.data == other.data

    def pretty_print(self, add_tabs: int = 0) -> str:
        return (
            self.header.pretty_print(add_tabs) + "\n" + self.data.pretty_print(add_tabs)
        )

    @classmethod
    def from_json(cls, s: str) -> Message:
        # Convert json string to dict
        d = json.loads(s)

        # Decode header segment
        hdr_cls = get_header_cls()
        hdr = hdr_cls.from_dict(d["header"])

        # Decode message data segment
        msg_cls = hdr.get_data()

        # Note: Ignore the sync check if header.version is not filled in
        # This can removed once all clients support this field.
        if hdr.version != 0 and hdr.version != msg_cls.type_hash:
            raise InvalidMessageDefinition(
                f"Client's message definition does not match senders version: {msg_cls.type_name}"
            )

        msg_data = msg_cls.from_dict(d["data"])

        obj = cls(hdr, msg_data)

        return obj


class RTMAJSONEncoder(json.JSONEncoder):
    """JSONEncoder object used to convert MessageData to json

    Example:
        data = json.dumps(msg, cls=pyrtma.encoding.RTMAJSONEncoder)
    """

    def default(self, o: Any) -> Any:
        if isinstance(o, Message):
            return dict(header=o.header, data=o.data)

        if issubclass(o.__class__, ctypes.Structure):
            return {k: getattr(o, k) for k, _ in getattr(o, ("_fields_"))}

        if isinstance(o, ctypes.Array):
            return list(o)

        if isinstance(o, bytes):
            return [int(x) for x in o]

        return super().default(o)


def _json_decode(obj, data):
    for name, ftype in obj._fields_:
        if issubclass(ftype, ctypes.Structure):
            _json_decode(getattr(obj, name), data[name])
        elif issubclass(ftype, ctypes.Array):
            if issubclass(ftype._type_, ctypes.Structure):  # type: ignore
                for i, elem in enumerate(getattr(obj, name)):
                    _json_decode(elem, data[name][i])
            elif ftype._type_ is ctypes.c_char:
                setattr(obj, name, data[name])
            else:
                getattr(obj, name)[:] = data[name]
        else:
            setattr(obj, name, data[name])
