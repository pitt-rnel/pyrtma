"""pyrtma.messaage: RTMA message classes"""

from __future__ import annotations

import json
import copy

from typing import Type, Dict, Any, TypeVar

from .header import MessageHeader, get_header_cls
from .message_data import MessageData
from .message_base import RTMAJSONEncoder
from .exceptions import InvalidMessageDefinition, UnknownMessageType

__all__ = [
    "Message",
    "MessageHeader",
    "MessageData",
    "get_header_cls",
    "get_msg_cls",
    "message_def",
    "msg_def",  # deprecated
]

# Main Map of all internal message types
_msg_defs: Dict[int, Type[MessageData]] = {}


_MD = TypeVar("_MD", bound=MessageData)  # Parent


def message_def(msg_cls: Type[_MD], *args, **kwargs) -> Type[_MD]:
    """Decorator to add user message definitions."""
    _msg_defs[msg_cls.type_id] = msg_cls
    return msg_cls


# backwards compatibility: deprecated name
msg_def = message_def


def set_msg_defs(defs: Dict[int, Type[MessageData]]):
    _msg_defs.clear()
    _msg_defs.update(defs)


def get_msg_defs() -> Dict[int, Type[MessageData]]:
    return copy.deepcopy(_msg_defs)


def update_msg_defs(defs: Dict[int, Type[MessageData]]):
    _msg_defs.update(defs)


def clear_msg_defs():
    _msg_defs.clear()


def get_msg_cls(id: int) -> Type[MessageData]:
    """get msg class for a given message type ID

    Args:
        id (int): Message Type ID

    Raises:
        UnknownMessageType: Message type is undefined

    Returns:
        Type[MessageData]: Message class
    """
    try:
        return _msg_defs[id]
    except KeyError as e:
        raise UnknownMessageType(
            f"There is no message definition associated with id: {id}"
        ) from e


class Message:
    """Message class

    Contains message header and data
    """

    def __init__(self, header: MessageHeader, data: MessageData):
        self.header = header
        self.data = data

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
        """Generate formatted string for pretty printing of message

        Args:
            add_tabs (int, optional): Indent level. Defaults to 0.

        Returns:
            str: Formatted string
        """
        return (
            self.header.pretty_print(add_tabs) + "\n" + self.data.pretty_print(add_tabs)
        )

    def __str__(self) -> str:
        return self.pretty_print()

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary

        Returns:
            Dict[str, Any]: Message dictionary
        """
        return dict(header=self.header.to_dict(), data=self.data.to_dict())

    def to_json(self, minify: bool = False, **kwargs) -> str:
        """Convert message to JSON string

        Args:
            minify (bool, optional): Flag to minify (compact format). Defaults to False.

        Returns:
            str: JSON message string
        """
        d = dict(header=self.header.to_dict(), data=self.data.to_dict())
        if minify:
            return json.dumps(d, cls=RTMAJSONEncoder, separators=(",", ":"), **kwargs)
        else:
            return json.dumps(d, cls=RTMAJSONEncoder, indent=2, **kwargs)

    @classmethod
    def from_json(cls, s: str) -> Message:
        """Create message object from JSON string

        Args:
            s (str): JSON message string

        Raises:
            InvalidMessageDefinition: JSON data does not match expected message defintion

        Returns:
            Message: Message object
        """
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
                f"Client's message definition does not match sender's version: {msg_cls.type_name}"
            )

        msg_data = msg_cls.from_dict(d["data"])

        obj = cls(hdr, msg_data)

        return obj

    @classmethod
    def copy(cls, m: Message) -> Message:
        """Generate a copy of a message structure

        Args:
            m: Message structure to copy
        """
        return Message(
            MessageHeader.from_buffer_copy(m.header), m.data.from_buffer_copy(m.data)
        )
