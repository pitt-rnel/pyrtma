"""pyrtma.messaage: RTMA message classes"""
import json
import ctypes

from typing import Type, Any, ClassVar, Dict
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
msg_defs: Dict[int, Type["MessageData"]] = {}


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


def message_def(msg_cls: Type["MessageData"], *args, **kwargs):
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


class _RTMA_MSG_HEADER(ctypes.Structure):
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
    def size(self) -> int:
        return ctypes.sizeof(self)

    @property
    def buffer(self):
        return memoryview(self)

    @property
    def version(self) -> int:
        return self.reserved

    @version.setter
    def version(self, value: int):
        self.reserved = value

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
        hexdump(bytes(self), length, sep)

    @property
    def get_data(self) -> Type["MessageData"]:
        try:
            return msg_defs[self.msg_type]
        except KeyError as e:
            raise UnknownMessageType(
                f"There is no message definition associated with id:{self.msg_type}"
            ) from e

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
        try:
            _json_decode(obj, data)
            return obj
        except Exception as e:
            raise JSONDecodingError(
                f"Unable to decode MessageHeader object from {data}."
            )

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


def _create_ftype_map(obj: "MessageData"):
    super(MessageData, obj).__setattr__(
        "_ftype_map",
        {k: v for k, v in super(MessageData, obj).__getattribute__("_fields_")},
    )


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
        return memoryview(
            self
        )  # should this return after .cast("B")? (or "b" or "c")? Uncasted memoryview is 0-dim and does not seem to be useful by itself

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
        hexdump(bytes(self), length, sep)

    def get_field_raw(self, name: str) -> bytes:
        """return copy of raw bytes for ctypes field 'name'"""
        meta = getattr(type(self), name)
        if name not in [x[0] for x in self._fields_]:
            raise KeyError(
                f"name {name} is not a field of message type {self.type_name}"
            )
        else:
            offset = meta.offset
            sz = meta.size

        return bytes(self.buffer.cast("c")[offset : offset + sz])

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
        try:
            _json_decode(obj, data)
            return obj
        except Exception as e:
            raise JSONDecodingError(f"Unable to decode {obj.type_name} from {data}.")

    @classmethod
    def from_json(cls, s):
        obj = cls.from_dict(json.loads(s))
        return obj


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

        # if isinstance(o, MessageData):
        #     d = {}
        #     d.update({k: getattr(o, k) for k, _ in getattr(o, ("_fields_"))})
        #     return d

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
