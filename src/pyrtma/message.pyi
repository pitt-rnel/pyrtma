from __future__ import annotations
import json
import ctypes
from typing import (
    Type,
    Any,
    ClassVar,
    Dict,
    Union,
    Iterator,
    TypeVar,
    Generic,
    overload,
    List,
)
from collections.abc import Sequence
from dataclasses import dataclass

msg_defs: Dict[int, Type[MessageData]]

class RTMAMessageError(Exception): ...
class UnknownMessageType(RTMAMessageError): ...
class JSONDecodingError(RTMAMessageError): ...
class InvalidMessageDefinition(RTMAMessageError): ...

def message_def(msg_cls: Type[MessageData], *args, **kwargs) -> Type[MessageData]: ...

msg_def = message_def

def _create_ftype_map(obj: _MessageBase): ...

# Type Aliases
MODULE_ID = ctypes.c_short
HOST_ID = ctypes.c_short
MSG_TYPE = ctypes.c_int
MSG_COUNT = ctypes.c_int

class _RTMA_MSG_HEADER(ctypes.Structure):
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

MB = TypeVar("MB", bound="_MessageBase")

class _MessageBase(ctypes.Structure):
    @property
    def buffer(self) -> memoryview: ...
    def pretty_print(self, add_tabs=0) -> str: ...
    def hexdump(self, length=16, sep=" "): ...
    def to_json(self, minify: bool = False, **kwargs) -> str: ...
    def get_field_raw(self, name: str) -> bytes: ...
    @classmethod
    def from_dict(cls: Type[MB], data) -> MB: ...
    @classmethod
    def from_json(cls: Type[MB], s) -> MB: ...
    @classmethod
    def from_random(cls: Type[MB]) -> MB: ...
    @classmethod
    def from_buffer(cls: Type[MB], source, offset=0) -> MB: ...
    @classmethod
    def from_buffer_copy(cls: Type[MB], source, offset=0) -> MB: ...
    def __str__(self) -> str: ...
    def __eq__(self, other: _MessageBase) -> bool: ...
    def __getattribute__(self, name: str) -> Any: ...
    def __setattr__(self, name: str, value: Any): ...

class MessageHeader(_RTMA_MSG_HEADER):
    @property
    def size(self) -> int: ...
    @property
    def version(self) -> int: ...
    @version.setter
    def version(self, value: int): ...
    @property
    def get_data(self) -> Type[MessageData]: ...

class TimeCodeMessageHeader(MessageHeader):
    utc_seconds: int
    utc_fraction: int

def get_header_cls(timecode: bool = False) -> Type[MessageHeader]: ...

# proxy class to handle getting/setting from ctypes numeric arrays
_CT = TypeVar("_CT", bound=ctypes._CData)
_CInt = TypeVar(
    "_CInt",
    bound=Union[
        ctypes.c_bool,
        ctypes.c_byte,
        ctypes.c_long,
        ctypes.c_longlong,
        ctypes.c_int,
        ctypes.c_int8,
        ctypes.c_int16,
        ctypes.c_int32,
        ctypes.c_int64,
        ctypes.c_ulong,
        ctypes.c_ulonglong,
        ctypes.c_uint,
        ctypes.c_uint8,
        ctypes.c_uint16,
        ctypes.c_uint32,
        ctypes.c_uint64,
        ctypes.c_long,
        ctypes.c_longlong,
    ],
)
_CFloat = TypeVar(
    "_CFloat",
    bound=Union[
        ctypes.c_float,
        ctypes.c_double,
        ctypes.c_longdouble,
    ],
)
_CNum = TypeVar(
    "_CNum",
    bound=Union[
        ctypes.c_bool,
        ctypes.c_byte,
        ctypes.c_long,
        ctypes.c_longlong,
        ctypes.c_int,
        ctypes.c_int8,
        ctypes.c_int16,
        ctypes.c_int32,
        ctypes.c_int64,
        ctypes.c_ulong,
        ctypes.c_ulonglong,
        ctypes.c_uint,
        ctypes.c_uint8,
        ctypes.c_uint16,
        ctypes.c_uint32,
        ctypes.c_uint64,
        ctypes.c_long,
        ctypes.c_longlong,
        ctypes.c_float,
        ctypes.c_double,
        ctypes.c_longdouble,
    ],
)
# _CStr = TypeVar("_CStr", bound=ctypes.c_char)

class ArrayField(Sequence, Generic[_CNum]):
    _array: ctypes.Array[_CNum]
    _pytype_: type
    def __init__(self, array: ctypes.Array[_CNum]): ...
    @property
    def _length_(self) -> int: ...
    @property
    def _type_(self) -> Type[_CNum]: ...
    @overload
    def __setitem__(self: ArrayField[_CInt], __s: int, value_in: int): ...
    @overload
    def __setitem__(self: ArrayField[_CInt], __s: slice, value_in: Sequence[int]): ...
    @overload
    def __setitem__(self: ArrayField[_CFloat], __s: int, value_in: float): ...
    @overload
    def __setitem__(
        self: ArrayField[_CFloat], __s: slice, value_in: Sequence[float]
    ): ...
    @overload
    def __getitem__(self: ArrayField[_CInt], __s: int) -> int: ...
    @overload
    def __getitem__(self: ArrayField[_CInt], __s: slice) -> List[int]: ...
    @overload
    def __getitem__(self: ArrayField[_CFloat], __s: int) -> float: ...
    @overload
    def __getitem__(self: ArrayField[_CFloat], __s: slice) -> List[float]: ...
    def __len__(self) -> int: ...
    def __repr__(self) -> str: ...
    def __str__(self) -> str: ...

class MessageData(ctypes.Structure):
    type_id: ClassVar[int]
    type_name: ClassVar[str]
    type_hash: ClassVar[int]
    type_source: ClassVar[str]
    type_def: ClassVar[str]

    @property
    def type_size(self) -> int: ...

@dataclass
class Message:
    header: MessageHeader
    data: MessageData
    @property
    def type_id(self) -> int: ...
    @property
    def name(self) -> str: ...
    def __eq__(self, other: Message) -> bool: ...
    def pretty_print(self, add_tabs: int = 0) -> str: ...
    def __str__(self) -> str: ...
    def to_json(self, minify: bool = False, **kwargs) -> str: ...
    @classmethod
    def from_json(cls, s: str) -> Message: ...

class RTMAJSONEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any: ...

def _json_decode(obj, data): ...
