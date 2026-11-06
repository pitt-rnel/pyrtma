"""pyrtma.client module

Includes :py:class:`~Client` class and associated exception classes
"""

from shlex import split
import socket
import select
import struct
import time
import os
import ctypes
import logging
import sys

from contextlib import contextmanager

from .message import Message
from .message_data import MessageData
from .header import MessageHeader, get_header_cls
from .core_defs import ALL_MESSAGE_TYPES
from .definitions import MessageDefinitions
from .loader import (
    is_message_definitions_module,
    get_message_definitions_from_module,
)
from .validators import disable_message_validation
from .client_logging import RTMALogger, ClientLike
from .exceptions import (
    InvalidMessageDefinition,
    UnknownMessageType,
    ClientError,
    SocketOptionError,
    MessageManagerNotFound,
    NotConnectedError,
    ConnectionLost,
    AcknowledgementTimeout,
    InvalidDestinationModule,
    InvalidDestinationHost,
    InvalidSubscription,
    MessageDefinitionsLoadError,
)

from . import core_defs as cd

from functools import wraps
from typing import (
    Dict,
    Optional,
    Tuple,
    Type,
    List,
    Union,
    Iterable,
    Iterator,
    Set,
    Callable,
    Any,
    TypeVar,
    cast,
)
from types import ModuleType

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

F = TypeVar("F", bound=Callable[..., Any])

# The largest payload the client accepts. It matches the message manager's
# receive buffer, so anything the manager forwards is accepted. A header that
# announces more than this, or less than zero, means the stream is corrupt.
_MAX_DATA_BYTES: int = 1024**2

# Header fields read from the raw bytes rather than through the header's
# attribute hooks, which cost several times as much.
_INT32 = struct.Struct("i")
_MSG_TYPE_OFFSET: int = MessageHeader._msg_type.offset  # type: ignore[attr-defined]
_NUM_DATA_BYTES_OFFSET: int = MessageHeader._num_data_bytes.offset  # type: ignore[attr-defined]

# A deadline that has always passed: a read given it takes only what has
# already arrived.
_NO_WAIT: float = float("-inf")

# The port used when a server name doesn't give one.
DEFAULT_PORT: int = 7111

# How long disconnect() waits for the manager to close its end, in seconds.
_DISCONNECT_WAIT: float = 0.1

# The module's own logger, for events that mustn't go through a client's RTMA
# logger: logging a dropped send through it would send another message.
_log = logging.getLogger(__name__)


def _split_server_name(server_name: str) -> Tuple[str, int]:
    """Split a ``host:port`` server name.

    Args:
        server_name: ``host:port``, or ``host`` alone for ``DEFAULT_PORT``.

    Returns:
        The host and the port number.

    Raises:
        ValueError: The host is empty, or the port isn't a number from 1 to
            65535.
    """
    host, sep, port = server_name.rpartition(":")
    if not sep:
        host, number = server_name, DEFAULT_PORT
    else:
        try:
            number = int(port)
        except ValueError:
            number = 0
    if not host or not 0 < number < 65536:
        raise ValueError(
            f"Invalid server name {server_name!r}: expected host:port or host."
        )
    return host, number


def _remaining(deadline: Optional[float]) -> Optional[float]:
    """Seconds left until a ``perf_counter`` deadline.

    Args:
        deadline: The deadline, or None for no deadline.

    Returns:
        The seconds left, at least 0, or None for no deadline.
    """
    if deadline is None:
        return None
    return max(deadline - time.perf_counter(), 0.0)


def _check_destination(dest_mod_id: int, dest_host_id: int) -> None:
    """Check a message's destination, as both send methods do.

    Args:
        dest_mod_id: 0 for every module, or a static or dynamic module ID, up
            to ``MAX_MODULE_ID``.
        dest_host_id: 0 to ``MAX_HOSTS``, or ``ALL_HOSTS``.

    Raises:
        InvalidDestinationModule: The module ID is out of range.
        InvalidDestinationHost: The host ID is out of range.
    """
    if dest_mod_id < 0 or dest_mod_id > cd.MAX_MODULE_ID:
        raise InvalidDestinationModule(f"Invalid dest_mod_id of [{dest_mod_id}]")

    if dest_host_id != cd.ALL_HOSTS and (
        dest_host_id < 0 or dest_host_id > cd.MAX_HOSTS
    ):
        raise InvalidDestinationHost(f"Invalid dest_host_id of [{dest_host_id}]")


def requires_connection(func: F) -> F:
    """Decorator wrapper for Client methods that require a connection"""

    @wraps(func)
    def wrapper(self, *args, **kwargs) -> F:
        if not self.connected:
            raise NotConnectedError
        else:
            return func(self, *args, **kwargs)

    return cast(F, wrapper)


