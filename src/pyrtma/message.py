"""pyrtma.messaage: RTMA message classes"""
from __future__ import annotations
import json
import ctypes

from typing import Type, Any, ClassVar, Dict, Union, TypeVar, Generic
from collections.abc import Sequence
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
    "ArrayField",
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


def _create_ftype_map(obj: _MessageBase):
    super(_MessageBase, obj).__setattr__(
        "_ftype_map",
        {k: v for k, v in super(_MessageBase, obj).__getattribute__("_fields_")},
    )


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


MB = TypeVar("MB", bound="_MessageBase")


# "abstract" base class for MessageHeader and MessageData
class _MessageBase(ctypes.Structure):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _create_ftype_map(self)

    @property
    def buffer(self) -> memoryview:
        return memoryview(self)

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
        meta = getattr(type(self), name)
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

    @classmethod
    def from_buffer(cls: Type[MB], source, offset=0) -> MB:
        obj = type(cls).from_buffer(cls, source, offset)
        _create_ftype_map(obj)
        return obj

    @classmethod
    def from_buffer_copy(cls: Type[MB], source, offset=0) -> Type[MB]:
        obj = type(cls).from_buffer_copy(cls, source, offset)
        _create_ftype_map(obj)
        return obj

    def __str__(self) -> str:
        return self.pretty_print()

    def __eq__(self, other: _MessageBase) -> bool:
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
        elif issubclass(ftype, ctypes.Array):
            return ArrayField(value)
        else:
            return value

    def __setattr__(self, name: str, value: Any):
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
            elif isinstance(value, int):
                # check for int overflow
                try:
                    if int.from_bytes(ftype(value).value, "little") != value:
                        raise ValueError(
                            f"Value {value} incompatible with type <ctypes.{ftype.__name__}>"
                        )
                except TypeError:
                    raise ValueError(
                        f"Value {value} incompatible with type <ctypes.{ftype.__name__}>"
                    )
        elif issubclass(ftype, ctypes.Array) and ftype._type_ is ctypes.c_char:
            if isinstance(value, str):
                value = value.encode()
        elif issubclass(ftype, ctypes.Array):
            array_proxy = getattr(self, name)
            array_proxy[:] = value
            return
        else:  # check for scalar rollover
            pytype = type(getattr(self, name))
            if pytype is int:  # check for value overflow (this is hard to do for float)
                try:
                    if ftype(value).value != value:
                        raise ValueError(
                            f"Value {value} incompatible with type <ctypes.{ftype.__name__}>"
                        )
                except TypeError:
                    raise TypeError(
                        f"Value {value} incompatible with type <ctypes.{ftype.__name__}>"
                    )
            elif pytype is float:
                # allow rounding errors but check that float values aren't wildly off
                try:
                    if abs(ftype(value).value - value) > 0.1:
                        raise ValueError(
                            f"Value {value} incompatible with type <ctypes.{ftype.__name__}>"
                        )
                except TypeError:
                    raise TypeError(
                        f"Value {value} incompatible with type <ctypes.{ftype.__name__}>"
                    )

        super().__setattr__(name, value)


class MessageHeader(_RTMA_MSG_HEADER, _MessageBase):
    @property
    def size(self) -> int:
        return ctypes.sizeof(self)

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


# proxy class to handle getting/setting from ctypes numeric arrays
_CT = TypeVar("_CT", bound=ctypes._SimpleCData)


class ArrayField(Sequence, Generic[_CT]):
    def __init__(self, array: ctypes.Array[_CT]):
        self._carray = array
        self._pytype_ = type(self._carray[0])

    @property
    def _length_(self) -> int:
        return len(self)

    @property
    def _type_(self) -> Type[_CT]:
        return self._carray._type_

    def __setitem__(self, __s: Union[slice, int], value_in):
        if type(__s) is slice:
            r = range(__s.start or 0, __s.stop or len(self), __s.step or 1)  # type: ignore
        else:
            r = range(__s, __s + 1)
        try:
            if len(value_in) != len(r):
                raise IndexError(f"Value longer than slice")
        except TypeError:  # ignore scalar value in which can be applied to all values
            pass

        if r.stop > len(self):
            raise IndexError("Index out of range")

        for j, i in enumerate(r):
            try:
                value = value_in[j]
            except TypeError:  # expand scalar to all values of slice
                value = value_in
            ftype = self._type_
            pytype = self._pytype_
            if pytype is int:
                try:
                    if ftype(value).value != value:
                        raise ValueError(
                            f"Value {value} incompatible with type <ctypes.{ftype.__name__}>"
                        )
                except TypeError:
                    raise TypeError(
                        f"Value {value} incompatible with type <ctypes.{ftype.__name__}>"
                    )
            elif pytype is float:
                # allow rounding errors but check that float values aren't wildly off
                try:
                    if abs(ftype(value).value - value) > 0.1:
                        raise ValueError(
                            f"Value {value} incompatible with type <ctypes.{ftype.__name__}>"
                        )
                except TypeError:
                    raise TypeError(
                        f"Value {value} incompatible with type <ctypes.{ftype.__name__}>"
                    )
            self._carray[i] = value

    def __getitem__(self, __s: Union[slice, int]) -> Any:
        if (isinstance(__s, int) and __s > len(self)) or (
            isinstance(__s, slice) and (__s.start > len(self) or __s.stop > len(self))
        ):
            raise IndexError("Index out of range")
        item = self._carray[__s]
        if isinstance(item, ctypes.Array):  # multi-dimensional arrays
            item = ArrayField(item)
        return item

    def __len__(self) -> int:
        return len(self._carray)

    def __repr__(self) -> str:
        mloc = id(self)
        return f"ArrayField object of {repr(self._carray)} at 0x{mloc:016X}"

    def __str__(self) -> str:
        return print_ctype_array(self._carray)


# TODO: Make this class abstract
class MessageData(_MessageBase):
    type_id: ClassVar[int] = -1
    type_name: ClassVar[str] = ""
    type_hash: ClassVar[int]
    type_source: ClassVar[str] = ""
    type_def: ClassVar[str] = ""

    @property
    def type_size(self) -> int:
        return ctypes.sizeof(self)


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

    def __str__(self) -> str:
        return self.pretty_print()

    def to_json(self, minify: bool = False, **kwargs) -> str:
        if minify:
            return json.dumps(
                self, cls=RTMAJSONEncoder, separators=(",", ":"), **kwargs
            )
        else:
            return json.dumps(self, cls=RTMAJSONEncoder, indent=2, **kwargs)

    @classmethod
    def from_json(cls, s: str) -> Message:
        # Convert json string to dict
        d = json.loads(s)

        # Decode header segment
        timecode_flag = "utc_seconds" in d["header"]
        hdr_cls = get_header_cls(timecode_flag)
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

        if isinstance(o, ArrayField) or isinstance(o, ctypes.Array):
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
