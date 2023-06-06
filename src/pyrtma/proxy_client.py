"""pyrtma.client module

Includes :py:class:`~Client` class and associated exception classes
"""
import socket
import select
import time
import os
import ctypes

from ._core import *
from .constants import *
from .client import (
    ClientError,
    MessageManagerNotFound,
    NotConnectedError,
    ConnectionLost,
)

from functools import wraps
from typing import List, Optional, Tuple, Type, Union, Dict

__all__ = [
    "ProxyClient",
]


def requires_connection(func):
    """Decorator wrapper for Client methods that require a connection"""

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.connected:
            raise NotConnectedError
        else:
            return func(self, *args, **kwargs)

    return wrapper


class ProxyClient(object):
    """RTMA Web Client interface

    Args:
        module_id (optional): Static module ID, which must be unique.
            Defaults to 0, which generates a dynamic module ID.
        host_id (optional): Host ID. Defaults to 0.
        timecode (optional): Add additional timecode fields to message
            header, used by some projects at RNEL. Defaults to False.
    """

    def __init__(self):
        self._msg_count = 0
        self._server = ("", -1)
        self._connected = False
        self._header_cls = get_header_cls(timecode=False)
        self._recv_buffer = bytearray(1024**2)

    def __del__(self):
        if self._connected:
            try:
                self.disconnect()
            except ClientError:
                """Silently ignore any errors at this point."""
                pass

    def connect(self, server_name: str = "localhost:7111"):
        """Connect to message manager server

        Args:
            server_name (optional): IP_addr:port_num string associated with message manager.
                Defaults to "localhost:7111".
        Raises:
            MessageManagerNotFound: Unable to connect to message manager
        """
        addr, port = server_name.split(":")
        self._server = (addr, int(port))

        # Create the tcp socket
        self.sock = socket.socket(
            family=socket.AF_INET, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
        )

        # Connect to the message server
        try:
            self._connected = True
            self.sock.connect(self._server)
        except ConnectionRefusedError as e:
            self._connected = False
            raise MessageManagerNotFound(
                f"No message manager server responding at {self.ip_addr}:{self.port}"
            ) from e

        # Disable Nagle Algorithm
        self.sock.setsockopt(socket.getprotobyname("tcp"), socket.TCP_NODELAY, 1)

        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    def disconnect(self):
        """Disconnect from message manager server"""
        if self._connected:
            self.sock.close()
            self._connected = False

    @property
    def server(self) -> Tuple[str, int]:
        """Message manager server address as a (IP_addr, port_num) tuple"""
        return self._server

    @property
    def ip_addr(self) -> str:
        """Message manager IP address string"""
        return self._server[0]

    @property
    def port(self) -> int:
        """Message manager port number"""
        return self._server[1]

    @property
    def connected(self) -> bool:
        """Status of connection to message manager server"""
        return self._connected

    @property
    def msg_count(self) -> int:
        """Count of messages that have been sent"""
        return self._msg_count

    @property
    def header_cls(self) -> Type[MessageHeader]:
        """Class defining the RTMA message header"""
        return self._header_cls

    @requires_connection
    def forward_message(
        self,
        msg_hdr: MessageHeader,
        msg_data: Optional[MessageData] = None,
        timeout: float = -1,
    ):
        """Send a message

        A message is a packet that contains a defined data payload.
        To send a message without associated data, see :py:func:`send_signal`.

        Args:
            msg_hdr: Object containing RTMA header to send
            msg_data: Object containing the message to send
            timeout (optional): Timeout in seconds to wait for socket to be available for sending.
                Defaults to -1 (blocking).

        """
        # Assume that msg_type, num_data_bytes, data - have been filled in
        if msg_data is not None:
            msg_hdr.num_data_bytes = ctypes.sizeof(msg_data)

        if timeout >= 0:
            readfds, writefds, exceptfds = select.select([], [self.sock], [], timeout)
        else:
            readfds, writefds, exceptfds = select.select(
                [], [self.sock], []
            )  # blocking

        if writefds:
            self._sendall(msg_hdr)
            if msg_data is not None:
                self._sendall(msg_data)

            self._msg_count += 1

        else:
            # Socket was not ready to write data. Drop the packet.
            print("x", end="")

    def _sendall(self, buffer: bytearray):
        try:
            self.sock.sendall(buffer)
        except ConnectionError as e:
            self._connected = False
            raise ConnectionLost from e

    @requires_connection
    def read_message(self) -> Optional[Message]:
        """Read a message

        Args:

        Raises:
            ConnectionLost: Connection error to message manager server

        Returns:
            Message object. If no message is read before timeout, returns None.
        """

        # Read RTMA Header Section
        header = self._header_cls()
        try:
            nbytes = self.sock.recv_into(header, header.size, socket.MSG_WAITALL)
            """
            Note:
            MSG_WAITALL Flag:
            The receive request will complete only when one of the following events occurs:
            The buffer supplied by the caller is completely full.
            The connection has been closed.
            The request has been canceled or an error occurred.
            """

            if nbytes != header.size:
                self._connected = False
                raise ConnectionLost

            header.recv_time = time.time()
        except ConnectionError:
            raise ConnectionLost

        # Read Data Section
        data = header.get_data()
        if header.num_data_bytes:
            try:
                nbytes = self.sock.recv_into(data, data.size, socket.MSG_WAITALL)

                if nbytes != data.size:
                    self._connected = False
                    raise ConnectionLost
            except ConnectionError:
                raise ConnectionLost

        return Message(header, data)

    def __str__(self) -> str:
        # TODO: Make this better.
        return f"WebClient(server={self.server}, connected={self.connected}."