class Client(ClientLike):
    """RTMA Client interface

    Args:
        module_id (optional): Static module ID, which must be unique.
            Defaults to 0, which generates a dynamic module ID.
        host_id (optional): Host ID. Defaults to 0.
        name (optional): Name of module. Defaults to "". This and the
            arguments after it are keyword-only.
        definitions (optional): MessageDefinitions object or Module containing MessageDefinitions. Defaults to None, which will auto-detect
            message definitions from the current module or use core_defs if not found.
        auto_detect (optional): If True, will attempt to auto-detect message definitions
            from the current module. If False, will use core_defs. Defaults to True.

    """

    def __init__(
        self,
        module_id: int = 0,
        host_id: int = 0,
        *,
        name: str = "",
        definitions: Optional[MessageDefinitions | ModuleType] = None,
        auto_detect: bool = True,
    ):
        if module_id >= cd.DYN_MOD_ID_START or module_id < 0:
            raise ValueError(f"Module ID must be >= 0 and < {cd.DYN_MOD_ID_START}")

        self._module_id = module_id
        self._host_id = host_id
        self._msg_count = 0
        self._server = ("", -1)
        self._connected = False
        self._header_cls = get_header_cls()
        self._header_size = ctypes.sizeof(self._header_cls)
        # The message being received, straight into the objects it is
        # returned in: the header into a new header object, then the payload
        # into a new message object, or into a bytearray if the message can't
        # be decoded. _rx_target is the one being filled, _rx_size its size,
        # and _rx_have how much has arrived. A read can end mid-message; the
        # next one carries on.
        self._rx_header: Optional[MessageHeader] = None
        self._rx_payload: Union[MessageData, bytearray, None] = None
        self._rx_target: Union[MessageHeader, MessageData, bytearray, None] = None
        self._rx_size = 0
        self._rx_have = 0
        self._sub_all = False
        self._subscribed_types: Set[int] = set()
        self._paused_types: Set[int] = set()
        self._dynamic_id: bool = module_id == 0
        self._sock = socket.socket()
        self._name = name

        self._logger = RTMALogger(
            self._name or f"Module {module_id}", self, logging.INFO
        )

        # alias logger methods
        self.debug = self._logger.debug
        self.info = self._logger.info
        self.warning = self._logger.warning
        self.warn = self._logger.warn
        self.error = self._logger.error
        self.exception = self._logger.exception
        self.critical = self._logger.critical

        # Determine which message definitions to use
        self._definitions = self._get_definitions(definitions, auto_detect)

        # Auto-assign a name if module-id is defined
        if name == "" and module_id != 0:
            self._name = self.module_name_from_id(module_id) or ""
        else:
            self._name = name

    def _auto_detect_definitions(self) -> MessageDefinitions:
        """Find the one compiled definitions module that has been imported.

        Modules that share one ``get_message_definitions`` function count as
        one, because ``from defs import *`` copies it into the importing
        module. Modules whose names start with ``_``, pyrtma's own, and the
        standard library's are skipped.

        Raises:
            MessageDefinitionsLoadError: More than one definitions module is
                loaded, so the choice would be a guess.

        Returns:
            That module's definitions, or the core definitions if there is
            none.
        """
        # Prune the modules to only those that are not built-in or standard library modules
        skipped = set(sys.builtin_module_names) | sys.stdlib_module_names

        # The modules found, keyed by their get_message_definitions function,
        # in import order. sys.modules is copied: an import in another thread
        # can change it.
        found: Dict[int, List[str]] = {}
        getters: Dict[int, ModuleType] = {}
        for name, mod in list(sys.modules.items()):
            if name in skipped or mod is None:
                continue

            if name == "pyrtma" or name.startswith("pyrtma."):
                continue

            if name.startswith("_"):
                continue

            if is_message_definitions_module(mod):
                key = id(mod.get_message_definitions)
                found.setdefault(key, []).append(name)
                getters.setdefault(key, mod)

        if len(found) > 1:
            names = "; ".join(", ".join(names) for names in found.values())
            raise MessageDefinitionsLoadError(
                "Message definitions were found in more than one loaded module "
                f"({names}). Pass definitions= to the client to choose one."
            )

        if found:
            ((key, names),) = found.items()
            self.debug(f"Auto-detected message definitions from module: {names[0]}")
            return get_message_definitions_from_module(getters[key])

        # Return core_defs if no other message definitions found
        self.debug("No message definitions found in loaded modules, using core_defs")
        return cd.get_message_definitions()

    def _get_definitions(
        self, definitions: Optional[MessageDefinitions | ModuleType], auto_detect: bool
    ) -> MessageDefinitions:
        """Determine which message definitions to use"""
        if isinstance(definitions, MessageDefinitions):
            return definitions
        elif isinstance(definitions, ModuleType):
            if is_message_definitions_module(definitions):
                self.debug(
                    f"Using message definitions from module {definitions.__name__}"
                )
                return get_message_definitions_from_module(definitions)
            else:
                raise MessageDefinitionsLoadError(
                    f"Module {definitions.__name__} does not have message definitions"
                )
        elif definitions is None:
            # Check for message definitions in PYRTMA_MSGDEF_MODULES environment variable
            # Allows for multiple modules to be specified, separated by semicolons
            # example: PYRTMA_MSGDEF_MODULES=module1;module2;module3
            # First module that has message definitions will be used. If none found, will fall back to auto-detect or core_defs.
            success = False
            if mod_names := os.getenv("PYRTMA_MSGDEF_MODULES"):
                mod_list = mod_names.removesuffix(";").split(";")
                # Find the first module that has message definitions
                for mod_name in mod_list:
                    mod = sys.modules.get(mod_name)
                    if mod is not None:
                        if is_message_definitions_module(mod):
                            self.debug(
                                f"Using message definitions from module {mod_name}"
                            )
                            success = True
                            return get_message_definitions_from_module(mod)
                else:
                    self.warning(
                        "Warning: No message definitions found in PYRTMA_MSGDEF_MODULES list, Falling back to auto-detect or core_defs."
                    )

            if not success:
                if auto_detect:
                    return self._auto_detect_definitions()
                else:
                    self.warning(
                        "Warning: No message definitions provided, using core_defs only!"
                    )

            return cd.get_message_definitions()

        else:
            raise TypeError(
                f"Invalid type for definitions: {type(definitions)}. Must be MessageDefinitions or ModuleType."
            )

    @property
    def logger(self) -> RTMALogger:
        return self._logger

    @property
    def definitions(self) -> MessageDefinitions:
        return self._definitions

    def get_msg_cls(self, msg_type: int) -> Type[MessageData]:
        return self._definitions.get_msg_cls(msg_type)

    def message_name_from_id(self, message_id: int) -> Optional[str]:
        return self._definitions.message_name_from_id(message_id)

    def message_id_from_name(self, message_name: str) -> Optional[int]:
        return self._definitions.message_id_from_name(message_name)

    def module_name_from_id(self, module_id: int) -> Optional[str]:
        return self._definitions.module_name_from_id(module_id)

    def module_id_from_name(self, module_name: str) -> Optional[int]:
        return self._definitions.module_id_from_name(module_name)

    def __del__(self):
        # getattr: the constructor may have raised before setting _connected.
        if getattr(self, "_connected", False):
            try:
                # During garbage collection, don't wait for the manager.
                self._disconnect(wait=0.0)
            except Exception:
                """Silently ignore any errors at this point."""
                pass

    def _socket_connect(self, server_name: str, deadline: Optional[float] = None):
        """Open the TCP connection to the message manager.

        Note that this is also used by web_manager.

        Args:
            server_name: ``host:port``, or ``host`` for ``DEFAULT_PORT``.
            deadline: A ``perf_counter`` time by which the connection must be
                made, or None to wait as long as the system does. The name
                lookup isn't bounded by it.

        Raises:
            ValueError: The server name is malformed.
            MessageManagerNotFound: The host couldn't be found or reached,
                refused the connection, or didn't answer before the deadline.
            SocketOptionError: A socket option couldn't be set.
        """
        # Close the previously used socket
        self._connected = False
        self._sock.close()
        self._reset_receive()

        # Get the server ip info
        self._server = _split_server_name(server_name)

        # Create the tcp socket
        self._sock = socket.socket(
            family=socket.AF_INET, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
        )

        # Connect to the message server. Every failure here, a failed name
        # lookup and a timeout included, is an OSError.
        try:
            self._sock.settimeout(_remaining(deadline))
            self._sock.connect(self._server)
        except OSError as e:
            self._sock.close()
            raise MessageManagerNotFound(
                f"No message manager server responding at {self.ip_addr}:{self.port}: {e}"
            ) from e
        self._connected = True

        # Reads and writes never block in the socket itself: waiting is done
        # in select(), which can be given a timeout. See _recv_frame and
        # _sendall.
        self._sock.setblocking(False)

        # Disable Nagle Algorithm
        try:
            self._sock.setsockopt(socket.getprotobyname("tcp"), socket.TCP_NODELAY, 1)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        except Exception as e:
            self._connected = False
            self._sock.close()
            raise SocketOptionError from e

    def _connect_helper(
        self, logger_status: bool, timeout: Optional[float] = 3
    ) -> Message:
        """Called internally after _socket_connect

        Note that this is also used by web_manager

        Args:
            logger_status: Whether to connect as a logger module.
            timeout: Seconds to wait for the manager's ACK; None blocks.

        Raises:
            AcknowledgementTimeout: No ACK for this client arrived in time.
            ConnectionLost: The connection failed. The client is disconnected.

        Returns:
            The ACK.
        """

        # Reset the module_id to zero for dynamic assignment
        if self._dynamic_id:
            self._module_id = 0

        msg = cd.MDF_CONNECT()
        msg.logger_status = int(logger_status)

        msg2 = cd.MDF_CONNECT_V2()
        msg2.logger_status = int(logger_status)
        msg2.pid = os.getpid()
        msg2.mod_id = self.module_id
        msg2.name = self.name

        self.send_message(msg2)
        # self.send_message(msg)
        ack_msg = self._wait_for_acknowledgement(timeout)

        # save own module ID from ACK if asked to be assigned dynamic ID
        if self._module_id == 0:
            self._module_id = ack_msg.header.dest_mod_id

        # reset subscribed and paused types
        self._subscribed_types = set()
        self._paused_types = set()
        self._sub_all = False

        self.logger.log_name = self._name or f"Module {self._module_id}"

        return ack_msg

    @property
    def log_level(self) -> int:
        return self._logger.level

    @log_level.setter
    def log_level(self, level: int):
        self._logger.set_all_levels(level)

    @property
    def name(self) -> str:
        return self._name

    def connect(
        self,
        server_name: str = "localhost:7111",
        logger_status: bool = False,
        *,
        timeout: Optional[float] = 5.0,
    ):
        """Connect to message manager server

        If the connection fails, the client is left disconnected.

        Args:
            server_name (optional): IP_addr:port_num string associated with message manager.
                The port may be left out, for 7111. Defaults to "localhost:7111".
            logger_status (optional): Flag to declare client as a logger module.
                A logger module is sent the messages it subscribes to even when
                they are addressed to another module, and copies of other
                modules' ACKs, and by default the manager waits for it rather
                than dropping messages. It isn't subscribed to anything
                automatically: subscribe to ``ALL_MESSAGE_TYPES`` to receive
                everything.
                Defaults to False.
            timeout (optional): Seconds to wait for the connection and the
                manager's ACK together; None waits as long as it takes. Looking
                up the host's name isn't bounded by it. Keyword-only. Defaults
                to 5.

        Raises:
            ValueError: The server name is malformed.
            MessageManagerNotFound: Unable to connect to message manager: the
                host couldn't be found or reached, refused the connection, or
                didn't answer in time.
            AcknowledgementTimeout: The manager didn't acknowledge the
                connection in time.
            ConnectionLost: The connection failed during the handshake.
        """
        deadline = self._deadline(timeout)

        # Disconnect first
        if self.connected:
            self.disconnect()

        try:
            # Setup the underlying socket connection
            self._socket_connect(server_name, deadline)
            self._connect_helper(logger_status, _remaining(deadline))
        except BaseException:
            # Leave nothing behind: no open socket, no connected flag.
            self._connection_lost()
            raise

    def disconnect(self):
        """Disconnect from message manager server

        ``DISCONNECT`` is sent, and the client waits briefly, up to 0.1 s, for
        the manager to close its end before closing the socket.
        """
        self._disconnect(_DISCONNECT_WAIT)

    def _disconnect(self, wait: float) -> None:
        """Disconnect, waiting up to ``wait`` seconds for the manager.

        Args:
            wait: Seconds to wait for room to send ``DISCONNECT``, and then for
                the manager to close its end.
        """
        try:
            if self._connected:
                self._say_goodbye(wait)
        except Exception:
            pass
        finally:
            if hasattr(self, "_sock"):
                self._sock.close()
            self._connected = False
            self._reset_receive()
            # reset subscribed and paused types
            self._subscribed_types = set()
            self._paused_types = set()
            self._sub_all = False

    def _say_goodbye(self, wait: float) -> None:
        """Send ``DISCONNECT`` and wait for the manager to close its end.

        Closing a socket that still has unread bytes sends a reset, which can
        make the manager lose the ``DISCONNECT`` before reading it. So the
        sending side is shut down, and what arrives is read and discarded
        until the manager closes its end, which it does once it has handled
        the ``DISCONNECT``, or until ``wait`` runs out.

        Args:
            wait: The longest time to spend, in seconds.

        Raises:
            ConnectionLost: The connection failed.
        """
        deadline = time.perf_counter() + wait
        if not self.send_signal(cd.MT_DISCONNECT, timeout=wait):
            return
        self._sock.shutdown(socket.SHUT_WR)
        while True:
            remaining = deadline - time.perf_counter()
            if remaining <= 0:
                return
            readable, _, _ = select.select([self._sock], [], [], remaining)
            if not readable:
                return
            try:
                if not self._sock.recv(65536):
                    return
            except BlockingIOError:
                continue

    def _connection_lost(self) -> None:
        """Mark the client disconnected after its connection failed.

        This does what :py:func:`disconnect` does, except send ``DISCONNECT``:
        the socket is closed, and the partly received message and the local
        subscription state are cleared, as the manager has dropped them too.
        """
        self._connected = False
        self._sock.close()
        self._reset_receive()
        self._subscribed_types = set()
        self._paused_types = set()
        self._sub_all = False

    def _reset_receive(self) -> None:
        """Forget any partly received message, as for a new connection."""
        self._rx_header = None
        self._rx_payload = None
        self._rx_target = None
        self._rx_size = 0
        self._rx_have = 0

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
        # Read the iterable once: a generator is empty after a first pass.
        msg_set = set(msg_list)
        all_msg = ALL_MESSAGE_TYPES in msg_set
        if all_msg:
            msg_set = {ALL_MESSAGE_TYPES}

        # Note: Ignore any sub control for individual msg_types
        # when subscribed to ALL_MESSAGE_TYPES
        if self._sub_all and not all_msg:
            raise InvalidSubscription(
                "Cannot modify subscriptions to individual MTs while subscribed to ALL_MESSAGE_TYPES"
            )

        msg: MessageData
        if ctrl_msg == "Subscribe":
            msg = cd.MDF_SUBSCRIBE()
            if all_msg:
                self._subscribed_types = msg_set
                self._paused_types.clear()
                self._sub_all = True
            else:
                self._subscribed_types |= msg_set
                self._paused_types -= msg_set
        elif ctrl_msg == "Unsubscribe":
            msg = cd.MDF_UNSUBSCRIBE()
            if all_msg:
                self._subscribed_types.clear()
                self._paused_types.clear()
                self._sub_all = False
            else:
                self._subscribed_types -= msg_set
                self._paused_types -= msg_set
        elif ctrl_msg == "PauseSubscription":
            msg = cd.MDF_PAUSE_SUBSCRIPTION()
            if all_msg:
                # The manager drops every subscription. They are paused, not
                # forgotten: ALL_MESSAGE_TYPES itself, or the individual
                # types, so that resume_all_subscriptions() restores them.
                self._paused_types |= self._subscribed_types
                self._subscribed_types.clear()
                self._sub_all = False
            else:
                self._subscribed_types -= msg_set
                self._paused_types |= msg_set
        elif ctrl_msg == "ResumeSubscription":
            msg = cd.MDF_RESUME_SUBSCRIPTION()
            if all_msg:
                self._subscribed_types = msg_set
                self._paused_types.clear()
                self._sub_all = True
            else:
                self._subscribed_types |= msg_set
                self._paused_types -= msg_set
        else:
            raise TypeError("Unknown control message type.")

        for msg_type in msg_set:
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
        """Unsubscribe from all subscribed types, and forget paused ones

        Paused types have no subscription at the manager, so nothing is sent
        for them; they are no longer resumed by
        :py:func:`resume_all_subscriptions`.
        """
        self.unsubscribe(self.subscribed_types)
        self._paused_types.clear()

    @requires_connection
    def pause_all_subscriptions(self):
        """Pause all subscribed types"""
        self.pause_subscription(self.subscribed_types)

    @requires_connection
    def resume_all_subscriptions(self):
        """Resume all paused subscriptions"""
        self.resume_subscription(self.paused_subscribed_types)

    @contextmanager
    def subscription_context(self, msg_list: Iterable[int]) -> Iterator[None]:
        """Context manager to subscribe to a list of message types

        On exit, including when the body raises, the types this context
        subscribed to are unsubscribed again, unless the body has already
        unsubscribed or paused them. Types already subscribed to are left
        alone, with a warning. Subscribing to ``ALL_MESSAGE_TYPES`` replaces
        individual subscriptions at the manager, so on exit those, and any
        paused types, are restored. Nothing is restored if the client is no
        longer connected.

        Args:
            msg_list (Iterable[int]): A list of numeric message IDs to subscribe to
        """
        before = self.subscribed_types
        paused_before = self.paused_subscribed_types
        added: List[int] = []
        for mt in dict.fromkeys(msg_list):  # in order, once each
            if mt in before:
                warn(
                    f"Message ID {mt} is already subscribed, ignored from subscription_context"
                )
            else:
                added.append(mt)

        if added:
            self.subscribe(added)
        try:
            yield
        finally:
            if self.connected:
                if ALL_MESSAGE_TYPES in added and self._sub_all:
                    self.unsubscribe([ALL_MESSAGE_TYPES])
                    if before:
                        self.subscribe(before)
                    self._paused_types |= paused_before - before
                else:
                    still = [mt for mt in added if mt in self._subscribed_types]
                    if still:
                        self.unsubscribe(still)

    @contextmanager
    def paused_subscription_context(self, msg_list: Iterable[int]) -> Iterator[None]:
        """Context manager to pause subscriptions to a list of message types

        On exit, including when the body raises, the types this context
        paused are resumed, unless the body has already resumed or
        unsubscribed them. Types that aren't subscribed to are ignored, with a
        warning. Nothing is resumed if the client is no longer connected.

        Args:
            msg_list (Iterable[int]): A list of numeric message IDs to temporarily unsubscribe to
        """
        subscribed = self.subscribed_types
        paused: List[int] = []
        for mt in dict.fromkeys(msg_list):  # in order, once each
            if mt in subscribed:
                paused.append(mt)
            else:
                warn(
                    f"Message ID {mt} is not subscribed, ignored from paused_subscription_context"
                )

        if paused:
            self.pause_subscription(paused)
        try:
            yield
        finally:
            if self.connected:
                still = [mt for mt in paused if mt in self._paused_types]
                if still:
                    self.resume_subscription(still)

    @requires_connection
    def send_signal(
        self,
        signal_type: int,
        dest_mod_id: int = 0,
        dest_host_id: int = 0,
        timeout: float = -1,
    ) -> bool:
        """Send a signal

        A signal is a message type without an associated data payload.
        Only a unique message type ID is required to send a signal.
        To send a message with data, see :py:func:`send_message`.

        Args:
            signal_type: Numeric message type ID of signal
            dest_mod_id (optional): Specific module ID to send to, static or
                dynamic. Defaults to 0 (broadcast).
            dest_host_id (optional): Specific host ID to send to, or
                ``ALL_HOSTS``. Defaults to 0 (broadcast).
            timeout (optional): Timeout in seconds to wait for socket to be available for sending.
                Defaults to -1 (blocking). Once sending starts, the signal is
                sent whole.

        Raises:
            InvalidDestinationModule: Specified destination module is invalid
            InvalidDestinationHost: Specified destination host is invalid
            ConnectionLost: The connection failed. The client is disconnected.

        Returns:
            True if the signal was sent, False if the socket wasn't writable
            within the timeout and the signal was dropped.
        """
        _check_destination(dest_mod_id, dest_host_id)

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
            header.remaining_bytes = 0
            header.reserved = 0

            self._sendall(header, self._header_size)

            self._msg_count += 1
            return True

        # The socket wasn't writable in time: drop the message.
        _log.debug("Dropped message type %d: the socket wasn't writable.", signal_type)
        return False

    @requires_connection
    def send_message(
        self,
        msg_data: MessageData,
        dest_mod_id: int = 0,
        dest_host_id: int = 0,
        timeout: float = -1,
    ) -> bool:
        """Send a message

        A message is a packet that contains a defined data payload.
        To send a message without associated data, see :py:func:`send_signal`.

        Args:
            msg_data: Object containing the message to send
            dest_mod_id (optional): Specific module ID to send to, static or
                dynamic. Defaults to 0 (broadcast).
            dest_host_id (optional): Specific host ID to send to, or
                ``ALL_HOSTS``. Defaults to 0 (broadcast).
            timeout (optional): Timeout in seconds to wait for socket to be available for sending.
                Defaults to -1 (blocking). Once sending starts, the message is
                sent whole.

        Raises:
            InvalidDestinationModule: Specified destination module is invalid
            InvalidDestinationHost: Specified destination host is invalid
            ConnectionLost: The connection failed. The client is disconnected.

        Returns:
            True if the message was sent, False if the socket wasn't writable
            within the timeout and the message was dropped.
        """
        _check_destination(dest_mod_id, dest_host_id)

        if timeout >= 0:
            readfds, writefds, exceptfds = select.select([], [self._sock], [], timeout)
        else:
            readfds, writefds, exceptfds = select.select(
                [], [self._sock], []
            )  # blocking

        if writefds:
            with disable_message_validation():
                header = self._header_cls()
                header.msg_type = msg_data.type_id
                header.msg_count = self._msg_count
                header.send_time = time.perf_counter()
                header.recv_time = 0.0
                header.src_host_id = self._host_id
                header.src_mod_id = self._module_id
                header.dest_host_id = dest_host_id
                header.dest_mod_id = dest_mod_id
                num_data_bytes = ctypes.sizeof(msg_data)
                header.num_data_bytes = num_data_bytes
                header.remaining_bytes = 0
                header.reserved = 0

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

            self._sendall(header, self._header_size)
            if num_data_bytes > 0:
                self._sendall(msg_data, num_data_bytes)

            self._msg_count += 1
            return True

        # The socket wasn't writable in time: drop the message.
        _log.debug(
            "Dropped message type %d: the socket wasn't writable.", msg_data.type_id
        )
        return False

    @requires_connection
    def forward_message(
        self,
        msg_hdr: MessageHeader,
        msg_data: Optional[MessageData] = None,
        timeout: float = -1,
    ) -> bool:
        """Forward a message

        A message is a packet that contains a defined data payload.
        To send a message without associated data, see :py:func:`send_signal`.

        Args:
            msg_hdr: Object containing RTMA header to send
            msg_data: Object containing the message to send
            timeout (optional): Timeout in seconds to wait for socket to be available for sending.
                Defaults to -1 (blocking). Once sending starts, the message is
                sent whole.

        Raises:
            ConnectionLost: The connection failed. The client is disconnected.

        Returns:
            True if the message was sent, False if the socket wasn't writable
            within the timeout and the message was dropped.
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
            self._sendall(msg_hdr, ctypes.sizeof(msg_hdr))
            if msg_data is not None:
                self._sendall(msg_data, ctypes.sizeof(msg_data))

            self._msg_count += 1
            return True

        # The socket wasn't writable in time: drop the message.
        _log.debug(
            "Dropped message type %d: the socket wasn't writable.", msg_hdr.msg_type
        )
        return False

    def _sendall(
        self,
        buffer: Union[ctypes.Structure, bytes, bytearray],
        nbytes: Optional[int] = None,
    ):
        """Send a whole buffer, waiting for room in the socket as long as it takes.

        The socket is non-blocking, so ``socket.sendall`` would stop with
        ``BlockingIOError`` when the socket's buffer is full. Usually one
        ``send`` takes everything. Otherwise this waits in ``select`` until
        there is room and sends the rest, through a view, so nothing is
        copied.

        Args:
            buffer: The bytes to send, such as a header or a message's data.
            nbytes: The buffer's size in bytes, which callers know already.
                Found from the buffer when not given.

        Raises:
            ConnectionLost: The connection failed. The client is disconnected.
        """
        if nbytes is None:
            nbytes = memoryview(buffer).nbytes
        try:
            try:
                sent = self._sock.send(buffer)
            except BlockingIOError:
                sent = 0
            if sent < nbytes:
                rest = memoryview(buffer).cast("B")[sent:]
                while rest:
                    select.select([], [self._sock], [])
                    try:
                        sent = self._sock.send(rest)
                    except BlockingIOError:
                        continue
                    rest = rest[sent:]
        except OSError as e:
            self._connection_lost()
            raise ConnectionLost(
                f"Lost the connection to the message manager: {e}"
            ) from e

    @requires_connection
    def read_message(
        self, timeout: Union[int, float, None] = -1, ack=False, sync_check=False
    ) -> Optional[Message]:
        """Read a message

        Messages the client isn't subscribed to are discarded without being
        decoded, so they can't raise. The timeout is a deadline for the whole
        call, including any messages discarded on the way; a message that is
        only partly received when it passes is kept, and completed by a later
        call.

        Args:
            timeout (optional): Seconds to wait for a message. A negative value
                or None blocks until one arrives. 0 doesn't wait: it reads at
                most one message that has already arrived, and returns None if
                there is none or the client isn't subscribed to it. Defaults to
                -1 (blocking).
            ack (optional): Primarily for internal use. When True, will not discard ACK messages. Defaults to False.
            sync_check (optional): Validate message definition matches header version. Defaults to False.

        Raises:
            ConnectionLost: The connection to the message manager failed or
                was closed. The client is disconnected.
            UnknownMessageType: A message the client is subscribed to has no
                definition.
            InvalidMessageDefinition: A message the client is subscribed to
                doesn't match its definition.

        Returns:
            Message object. If no message is read before timeout, returns None.
        """
        deadline = self._deadline(timeout)
        while True:
            frame = self._recv_frame(deadline)
            if frame is None:
                return None

            msg_type, header, payload = frame
            if (
                self._sub_all
                or msg_type in self._subscribed_types
                or (ack and msg_type == cd.MT_ACKNOWLEDGE)
            ):
                return self._decode(header, payload, sync_check)

            # Not subscribed: a message queued before an unsubscribe, or an
            # ACK. A poll reads at most one message; otherwise keep reading
            # until the deadline.
            if timeout == 0:
                return None

    @requires_connection
    def _read_message(
        self, timeout: Union[int, float, None] = -1, ack=False, sync_check=False
    ) -> Optional[Message]:
        """Read one message without filtering for subscribed messages

        Args:
            timeout (optional): As for :py:func:`read_message`.
            ack (optional): Ignored; every message is returned.
            sync_check (optional): As for :py:func:`read_message`.

        Raises:
            ConnectionLost: As for :py:func:`read_message`.
            UnknownMessageType: The message has no definition.
            InvalidMessageDefinition: The message doesn't match its definition.

        Returns:
            The message, or None if none was complete before the timeout.
        """
        frame = self._recv_frame(self._deadline(timeout))
        if frame is None:
            return None
        _, header, payload = frame
        return self._decode(header, payload, sync_check)

    @staticmethod
    def _deadline(timeout: Union[int, float, None]) -> Optional[float]:
        """Turn a read timeout into a deadline on the ``perf_counter`` clock.

        Args:
            timeout: Seconds to wait; None or a negative value blocks.

        Returns:
            The deadline, or None to block.
        """
        if timeout is None or timeout < 0:
            return None
        return time.perf_counter() + timeout

    def _recv_frame(
        self, deadline: Optional[float]
    ) -> Optional[Tuple[int, MessageHeader, Union[MessageData, bytearray]]]:
        """Receive the rest of the current message, until it's complete or the deadline passes.

        The socket is non-blocking, so each ``recv`` returns at once with what
        has arrived, asking for no more than the rest of the current header
        or payload. Only when nothing has arrived does it wait, in ``select``,
        for the time left, so the deadline holds even when only part of a
        message has arrived. A message that has arrived in full costs two
        ``recv`` calls and no ``select``. Nothing past the current message is
        read, so a ``select`` on :py:attr:`sock` still shows whether a message
        is waiting.

        Bytes go straight into the objects returned, with no copies: the
        header into a header object, and the payload into an object of its
        message class, or into a bytearray when the type is unknown or its
        size doesn't match the definition.

        Args:
            deadline: A ``perf_counter`` time, or None to wait as long as it
                takes. A deadline that has passed reads only what has already
                arrived.

        Raises:
            ConnectionLost: The connection failed, was closed, or delivered a
                header with an impossible payload size. The client is
                disconnected.

        Returns:
            The completed message's type, header and payload, or None if the
            deadline passed first. An incomplete message is kept for the next
            call.
        """
        while True:
            target = self._rx_target
            if target is None:
                # A new message: start with its header.
                target = self._rx_header = self._rx_target = self._header_cls()
                self._rx_size = self._header_size
            have = self._rx_have
            size = self._rx_size
            try:
                try:
                    if have:
                        nbytes = self._sock.recv_into(
                            memoryview(target).cast("B")[have:], size - have
                        )
                    else:
                        nbytes = self._sock.recv_into(target, size)
                except BlockingIOError:
                    # Nothing more has arrived: wait for it, or the deadline.
                    wait = None
                    if deadline is not None:
                        wait = max(deadline - time.perf_counter(), 0)
                    readable, _, _ = select.select([self._sock], [], [], wait)
                    if not readable:
                        return None
                    continue
            except OSError as e:
                self._connection_lost()
                raise ConnectionLost(
                    f"Lost the connection to the message manager: {e}"
                ) from e

            if nbytes == 0:
                where = " mid-message" if have or target is not self._rx_header else ""
                self._connection_lost()
                raise ConnectionLost(
                    f"The message manager closed the connection{where}"
                )

            have += nbytes
            if have < size:
                # Only part has arrived; go round to read or wait for the rest.
                self._rx_have = have
                continue

            header = self._rx_header
            assert header is not None
            (msg_type,) = _INT32.unpack_from(header, _MSG_TYPE_OFFSET)
            if target is header:
                (data_size,) = _INT32.unpack_from(header, _NUM_DATA_BYTES_OFFSET)
                if data_size < 0 or data_size > _MAX_DATA_BYTES:
                    self._connection_lost()
                    raise ConnectionLost(
                        f"Received a header with num_data_bytes={data_size}, outside 0 to "
                        f"{_MAX_DATA_BYTES}; the connection can't be read further"
                    )
                self._rx_payload = self._payload_for(msg_type, data_size)
                if data_size:
                    # Go round again: the payload has usually arrived too.
                    self._rx_target = self._rx_payload
                    self._rx_size = data_size
                    self._rx_have = 0
                    continue

            payload = self._rx_payload
            assert payload is not None
            header.recv_time = time.perf_counter()
            self._reset_receive()
            return msg_type, header, payload

    def _payload_for(
        self, msg_type: int, data_size: int
    ) -> Union[MessageData, bytearray]:
        """Make the object a message's payload is received into.

        Args:
            msg_type: The message's type.
            data_size: The payload size its header announces.

        Returns:
            A new object of the type's message class, or a bytearray if the
            type has no definition or its size doesn't match the definition's.
            :py:func:`_decode` reports either error once the message is in.
        """
        try:
            msg_cls = self._definitions.get_msg_cls(msg_type)
        except UnknownMessageType:
            return bytearray(data_size)

        type_size = msg_cls.type_size
        if type_size == -1:  # not defined for v1 message defs
            type_size = ctypes.sizeof(msg_cls)
        if type_size != data_size:
            return bytearray(data_size)
        return msg_cls()

    def _decode(
        self,
        header: MessageHeader,
        payload: Union[MessageData, bytearray],
        sync_check: bool,
    ) -> Message:
        """Check a received message against the client's definitions.

        The message has already been read in full, so the next read starts at
        the next message whether or not this one is valid.

        Args:
            header: The message's header.
            payload: Its payload: an object of its message class, or a
                bytearray if :py:func:`_payload_for` couldn't make one.
            sync_check: Also check the header's version against the
                definition's hash.

        Raises:
            UnknownMessageType: The type has no definition.
            InvalidMessageDefinition: The size, or with ``sync_check`` the
                version, doesn't match the definition.

        Returns:
            The message.
        """
        data: MessageData
        if isinstance(payload, bytearray):
            # Find out why there was no message object.
            try:
                msg_cls = self._definitions.get_msg_cls(header.msg_type)
            except UnknownMessageType as e:
                raise UnknownMessageType(
                    f"No message definition found for MT={header.msg_type}",
                    header,
                    bytes(payload),
                ) from e

            type_size = msg_cls.type_size
            if type_size == -1:  # not defined for v1 message defs
                type_size = ctypes.sizeof(msg_cls)
            if type_size != header.num_data_bytes:
                raise InvalidMessageDefinition(
                    f"Received message header indicating a message data size ({header.num_data_bytes}) that does not match the expected size ({type_size}) of message type {msg_cls.type_name}. Message definitions may be out of sync across systems."
                )
            data = msg_cls.from_buffer_copy(payload)
        else:
            data = payload

        # Note: Ignore the sync check if header.version is not filled in
        # This can removed once all clients support this field.
        if sync_check and header.version != 0 and header.version != data.type_hash:
            raise InvalidMessageDefinition(
                f"Received message header indicating a message version that does not match the expected version of message type {data.type_name}. Message definitions may be out of sync across systems."
            )

        return Message(header, data)

    def _wait_for_acknowledgement(self, timeout: Optional[float] = 3) -> Message:
        """Wait for acknowledgement from message manager module

        Used internally when acknowledgement replies from message manager are expected

        Only an ACK for this client counts: for a static ID, one addressed
        to that ID, or to 0. A logger is sent copies of other modules' ACKs,
        which are skipped. A client asking for a dynamic ID can't tell its
        own ACK by address, and takes the first; the manager sends it first
        on a new connection. Other messages are discarded.

        Args:
            timeout (optional): Timeout in seconds to wait for ack message.
                None or a negative value waits as long as it takes. Defaults
                to 3.

        Raises:
            AcknowledgementTimeout: Ack not received from message manager
            ConnectionLost: The connection failed. The client is disconnected.

        Returns:
            Ack message
        """
        deadline = self._deadline(timeout)
        while True:
            frame = self._recv_frame(deadline)
            if frame is None:
                raise AcknowledgementTimeout(
                    "Failed to receive Acknowlegement from MessageManager"
                )
            msg_type, header, payload = frame
            if msg_type == cd.MT_ACKNOWLEDGE and (
                self._module_id == 0 or header.dest_mod_id in (0, self._module_id)
            ):
                return self._decode(header, payload, False)

    @requires_connection
    def discard_messages(self, timeout: float = 1) -> bool:
        """Read and discard the messages that have already arrived

        Messages are discarded without being decoded, so neither subscriptions
        nor unknown types stop it early. Messages still on their way from the
        manager aren't waited for.

        Args:
            timeout (optional): Maximum time in seconds to spend discarding.
                Defaults to 1.

        Raises:
            ConnectionLost: The connection to the message manager failed or
                was closed. The client is disconnected.

        Returns:
            True if no complete message is left waiting, False if the timeout
            ended the loop first. Part of a message counts as nothing waiting.
        """
        deadline = time.perf_counter() + timeout
        while True:
            if self._recv_frame(_NO_WAIT) is None:
                return True
            if time.perf_counter() >= deadline:
                readable, _, _ = select.select([self._sock], [], [], 0)
                return not readable

    def reset_subscriptions(self, subscribe_list: Optional[Iterable[int]] = None):
        """Unsubscribe from all messages and empty the message buffer.
        If optional 'subscribe_list' argument given, then will subscribe to new messages after reset.

        Args:
            subscribe_list (Optional[Iterable[int]], optional): List of message IDs to subscribe to. Defaults to None.
        """
        self.unsubscribe_from_all()
        self.discard_messages()
        if subscribe_list:
            self.subscribe(subscribe_list)

    def __str__(self) -> str:
        # TODO: Make this better.
        return f"Client(module_id={self.module_id}, server={self.server}, connected={self.connected})"


@contextmanager
def client_context(
    module_id: int = 0,
    server_name: str = "localhost:7111",
    msg_list: Optional[Iterable[int]] = None,
    host_id: int = 0,
    *,
    logger_status: bool = False,
    name: str = "",
    definitions: Optional[MessageDefinitions | ModuleType] = None,
    auto_detect: bool = True,
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
        logger_status (optional): Flag to declare client as a logger module.
            This and the arguments after it are keyword-only. A logger isn't
            subscribed to anything automatically; see :py:func:`Client.connect`.
            Defaults to False.
        name (optional): Name of module
        definitions (optional): MessageDefinitions object or Module containing MessageDefinitions. Defaults to None, which will auto-detect
            message definitions from the current module or use core_defs if not found.
        auto_detect (optional): If True, will attempt to auto-detect message definitions
            from the current module. If False, will use core_defs. Defaults to True.

    Yields:
        Client: initialized pyrtma Client object
    """
    c = Client(
        module_id,
        host_id,
        name=name,
        definitions=definitions,
        auto_detect=auto_detect,
    )
    try:
        c.connect(server_name, logger_status)
        if msg_list:
            c.subscribe(msg_list)
        c.send_module_ready()
        yield c
    finally:
        c.disconnect()
