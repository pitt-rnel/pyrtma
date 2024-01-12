from typing import ClassVar
from .message_base import MessageBase, MessageMeta


class MessageData(MessageBase, metaclass=MessageMeta):
    """MessageData base class

    This is intended to be treated as an abstract class and
    and should not be directly instantiated.
    """

    type_id: ClassVar[int] = -1
    type_name: ClassVar[str] = ""
    type_hash: ClassVar[int]
    type_source: ClassVar[str] = ""
    type_size: ClassVar[int] = -1
    type_def: ClassVar[str] = ""
