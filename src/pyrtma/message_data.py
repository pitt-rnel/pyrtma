import ctypes

from typing import ClassVar
from .message_base import MessageBase
from .utils.random_fields import _random_struct


class MessageData(MessageBase):
    type_id: ClassVar[int] = -1
    type_name: ClassVar[str] = ""
    type_hash: ClassVar[int]
    type_source: ClassVar[str] = ""
    type_def: ClassVar[str] = ""

    @property
    def type_size(self) -> int:
        return ctypes.sizeof(self)

    @classmethod
    def from_random(cls) -> "MessageData":
        obj = _random_struct(cls())
        return obj

    @classmethod
    def copy(cls, s: "MessageData"):
        return cls.from_buffer_copy(s)
