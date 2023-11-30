from typing import ClassVar
from .message_base import MessageBase


class MessageData(MessageBase):
    type_id: ClassVar[int] = -1
    type_name: ClassVar[str] = ""
    type_hash: ClassVar[int]
    type_source: ClassVar[str] = ""
    type_size: ClassVar[int] = -1
    type_def: ClassVar[str] = ""
