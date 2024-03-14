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


class ClientError(Exception):
    """Base exception for all Client Errors."""

    pass


class MessageManagerNotFound(ClientError):
    """Raised when unable to connect to message manager."""

    pass


class SocketOptionError(ClientError):
    """Raised when unable to set socket options."""

    pass


class NotConnectedError(ClientError):
    """Raised when the client tries to read/write while not connected."""

    pass


class ConnectionLost(ClientError):
    """Raised when there is a connection error with the server."""

    pass


class AcknowledgementTimeout(ClientError):
    """Raised when client does not receive ack from message manager."""

    pass


class InvalidDestinationModule(ClientError):
    """Raised when client tries to send to an invalid module."""

    pass


class InvalidDestinationHost(ClientError):
    """Raised when client tries to send to an invalid host."""

    pass
