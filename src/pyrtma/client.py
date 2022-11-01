import socket
import select
import time
import os
import ctypes

from ._core import *
from .constants import *

from functools import wraps
from typing import List, Optional, Tuple, Type, Union, Dict

__all__ = [
    "ClientError",
    "MessageManagerNotFound",
    "NotConnectedError",
    "ConnectionLost",
    "AcknowledgementTimeout",
    "InvalidDestinationModule",
    "InvalidDestinationHost",
    "Client",
]


class ClientError(Exception):
    """Base exception for all Client Errors."""

    pass


class MessageManagerNotFound(ClientError):
    """Raised when unable to connect to message manager."""

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


def requires_connection(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        if not self.connected:
            raise NotConnectedError
        else:
            return func(self, *args, **kwargs)

    return wrapper


class Client(object):
    def __init__(
        self,
        module_id: int = 0,
        host_id: int = 0,
        timecode: bool = False,
    ):
        self._module_id = module_id
        self._host_id = host_id
        self._msg_count = 0
        self._server = ("", -1)
        self._connected = False
        self._header_cls = get_header_cls(timecode)
        self._recv_buffer = bytearray(1024**2)

    def __del__(self):
        if self._connected:
            try:
                self.disconnect()
            except ClientError:
                """Siliently ignore any errors at this point."""
                pass

    def connect(
        self,
        server_name: str = "localhost:7111",
        logger_status: bool = False,
        daemon_status: bool = False,
    ):

        addr, port = server_name.split(":")
        self._server = (addr, int(port))

        # Create the tcp socket
        self._sock = socket.socket(
            family=socket.AF_INET, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
        )

        # Connect to the message server
        try:
            self._connected = True
            self._sock.connect(self._server)
        except ConnectionRefusedError as e:
            self._connected = False
            raise MessageManagerNotFound(
                f"No message manager server responding at {self.ip_addr}:{self.port}"
            ) from e

        # Disable Nagle Algorithm
        self._sock.setsockopt(socket.getprotobyname("tcp"), socket.TCP_NODELAY, 1)

        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        msg = CONNECT()
        msg.logger_status = int(logger_status)
        msg.daemon_status = int(daemon_status)

        self.send_message(msg)
        ack_msg = self.wait_for_acknowledgement()

        # save own module ID from ACK if asked to be assigned dynamic ID
        if self._module_id == 0:
            self._module_id = ack_msg.header.dest_mod_id

    def disconnect(self):
        try:
            if self._connected:
                self.send_signal(MT_DISCONNECT)
                ack_msg = self.wait_for_acknowledgement(timeout=0.5)
        except AcknowledgementTimeout:
            pass
        finally:
            self._sock.close()
            self._connected = False

    @property
    def server(self) -> Tuple[str, int]:
        return self._server

    @property
    def ip_addr(self) -> str:
        return self._server[0]

    @property
    def port(self) -> int:
        return self._server[1]

    @property
    def connected(self) -> bool:
        return self._connected

    @property
    def msg_count(self) -> int:
        return self._msg_count

    @property
    def module_id(self) -> int:
        return self._module_id

    @property
    def header_cls(self) -> Type[MessageHeader]:
        return self._header_cls

    @requires_connection
    def send_module_ready(self):
        msg = MODULE_READY()
        msg.pid = os.getpid()
        self.send_message(msg)

    def _subscription_control(self, msg_list: List[int], ctrl_msg: str):
        if not isinstance(msg_list, list):
            msg_list = [msg_list]

        if ctrl_msg == "Subscribe":
            msg = SUBSCRIBE()
        elif ctrl_msg == "Unsubscribe":
            msg = UNSUBSCRIBE()
        elif ctrl_msg == "PauseSubscription":
            msg = PAUSE_SUBSCRIPTION()
        elif ctrl_msg == "ResumeSubscription":
            msg = RESUME_SUBSCRIPTION()
        else:
            raise TypeError("Unknown control message type.")

        for msg_type in msg_list:
            msg.msg_type = msg_type
            self.send_message(msg)

    @requires_connection
    def subscribe(self, msg_list: List[int]):
        self._subscription_control(msg_list, "Subscribe")

    @requires_connection
    def unsubscribe(self, msg_list: List[int]):
        self._subscription_control(msg_list, "Unsubscribe")

    @requires_connection
    def pause_subscription(self, msg_list: List[int]):
        self._subscription_control(msg_list, "PauseSubscription")

    @requires_connection
    def resume_subscription(self, msg_list: List[int]):
        self._subscription_control(msg_list, "ResumeSubscription")

    @requires_connection
    def send_signal(
        self,
        signal_type: int,
        dest_mod_id: int = 0,
        dest_host_id: int = 0,
        timeout: float = -1,
    ):

        # Verify that the module & host ids are valid
        if dest_mod_id < 0 or dest_mod_id > MAX_MODULES:
            raise InvalidDestinationModule(f"Invalid dest_mod_id  of [{dest_mod_id}]")

        if dest_host_id < 0 or dest_host_id > MAX_HOSTS:
            raise InvalidDestinationHost(f"Invalid dest_host_id of [{dest_host_id}]")

        # Assume that msg_type, num_data_bytes, data - have been filled in
        header = self._header_cls()
        header.msg_type = signal_type
        header.msg_count = self._msg_count
        header.send_time = time.time()
        header.recv_time = 0.0
        header.src_host_id = self._host_id
        header.src_mod_id = self._module_id
        header.dest_host_id = dest_host_id
        header.dest_mod_id = dest_mod_id
        header.num_data_bytes = 0

        if timeout >= 0:
            readfds, writefds, exceptfds = select.select([], [self._sock], [], timeout)
        else:
            readfds, writefds, exceptfds = select.select(
                [], [self._sock], []
            )  # blocking

        if writefds:
            self._sendall(header)

            self._msg_count += 1

        else:
            # Socket was not ready to receive data. Drop the packet.
            print("x", end="")

    @requires_connection
    def send_message(
        self,
        msg_data: MessageData,
        dest_mod_id: int = 0,
        dest_host_id: int = 0,
        timeout: float = -1,
    ):
        # Verify that the module & host ids are valid
        if dest_mod_id < 0 or dest_mod_id > MAX_MODULES:
            raise InvalidDestinationModule(f"Invalid dest_mod_id of [{dest_mod_id}]")

        if dest_host_id < 0 or dest_host_id > MAX_HOSTS:
            raise InvalidDestinationHost(f"Invalid dest_host_id of [{dest_host_id}]")

        # Assume that msg_type, num_data_bytes, data - have been filled in
        header = self._header_cls()
        header.msg_type = msg_data.type_id
        header.msg_count = self._msg_count
        header.send_time = time.time()
        header.recv_time = 0.0
        header.src_host_id = self._host_id
        header.src_mod_id = self._module_id
        header.dest_host_id = dest_host_id
        header.dest_mod_id = dest_mod_id
        header.num_data_bytes = ctypes.sizeof(msg_data)

        if timeout >= 0:
            readfds, writefds, exceptfds = select.select([], [self._sock], [], timeout)
        else:
            readfds, writefds, exceptfds = select.select(
                [], [self._sock], []
            )  # blocking

        if writefds:
            self._sendall(header)
            if header.num_data_bytes > 0:
                self._sendall(msg_data)

            self._msg_count += 1

        else:
            # Socket was not ready to receive data. Drop the packet.
            print("x", end="")

    def _sendall(self, buffer: bytearray):
        try:
            self._sock.sendall(buffer)
        except ConnectionError as e:
            self._connected = False
            raise ConnectionLost from e

    @requires_connection
    def read_message(
        self, timeout: Union[int, float] = -1, ack=False
    ) -> Optional[Message]:
        if timeout >= 0:
            readfds, writefds, exceptfds = select.select([self._sock], [], [], timeout)
        else:
            readfds, writefds, exceptfds = select.select(
                [self._sock], [], []
            )  # blocking

        # Read RTMA Header Section
        if readfds:
            header = self._header_cls()
            try:
                nbytes = self._sock.recv_into(header, header.size, socket.MSG_WAITALL)
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
        else:
            return None

        # Read Data Section
        data = header.get_data()
        if header.num_data_bytes:
            try:
                nbytes = self._sock.recv_into(data, data.size, socket.MSG_WAITALL)

                if nbytes != data.size:
                    self._connected = False
                    raise ConnectionLost
            except ConnectionError:
                raise ConnectionLost

        return Message(header, data)

    def wait_for_acknowledgement(self, timeout: float = 3):
        ret = 0

        # Wait Forever
        if timeout == -1:
            while True:
                msg = self.read_message(ack=True)
                if msg is not None:
                    if msg.header.msg_type == MT_ACKNOWLEDGE:
                        break
            return msg
        else:
            # Wait up to timeout seconds
            time_remaining = timeout
            start_time = time.perf_counter()
            while time_remaining > 0:
                msg = self.read_message(timeout=time_remaining, ack=True)
                if msg is not None:
                    if msg.header.msg_type == MT_ACKNOWLEDGE:
                        return msg

                time_now = time.perf_counter()
                time_waited = time_now - start_time
                time_remaining = timeout - time_waited

            raise AcknowledgementTimeout(
                "Failed to receive Acknowlegement from MessageManager"
            )

    def discard_messages(self, timeout: float = 1) -> bool:
        """Read and discard messages in socket buffer up to timeout.
        Returns: True if all messages available have been read.
        """
        msg = 1
        time_remaining = timeout
        start_time = time.perf_counter()
        while msg is not None and time_remaining > 0:
            msg = self.read_message(timeout=0)
            time_now = time.perf_counter()
            time_waited = time_now - start_time
            time_remaining = timeout - time_waited
        return not msg

    def __str__(self) -> str:
        # TODO: Make this better.
        return f"Client(module_id={self.module_id}, server={self.server}, connected={self.connected}."
