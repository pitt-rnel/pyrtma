"""pyrtma.messaage: RTMA message classes"""
import json

from typing import Type, Dict, Any, TypeVar
from dataclasses import dataclass

from .header import MessageHeader, get_header_cls
from .message_data import MessageData
from .exceptions import InvalidMessageDefinition, UnknownMessageType

__all__ = [
    "Message",
    "MessageHeader",
    "MessageData",
    "get_header_cls",
    "msg_defs",
    "message_def",
    "msg_def",  # deprecated
]

# Main Map of all internal message types
msg_defs: Dict[int, Type[MessageData]] = {}


_MD = TypeVar("_MD", bound=MessageData)  # Parent


def message_def(msg_cls: Type[_MD], *args, **kwargs) -> Type[_MD]:
    """Decorator to add user message definitions."""
    msg_defs[msg_cls.type_id] = msg_cls
    return msg_cls


# backwards compatibility: deprecated name
msg_def = message_def


def get_msg_cls(id: int) -> Type[MessageData]:
    try:
        return msg_defs[id]
    except KeyError as e:
        raise UnknownMessageType(
            f"There is no message definition associated with id:{id}"
        ) from e


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

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Message):
            return False
        return self.header == other.header and self.data == other.data

    def pretty_print(self, add_tabs: int = 0) -> str:
        return (
            self.header.pretty_print(add_tabs) + "\n" + self.data.pretty_print(add_tabs)
        )

    def to_dict(self) -> Dict[str, Any]:
        return dict(header=self.header.to_dict(), data=self.data.to_dict())

    def to_json(self, minify: bool = False, **kwargs) -> str:
        d = dict(header=self.header.to_dict(), data=self.data.to_dict())
        if minify:
            return json.dumps(d, separators=(",", ":"), **kwargs)
        else:
            return json.dumps(self, indent=2, **kwargs)

    @classmethod
    def from_json(cls, s: str) -> "Message":
        # Convert json string to dict
        d = json.loads(s)

        # Decode header segment
        hdr_cls = get_header_cls()
        hdr = hdr_cls.from_dict(d["header"])

        # Decode message data segment
        msg_cls = get_msg_cls(hdr.msg_type)

        # Note: Ignore the sync check if header.version is not filled in
        # This can removed once all clients support this field.
        if hdr.version != 0 and hdr.version != msg_cls.type_hash:
            raise InvalidMessageDefinition(
                f"Client's message definition does not match senders version: {msg_cls.type_name}"
            )

        msg_data = msg_cls.from_dict(d["data"])

        obj = cls(hdr, msg_data)

        return obj
