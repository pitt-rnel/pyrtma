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


class VersionMismatchWarning(UserWarning):
    """Raised when import message defs were compiled with a different pyrtma version"""

    pass
