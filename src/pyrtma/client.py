"""pyrtma.client module

Includes :py:class:`~Client` class and associated exception classes
"""

import socket
import select
import time
import os
import ctypes
from contextlib import contextmanager

from .message import Message, get_msg_cls
from .message_data import MessageData
from .header import MessageHeader, get_header_cls
from .exceptions import InvalidMessageDefinition, UnknownMessageType
from . import core_defs as cd

from functools import wraps
from typing import (
    Optional,
    Tuple,
    Type,
    Union,
    Iterable,
    Set,
    Callable,
    Any,
    TypeVar,
    cast,
)
from warnings import warn

__all__ = [
    "ClientError",
    "MessageManagerNotFound",
    "NotConnectedError",
    "ConnectionLost",
    "AcknowledgementTimeout",
    "InvalidDestinationModule",
    "InvalidDestinationHost",
    "Client",
    "client_context",
]


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


F = TypeVar("F", bound=Callable[..., Any])


def requires_connection(func: F) -> F:
    """Decorator wrapper for Client methods that require a connection"""

    @wraps(func)
    def wrapper(self, *args, **kwargs) -> F:
        if not self.connected:
            raise NotConnectedError
        else:
            return func(self, *args, **kwargs)

    return cast(F, wrapper)


class Client(object):
    """RTMA Client interface

    Args:
        module_id (optional): Static module ID, which must be unique.
            Defaults to 0, which generates a dynamic module ID.
        host_id (optional): Host ID. Defaults to 0.
        timecode (optional): Add additional timecode fields to message
            header, used by some projects at RNEL. Defaults to False.
    """

    def __init__(
        self,
        module_id: int = 0,
        host_id: int = 0,
        timecode: bool = False,
    ):
        if module_id >= cd.DYN_MOD_ID_START or module_id < 0:
            raise ValueError(f"Module ID must be >= 0 and < {cd.DYN_MOD_ID_START}")

        self._module_id = module_id
        self._host_id = host_id
        self._msg_count = 0
        self._server = ("", -1)
        self._connected = False
        self._header_cls = get_header_cls(timecode)
        self._recv_buffer = bytearray(1024**2)
        self._subscribed_types: Set[int] = set()
        self._paused_types: Set[int] = set()
        self._dynamic_id: bool = module_id == 0
        self._sock = socket.socket()

    def __del__(self):
        if self._connected:
            try:
                self.disconnect()
            except ClientError:
                """Silently ignore any errors at this point."""
                pass

    def _socket_connect(self, server_name: str):
        # Close the previously used socket
        self._connected = False
        self._sock.close()

        # Get the server ip info
        addr, port = server_name.split(":")
        self._server = (addr, int(port))

        # Create the tcp socket
        self._sock = socket.socket(
            family=socket.AF_INET, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
        )

        # Connect to the message server
        try:
            self._sock.connect(self._server)
            self._connected = True
        except ConnectionRefusedError as e:
            self._connected = False
            raise MessageManagerNotFound(
                f"No message manager server responding at {self.ip_addr}:{self.port}"
            ) from e

        # Disable Nagle Algorithm
        try:
            self._sock.setsockopt(socket.getprotobyname("tcp"), socket.TCP_NODELAY, 1)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception as e:
            self._connected = False
            self._sock.close()
            raise SocketOptionError from e

    def _connect_helper(self, logger_status: bool, daemon_status: bool) -> Message:
        """Called internally after _socket_connect"""

        # Reset the module_id to zero for dynamic assignment
        if self._dynamic_id:
            self._module_id = 0

        msg = cd.MDF_CONNECT()
        msg.logger_status = int(logger_status)
        msg.daemon_status = int(daemon_status)

        self.send_message(msg)
        ack_msg = self._wait_for_acknowledgement()

        # save own module ID from ACK if asked to be assigned dynamic ID
        if self._module_id == 0:
            self._module_id = ack_msg.header.dest_mod_id

        # reset subscribed and paused types
        self._subscribed_types = set()
        self._paused_types = set()

        return ack_msg

    def connect(
        self,
        server_name: str = "localhost:7111",
        logger_status: bool = False,
        daemon_status: bool = False,
    ):
        """Connect to message manager server

        Args:
            server_name (optional): IP_addr:port_num string associated with message manager.
                Defaults to "localhost:7111".
            logger_status (optional): Flag to declare client as a logger module.
                Logger modules are automatically subscribed to all message types.
                Defaults to False.
            daemon_status (optional): Flag to declare client as a daemon. Defaults to False.

        Raises:
            MessageManagerNotFound: Unable to connect to message manager
        """

        # Setup the underlying socket connection
        self._socket_connect(server_name)

        ack = self._connect_helper(logger_status, daemon_status)

    def disconnect(self):
        """Disconnect from message manager server"""
        try:
            if self._connected:
                self.send_signal(cd.MT_DISCONNECT)
                # Allow some time for signal to reach MM
                time.sleep(0.100)
        finally:
            if hasattr(self, "_sock"):
                self._sock.close()
            self._connected = False
            # reset subscribed and paused types
            self._subscribed_types = set()
            self._paused_types = set()

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
    def module_id(self) -> int:
        """Numeric module ID of client"""
        return self._module_id

    @property
    def sock(self) -> socket.socket:
        """Underlying socket connection with MessageManager"""
        return self._sock

    @property
    def header_cls(self) -> Type[MessageHeader]:
        """Class defining the RTMA message header"""
        return self._header_cls

    @property
    def subscribed_types(self) -> Set[int]:
        """List of subscribed message types"""
        return set(self._subscribed_types)

    @property
    def paused_subscribed_types(self) -> Set[int]:
        """Subscriptions on pause"""
        return set(self._paused_types)

    @requires_connection
    def send_module_ready(self):
        """Send a signal to message manager that client is ready

        This method also sends the client's process ID to message manager.
        """
        msg = cd.MDF_MODULE_READY()
        msg.pid = os.getpid()
        self.send_message(msg)

    def _subscription_control(self, msg_list: Iterable[int], ctrl_msg: str):
        msg_set = set(msg_list)
        msg: MessageData
        if ctrl_msg == "Subscribe":
            msg = cd.MDF_SUBSCRIBE()
            self._subscribed_types |= msg_set
            self._paused_types -= msg_set
        elif ctrl_msg == "Unsubscribe":
            msg = cd.MDF_UNSUBSCRIBE()
            self._subscribed_types -= msg_set
            self._paused_types -= msg_set
        elif ctrl_msg == "PauseSubscription":
            msg = cd.MDF_PAUSE_SUBSCRIPTION()
            self._subscribed_types -= msg_set
            self._paused_types |= msg_set
        elif ctrl_msg == "ResumeSubscription":
            msg = cd.MDF_RESUME_SUBSCRIPTION()
            self._subscribed_types |= msg_set
            self._paused_types -= msg_set
        else:
            raise TypeError("Unknown control message type.")

        for msg_type in msg_list:
            msg.msg_type = msg_type
            self.send_message(msg)

    @requires_connection
    def subscribe(self, msg_list: Iterable[int]):
        """Subscribe to message types

        Calling this method multiple times will add to, and not replace,
        the list of subscribed messages.

        Args:
            msg_list (Iterable[int]): A list of numeric message IDs to subscribe to
        """
        self._subscription_control(msg_list, "Subscribe")

    @requires_connection
    def unsubscribe(self, msg_list: Iterable[int]):
        """Unsubscribe from message types

        Args:
            msg_list (Iterable[int]): A list of numeric message IDs to unsubscribe to
        """
        self._subscription_control(msg_list, "Unsubscribe")

    @requires_connection
    def pause_subscription(self, msg_list: Iterable[int]):
        """Pause subscription to message types

        Args:
            msg_list (Iterable[int]): A list of numeric message IDs to temporarily unsubscribe to
        """
        self._subscription_control(msg_list, "PauseSubscription")

    @requires_connection
    def resume_subscription(self, msg_list: Iterable[int]):
        """Resume subscription to message types

        Args:
            msg_list (Iterable[int]): A list of paused message IDs to resubscribe to
        """
        self._subscription_control(msg_list, "ResumeSubscription")

    @requires_connection
    def unsubscribe_from_all(self):
        """Unsubscribe from all subscribed types"""
        self.unsubscribe(self.subscribed_types)

    @requires_connection
    def pause_all_subscriptions(self):
        """Pause all subscribed types"""
        self.pause_subscription(self.subscribed_types)

    @requires_connection
    def resume_all_subscriptions(self):
        """Resume all paused subscriptions"""
        self.resume_subscription(self.paused_subscribed_types)

    @contextmanager
    def subscription_context(self, msg_list: Iterable[int]):
        """Context manager to subscribe to a list of message types

        Message types will automatically unsubscribe after exiting context.

        Args:
            msg_list (Iterable[int]): A list of numeric message IDs to subscribe to
        """
        msg_list = list(msg_list)  # cast arbitrary iterable to list
        for mt in msg_list:
            if mt in self.subscribed_types:
                warn(
                    f"Message ID {mt} is already subscribed, ignored from subscription_context"
                )
                msg_list.remove(mt)

        self.subscribe(msg_list)
        yield
        self.unsubscribe(msg_list)

    @contextmanager
    def paused_subscription_context(self, msg_list: Iterable[int]):
        """Context manager to pause subscriptions to a list of message types

        Message types will automatically resume subscriptions after exiting context.

        Args:
            msg_list (Iterable[int]): A list of numeric message IDs to temporarily unsubscribe to
        """
        msg_list = list(msg_list)  # cast arbitrary iterable to list
        for mt in msg_list:
            if mt not in self.subscribed_types:
                warn(
                    f"Message ID {mt} is not subscribed, ignored from paused_subscription_context"
                )
                msg_list.remove(mt)

        self.pause_subscription(msg_list)
        yield
        self.resume_subscription(msg_list)

    @requires_connection
    def send_signal(
        self,
        signal_type: int,
        dest_mod_id: int = 0,
        dest_host_id: int = 0,
        timeout: float = -1,
    ):
        """Send a signal

        A signal is a message type without an associated data payload.
        Only a unique message type ID is required to send a signal.
        To send a message with data, see :py:func:`send_message`.

        Args:
            signal_type: Numeric message type ID of signal
            dest_mod_id (optional): Specific module ID to send to. Defaults to 0 (broadcast).
            dest_host_id (optional): Specific host ID to send to. Defaults to 0 (broadcast).
            timeout (optional): Timeout in seconds to wait for socket to be available for sending.
                Defaults to -1 (blocking).

        Raises:
            InvalidDestinationModule: Specified destination module is invalid
            InvalidDestinationHost: Specified destination host is invalid
        """
        # Verify that the module & host ids are valid
        if dest_mod_id < 0 or dest_mod_id > cd.MAX_MODULES:
            raise InvalidDestinationModule(f"Invalid dest_mod_id  of [{dest_mod_id}]")

        if dest_host_id < 0 or dest_host_id > cd.MAX_HOSTS:
            raise InvalidDestinationHost(f"Invalid dest_host_id of [{dest_host_id}]")

        if timeout >= 0:
            readfds, writefds, exceptfds = select.select([], [self._sock], [], timeout)
        else:
            readfds, writefds, exceptfds = select.select(
                [], [self._sock], []
            )  # blocking

        if writefds:
            header = self._header_cls()
            header.msg_type = signal_type
            header.msg_count = self._msg_count
            header.send_time = time.perf_counter()
            header.recv_time = 0.0
            header.src_host_id = self._host_id
            header.src_mod_id = self._module_id
            header.dest_host_id = dest_host_id
            header.dest_mod_id = dest_mod_id
            header.num_data_bytes = 0

            self._sendall(header)  # type: ignore

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
        """Send a message

        A message is a packet that contains a defined data payload.
        To send a message without associated data, see :py:func:`send_signal`.

        Args:
            msg_data: Object containing the message to send
            dest_mod_id (optional): Specific module ID to send to. Defaults to 0 (broadcast).
            dest_host_id (optional): Specific host ID to send to. Defaults to 0 (broadcast).
            timeout (optional): Timeout in seconds to wait for socket to be available for sending.
                Defaults to -1 (blocking).

        Raises:
            InvalidDestinationModule: Specified destination module is invalid
            InvalidDestinationHost: Specified destination host is invalid
        """
        # Verify that the module & host ids are valid
        if dest_mod_id < 0 or dest_mod_id > cd.MAX_MODULES:
            raise InvalidDestinationModule(f"Invalid dest_mod_id of [{dest_mod_id}]")

        if dest_host_id < 0 or dest_host_id > cd.MAX_HOSTS:
            raise InvalidDestinationHost(f"Invalid dest_host_id of [{dest_host_id}]")

        if timeout >= 0:
            readfds, writefds, exceptfds = select.select([], [self._sock], [], timeout)
        else:
            readfds, writefds, exceptfds = select.select(
                [], [self._sock], []
            )  # blocking

        if writefds:
            header = self._header_cls()
            header.msg_type = msg_data.type_id
            header.msg_count = self._msg_count
            header.send_time = time.perf_counter()
            header.recv_time = 0.0
            header.src_host_id = self._host_id
            header.src_mod_id = self._module_id
            header.dest_host_id = dest_host_id
            header.dest_mod_id = dest_mod_id
            header.num_data_bytes = ctypes.sizeof(msg_data)
            try:
                header.version = msg_data.type_hash
            except AttributeError as e:
                if not hasattr(msg_data, "type_hash"):
                    warn(
                        "Message class is missing type_hash. V1 message defs are deprecated.",
                        FutureWarning,
                    )
                else:
                    raise e

            self._sendall(header)  # type: ignore
            if header.num_data_bytes > 0:
                self._sendall(msg_data)  # type: ignore

            self._msg_count += 1

        else:
            # Socket was not ready to receive data. Drop the packet.
            print("x", end="")

    @requires_connection
    def forward_message(
        self,
        msg_hdr: MessageHeader,
        msg_data: Optional[MessageData] = None,
        timeout: float = -1,
    ):
        """Forward a message

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
            readfds, writefds, exceptfds = select.select([], [self._sock], [], timeout)
        else:
            readfds, writefds, exceptfds = select.select(
                [], [self._sock], []
            )  # blocking

        if writefds:
            self._sendall(msg_hdr)  # type: ignore
            if msg_data is not None:
                self._sendall(msg_data)  # type: ignore

            self._msg_count += 1

        else:
            # Socket was not ready to write data. Drop the packet.
            print("x", end="")

    def _sendall(self, buffer: bytearray):
        try:
            self._sock.sendall(buffer)
        except ConnectionError as e:
            self._connected = False
            raise ConnectionLost from e

    @requires_connection
    def read_message(
        self, timeout: Union[int, float, None] = -1, ack=False, sync_check=False
    ) -> Optional[Message]:
        """Read a message

        Args:
            timeout (optional): Timeout to wait for a message to be available for reading.
                Defaults to -1 (blocking).
            ack (optional): Primarily for internal use. When True, will not discard ACK messages. Defaults to False.
            sync_check (optional): Validate message definition matches header version. Defaults to False.

        Raises:
            ConnectionLost: Connection error to message manager server

        Returns:
            Message object. If no message is read before timeout, returns None.
        """
        t0 = time.perf_counter()
        M = self._read_message(timeout, ack, sync_check)

        # filter out unsubscribed messages that may still be in queue
        while M and M.header.msg_type not in self.subscribed_types:
            if (
                ack and M.header.msg_type == cd.MT_ACKNOWLEDGE
            ):  # ack input allows ACK to be read and not discarded
                break
            if timeout is None:  # blocking
                t_rem = None  # continue blocking until subscribed message recv'd
            elif timeout == 0:  # no timeout
                M = None  # discard unsub'd msg and break
                break
            else:  # subtract time elapsed from timeout and read again
                t_rem = max(timeout - (time.perf_counter() - t0), 0)
            M = self._read_message(timeout, ack, sync_check)

        return M

    @requires_connection
    def _read_message(
        self, timeout: Union[int, float, None] = -1, ack=False, sync_check=False
    ) -> Optional[Message]:
        """Read message without filtering for subscribed messages (helper called by read_message)"""

        if timeout is None:
            # Skip select call
            pass
        elif timeout >= 0:
            # Wait timeout amount
            readfds, writefds, exceptfds = select.select([self._sock], [], [], timeout)
            if len(readfds) == 0:
                return None
        else:
            # Blocking
            readfds, writefds, exceptfds = select.select([self._sock], [], [])
            if len(readfds) == 0:
                return None

        # Read RTMA Header Section
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

            header.recv_time = time.perf_counter()
        except ConnectionError:
            raise ConnectionLost

        # Read Data Section

        try:
            data = get_msg_cls(header.msg_type)()
        except UnknownMessageType as e:
            _ = self._sock.recv(header.num_data_bytes, socket.MSG_WAITALL)
            raise e

        type_size = data.type_size
        if type_size == -1:  # not defined for v1 message defs
            type_size = data.size

        if type_size != header.num_data_bytes:
            _ = self._sock.recv(header.num_data_bytes, socket.MSG_WAITALL)
            raise InvalidMessageDefinition(
                f"Received message header indicating a message data size ({header.num_data_bytes}) that does not match the expected size ({type_size}) of message type {data.type_name}. Message definitions may be out of sync across systems."
            )

        # Note: Ignore the sync check if header.version is not filled in
        # This can removed once all clients support this field.
        if sync_check and header.version != 0 and header.version != data.type_hash:
            _ = self._sock.recv(header.num_data_bytes, socket.MSG_WAITALL)
            raise InvalidMessageDefinition(
                f"Received message header indicating a message version that does not match the expected version of message type {data.type_name}. Message definitions may be out of sync across systems."
            )

        if header.num_data_bytes:
            try:
                nbytes = self._sock.recv_into(data, type_size, socket.MSG_WAITALL)

                if nbytes != type_size:
                    self._connected = False
                    raise ConnectionLost
            except ConnectionError:
                raise ConnectionLost

        return Message(header, data)

    def _wait_for_acknowledgement(self, timeout: float = 3) -> Message:
        """Wait for acknowledgement from message manager module

        Used internally when acknowledgement replies from message manager are expected

        Args:
            timeout (optional): Timeout in seconds to wait for ack message. Defaults to 3.

        Raises:
            AcknowledgementTimeout: Ack not received from message manager

        Returns:
            Ack message
        """
        ret = 0

        # Wait Forever
        if timeout == -1:
            while True:
                msg = self.read_message(ack=True)
                if msg is not None:
                    if msg.header.msg_type == cd.MT_ACKNOWLEDGE:
                        break
            return msg
        else:
            # Wait up to timeout seconds
            time_remaining = timeout
            start_time = time.perf_counter()
            while time_remaining > 0:
                msg = self.read_message(timeout=time_remaining, ack=True)
                if msg is not None:
                    if msg.header.msg_type == cd.MT_ACKNOWLEDGE:
                        return msg

                time_now = time.perf_counter()
                time_waited = time_now - start_time
                time_remaining = timeout - time_waited

            raise AcknowledgementTimeout(
                "Failed to receive Acknowlegement from MessageManager"
            )

    def discard_messages(self, timeout: float = 1) -> bool:
        """Read and discard messages in socket buffer up to timeout

        Args:
            timeout (optional): Maximum time in seconds to loop through message buffer.
                Defaults to 1.

        Returns:
            True if all messages have been read, False if messages remain in buffer
        """

        """Read and discard messages in socket buffer up to timeout.
        Returns: True if all messages available have been read.
        """
        start_time = time.perf_counter()

        def read_and_time():
            msg = self.read_message(0)
            time_now = time.perf_counter()
            time_waited = time_now - start_time
            time_remaining = timeout - time_waited
            return msg, time_remaining

        msg, time_remaining = read_and_time()
        while msg is not None and time_remaining > 0:
            msg, time_remaining = read_and_time()
        return not msg

    def __str__(self) -> str:
        # TODO: Make this better.
        return f"Client(module_id={self.module_id}, server={self.server}, connected={self.connected}."


@contextmanager
def client_context(
    module_id: int = 0,
    server_name: str = "localhost:7111",
    msg_list: Optional[Iterable[int]] = None,
    host_id: int = 0,
    timecode: bool = False,
    logger_status: bool = False,
    daemon_status: bool = False,
):
    """Context manager function to simplify initializing a pyrtma Client

    Context manager will yield a Client object after connecting to message manager,
    optionally subscribing to msg_list, and after calling send_module_ready().
    Client will disconnect when exiting context.

    Args:
        module_id (optional): Static module ID, which must be unique.
            Defaults to 0, which generates a dynamic module ID.
        server_name (optional): IP_addr:port_num string associated with message manager.
                Defaults to "localhost:7111".
        msg_list (optional): A list of numeric message IDs to subscribe to
        host_id (optional): Host ID. Defaults to 0.
        timecode (optional): Add additional timecode fields to message
            header, used by some projects at RNEL. Defaults to False.
        logger_status (optional): Flag to declare client as a logger module.
            Logger modules are automatically subscribed to all message types.
            Defaults to False.
        daemon_status (optional): Flag to declare client as a daemon. Defaults to False.

    Yields:
        Client: initialized pyrtma Client object
    """
    c = Client(module_id, host_id, timecode)
    c.connect(server_name, logger_status, daemon_status)
    if msg_list:
        c.subscribe(msg_list)
    c.send_module_ready()
    yield c
    c.disconnect()
