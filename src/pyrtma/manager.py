"""pyrtma.manager module

Contains :py:class:`~MessageManager` class
"""

import socket
import select
import argparse
import logging
import time
import random
import ctypes
import os
import sys


from .client_logging import RTMALogger, ClientLike
from .validators import disable_message_validation
from .message import Message
from .header import MessageHeader, _field_struct, get_header_cls
from .message_data import MessageData
from .core_defs import ALL_MESSAGE_TYPES
from . import core_defs as cd

from typing import Any, Deque, Dict, List, Tuple, Set, Type, Union, Optional
from typing import Sequence
from dataclasses import dataclass, field
from collections import defaultdict, deque

# Message types below this are core types, defined in core_defs. The manager
# checks their size and acts on some of them; it forwards other types as is.
_FIRST_USER_MSG_TYPE: int = cd.MAX_RTMA_MSG_TYPE + 1

#: Seconds a client may stall partway through sending a message before the
#: manager drops it.
DEFAULT_STALL_TIMEOUT: float = 5.0

# The header's num_data_bytes field, read straight from the received bytes:
# the read loop needs it for every message before there is a header object.
_NUM_DATA_BYTES, _NUM_DATA_BYTES_OFFSET = _field_struct(
    MessageHeader, "_num_data_bytes"
)

# What select() can watch. On Linux and macOS it can't take a descriptor
# numbered FD_SETSIZE (1024) or higher; on Windows it takes at most 512
# sockets per list. Past either limit it raises ValueError, which would stop
# the manager, so connections beyond them are refused instead.
_SELECT_MAX_SOCKETS: Optional[int]
_SELECT_MAX_FD: Optional[int]
if sys.platform == "win32":
    _SELECT_MAX_SOCKETS = 512
    _SELECT_MAX_FD = None
else:
    _SELECT_MAX_SOCKETS = None
    _SELECT_MAX_FD = 1024


@dataclass
class Module:
    """Module dataclass

    Used internally by MessageManager to manage connections to each client module.
    """

    conn: socket.socket
    address: Tuple[str, int]
    header_cls: Type[MessageHeader]
    name: str = ""
    mod_id: int = 0
    pid: int = 0
    subs: Set[int] = field(default_factory=set)
    connected: bool = False
    is_logger: bool = False
    is_daemon: bool = False
    drops: int = 0
    msg_count: int = 0

    # Receive state. The manager reads a message a piece at a time, as its
    # bytes arrive, into _rx: first the header, then the payload after it.
    # _rx_have counts the bytes received, _rx_need the bytes the current
    # section ends at, and _rx_last is when the last bytes arrived.
    _rx: bytearray = field(init=False, repr=False, compare=False)
    _rx_view: memoryview = field(init=False, repr=False, compare=False)
    _rx_have: int = field(default=0, init=False, repr=False, compare=False)
    _rx_need: int = field(init=False, repr=False, compare=False)
    _rx_header_size: int = field(init=False, repr=False, compare=False)
    _rx_header_done: bool = field(default=False, init=False, repr=False, compare=False)
    _rx_last: float = field(default=0.0, init=False, repr=False, compare=False)

    # Send state: bytes the kernel hasn't accepted yet, oldest first. The
    # first entry may be the rest of a message that was partly sent.
    _outbox: Deque[memoryview] = field(
        default_factory=deque, init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        self._rx_header_size = ctypes.sizeof(self.header_cls)
        self._rx = bytearray(self._rx_header_size)
        self._rx_view = memoryview(self._rx)
        self._rx_need = self._rx_header_size

    @property
    def ipaddr(self) -> str:
        return f"{self.address[0]}:{self.address[1]}"

    @property
    def addr(self) -> str:
        return self.address[0]

    @property
    def port(self) -> int:
        return self.address[1]

    @property
    def sub_all(self) -> bool:
        return ALL_MESSAGE_TYPES in self.subs

    @property
    def has_pending(self) -> bool:
        """Whether bytes are waiting to be sent to this module."""
        return bool(self._outbox)

    def send_message(
        self, header: MessageHeader, payload: Union[bytes, memoryview, MessageData]
    ):
        """Send a message, queueing what the connection can't take yet.

        The message is never dropped: bytes the kernel doesn't accept now are
        kept and sent by :meth:`flush`, after anything already queued. The
        header is sent unchanged, so the recipient sees the sender's
        ``msg_count``. ``Module.msg_count`` counts the messages sent to this
        module, for tracking only; it is not written into the header, which the
        manager shares between all recipients of a message.

        Args:
            header (MessageHeader): Message header
            payload (Union[bytes, memoryview, MessageData]): Message data

        Raises:
            OSError: The connection failed.
        """
        self.enqueue(b"".join((header, payload)))

    def send_ack(self):
        """Send ACKNOWLEDGE signal header, queueing it if needed.

        Raises:
            OSError: The connection failed.
        """
        # Just send a header
        header = self.header_cls()
        header.msg_type = cd.MT_ACKNOWLEDGE
        header.send_time = time.perf_counter()
        header.src_mod_id = cd.MID_MESSAGE_MANAGER
        header.dest_mod_id = self.mod_id
        header.num_data_bytes = 0
        header.msg_count = 0  # messages from the manager carry no count

        self.enqueue(bytes(header))

    def try_send(self, data: bytes) -> bool:
        """Start sending a whole message now, or not at all.

        Used for forwarded messages, which are dropped rather than delayed
        when a module can't take them. Queued bytes go first; if they can't
        all be sent, nothing new is started. Once the kernel accepts any of
        the message, the rest is queued, so a message is never cut short on
        the wire.

        Args:
            data: The message's header and payload, in one buffer.

        Returns:
            True if the message was sent or queued; False if none of it was,
            because the connection is full or still has queued bytes.

        Raises:
            OSError: The connection failed.
        """
        if self._outbox and not self.flush():
            return False
        try:
            sent = self.conn.send(data)
        except BlockingIOError:
            return False
        self.msg_count += 1
        if sent < len(data):
            self._outbox.append(memoryview(data)[sent:])
        return True

    def enqueue(self, data: bytes) -> None:
        """Send a message, queueing whatever the connection can't take yet.

        Args:
            data: The message's header and payload, in one buffer.

        Raises:
            OSError: The connection failed.
        """
        self.msg_count += 1
        if self._outbox and not self.flush():
            self._outbox.append(memoryview(data))
            return
        try:
            sent = self.conn.send(data)
        except BlockingIOError:
            sent = 0
        if sent < len(data):
            self._outbox.append(memoryview(data)[sent:])

    def flush(self) -> bool:
        """Send queued bytes until they're gone or the connection is full.

        Returns:
            True if nothing is left queued.

        Raises:
            OSError: The connection failed.
        """
        while self._outbox:
            chunk = self._outbox[0]
            try:
                sent = self.conn.send(chunk)
            except BlockingIOError:
                return False
            if sent < len(chunk):
                self._outbox[0] = chunk[sent:]
                return False
            self._outbox.popleft()
        return True

    def _rx_reserve(self, size: int) -> None:
        """Make the receive buffer hold at least ``size`` bytes.

        Bytes already received are kept. The buffer is replaced rather than
        resized, because a bytearray with a memoryview on it can't be resized.

        Args:
            size: The number of bytes needed.
        """
        if len(self._rx) >= size:
            return
        grown = bytearray(size)
        grown[: self._rx_have] = self._rx_view[: self._rx_have]
        self._rx_view.release()
        self._rx = grown
        self._rx_view = memoryview(grown)

    def _rx_reset(self) -> None:
        """Get ready to receive the next message's header."""
        self._rx_have = 0
        self._rx_need = self._rx_header_size
        self._rx_header_done = False

    def close(self):
        """Close connection"""
        self.conn.close()
        self.connected = False

    def __str__(self):
        return f"{self.name or 'ID'}({self.mod_id}) @ {self.ipaddr}"

    def __hash__(self):
        return self.conn.__hash__()


class _Routing:
    """The context ``MessageManager._routing()`` returns.

    One per manager, entered again for each forward, so a forward costs no
    new object. A forward that raises still ends, but doesn't finish
    removals, as a generator-based context manager wouldn't either.

    Args:
        manager: The manager whose forwards it marks.
    """

    __slots__ = ("_manager",)

    def __init__(self, manager: "MessageManager") -> None:
        self._manager = manager

    def __enter__(self) -> None:
        self._manager._forward_depth += 1

    def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        manager = self._manager
        manager._forward_depth -= 1
        if exc_type is None:
            manager._finish_removals()


class MessageManager(ClientLike):
    """MessageManager class

    RTMA Message Manager server implemented in python.
    """

    INFO_INTERVAL = 5.0

    def __init__(
        self,
        ip_address: str = "",  # "" equivalent to socket.INADDR_ANY
        port: int = 7111,
        *,
        log_level=logging.INFO,
        debug=False,
        stall_timeout: Optional[float] = DEFAULT_STALL_TIMEOUT,
        logger_timeout: Optional[float] = None,
    ):
        """MessageManager class

        RTMA Message Manager server implemented in python.

        Args:
            ip_address (str, optional): server IP address. Defaults to "".
            port (int, optional): server port. Defaults to 7111. The arguments
                after it are keyword-only.
            log_level (int, optional): logging level, defaults to logging.INFO.
            debug (bool, optional): Flag for debug mode. Defaults to False.
            stall_timeout: Seconds a client may go without sending more bytes
                while partway through a message before it is dropped, or None
                to never drop it. A stalled client doesn't hold up the others
                either way. Defaults to 5 seconds.
            logger_timeout: Seconds to wait for a logger module that can't take
                a message, before dropping it, or None to wait as long as it
                takes. Other modules are never waited for. Defaults to None.

        Raises:
            ValueError: A timeout is zero or negative.
            RuntimeError: The listening socket's descriptor is beyond what
                ``select()`` can watch, because the process has too many
                files open.
        """
        for name, value in (
            ("stall_timeout", stall_timeout),
            ("logger_timeout", logger_timeout),
        ):
            if value is not None and value <= 0:
                raise ValueError(f"{name} must be positive or None, not {value}.")
        self.stall_timeout = stall_timeout
        self.logger_timeout = logger_timeout

        self._keep_running = False
        self.ip_address = ip_address
        self.port = port

        self.header_cls = get_header_cls()
        self.header_size = ctypes.sizeof(self.header_cls)
        self.header_buffer = bytearray(self.header_size)
        self.header_view = memoryview(self.header_buffer)

        # How long run() waits in select(). It also bounds how late the stall
        # check can run.
        self.read_timeout = 0.200
        # Unused since sends became non-blocking; kept for compatibility.
        self.write_timeout = 0
        self._debug = debug

        self._logger = RTMALogger(f"message_manager", self, logging.INFO)
        self.logger.set_all_levels(log_level)

        if ip_address == socket.INADDR_ANY:
            ip_address = ""  # bind and Module require a string input, '' is treated as INADDR_ANY by bind

        # Connected modules allowed at once, not counting the manager itself.
        self._max_modules: int = cd.MAX_MODULES

        # Connections beyond these are refused; see _SELECT_MAX_SOCKETS.
        self._max_sockets: Optional[int] = _SELECT_MAX_SOCKETS
        self._max_fd: Optional[int] = _SELECT_MAX_FD

        # Create the tcp listening socket
        self.listen_socket = socket.socket(
            family=socket.AF_INET, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
        )
        listen_fd = self.listen_socket.fileno()
        if self._max_fd is not None and listen_fd >= self._max_fd:
            self.listen_socket.close()
            raise RuntimeError(
                f"The listening socket's descriptor ({listen_fd}) is beyond what select() can watch (below {self._max_fd}). Start the manager with fewer files open."
            )
        self.listen_socket.bind((ip_address, port))
        self.listen_socket.listen(socket.SOMAXCONN)
        self.modules: Dict[socket.socket, Module] = {}
        self.logger_modules: Set[Module] = set()

        self.subscriptions: Dict[int, Set[Module]] = defaultdict(set)
        self.sockets = [self.listen_socket]
        self.start_time = time.time()

        # Disable Nagle Algorithm
        self.listen_socket.setsockopt(
            socket.getprotobyname("tcp"), socket.TCP_NODELAY, 1
        )

        # Unused since sends became non-blocking; kept for compatibility.
        self.wlist: List[socket.socket] = []

        # Add message manager to its module list
        self.mm_module = Module(
            conn=self.listen_socket,
            address=(ip_address, port),
            header_cls=self.header_cls,
            name="message_manager",
            mod_id=0,
            pid=os.getpid(),
            connected=True,
            is_logger=False,
        )

        self.modules[self.listen_socket] = self.mm_module

        self.data_buffer = bytearray(1024**2)
        self.data_view = memoryview(self.data_buffer)

        self._core_defs = cd.get_message_definitions().msg_defs

        # Removal bookkeeping. A removed module leaves the routing tables at
        # once, but its socket is closed and its GOODBYE sent only when no
        # forward is in progress, so a loop over subscribers never meets a
        # closed socket. See remove_module() and _routing().
        self._forward_depth = 0
        self._router = _Routing(self)
        self._closing: List[Module] = []
        self._finishing_removals = False

        # Address Reuse allowed for testing
        if debug:
            self.listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.logger.info("Message Manager Initialized.")

    @property
    def connected(self) -> bool:
        return True

    @property
    def logger(self) -> RTMALogger:
        return self._logger

    def assign_module_id(self) -> int:
        """Assign module ID dynamically to connecting module

        Raises:
            RuntimeError: Exceeded maximum number of allowed dynamic modules

        Returns:
            int: module ID
        """
        current_ids = [mod.mod_id for mod in self.modules.values()]

        for mod_id in range(cd.DYN_MOD_ID_START, cd.MAX_MODULE_ID):
            # check if mod id is already used, if it is, continue looping until we find an unused one
            if mod_id not in current_ids:
                return mod_id

        # if we exit loop without returning, we failed to find a valid id
        self.logger.error(
            f"MessageManager::assign_module_id: All valid dynamic IDs are in use"
        )

        raise RuntimeError("Exceeded maximum limit of allowed modules.")

    def decode_header(self) -> MessageHeader:
        return self.header_cls.from_buffer(self.header_view)

    def connect_module(self, module: Module, msg: Message) -> bool:
        """Connect module

        A module is refused and its connection closed when ``MAX_MODULES``
        modules are already connected, or when it asks for an ID that is out
        of range or already in use. It keeps no ID, and it gets no
        GOODBYE, since it was never introduced with a HELLO.

        Args:
            module (Module): Connecting module
            msg (Message): Incoming connect message

        Returns:
            bool: success code
        """
        # ignore v1 message that follows v2 message
        if module.connected:
            return False

        if isinstance(msg.data, cd.MDF_CONNECT_V2):
            requested = msg.data.mod_id
            module.pid = msg.data.pid
            module.name = msg.data.name
        elif isinstance(msg.data, cd.MDF_CONNECT):
            requested = msg.header.src_mod_id
        else:
            raise RuntimeError(
                f"MessageManager::connect_module: Uknown Connect message definition"
            )

        # fields common to v1 and v2
        module.is_logger = msg.data.logger_status == 1

        connected = sum(
            1 for m in self.modules.values() if m.connected and m is not self.mm_module
        )
        if connected >= self._max_modules:
            self.logger.error(
                f"DROPPING - {module!s} - The limit of {self._max_modules} modules (MAX_MODULES) is reached. Closing connection."
            )
            self.remove_module(module)
            return False

        # The ID is checked before it is given to the module, so that a
        # refused module never carries another module's ID.
        if requested == 0:
            requested = self.assign_module_id()
        else:
            # DYN_MOD_ID_START is the first dynamic ID, so it can't be static.
            if requested < 1 or requested >= cd.DYN_MOD_ID_START:
                self.logger.error(
                    f"Invalid Module id specified: {requested}. User assigned ids must be in range 1 - {cd.DYN_MOD_ID_START - 1}"
                )
                self.remove_module(module)
                return False

            if any(
                m.mod_id == requested for m in self.modules.values() if m is not module
            ):
                self.logger.error(
                    f"SET_ID - {module.ipaddr} - ID({requested}) - ID already in use. Closing connection."
                )
                self.remove_module(module)
                return False

        module.mod_id = requested
        module.connected = True

        if module.is_logger:
            self.logger_modules.add(module)

        return True

    def update_connection(self, module: Module, msg: Message) -> None:
        """Take the details of a connect message from a connected module.

        Clients used to send both CONNECT and CONNECT_V2, in either order, for
        managers that didn't support CONNECT_V2. The first one connects the
        module and is acknowledged. A CONNECT_V2 after that updates the
        module's name and process ID, and a HELLO announces them; no ACK is
        sent, because the client waits for only one. Its module ID and logger
        status can't change while the module is connected, so a different
        request is logged and ignored. A CONNECT after either carries nothing
        new and is ignored.

        Args:
            module: The connected module.
            msg: Its CONNECT or CONNECT_V2 message.
        """
        if not isinstance(msg.data, cd.MDF_CONNECT_V2):
            return

        data = msg.data
        if data.mod_id not in (0, module.mod_id):
            self.logger.warning(
                f"CONNECT v2 - {module!s} - Already connected; ignoring the requested ID({data.mod_id})."
            )
        if (data.logger_status == 1) != module.is_logger:
            self.logger.warning(
                f"CONNECT v2 - {module!s} - Already connected; ignoring the change of logger status to {data.logger_status}."
            )
        module.name = data.name
        module.pid = data.pid
        self.logger.info(f"CONNECT v2 update - {module!s}")
        self.send_hello(module)

    def remove_module(self, module: Module):
        """Remove connected module

        The module leaves the routing tables at once, so no later message is
        sent to it. Its socket is closed and its GOODBYE sent straight away,
        or, when this is called while a message is being forwarded, as soon as
        the outermost forward finishes. Removing a module that was already
        removed does nothing.

        Args:
            module (Module): Module object to remove
        """
        if not self._is_routed(module):
            return

        # Drop all subscriptions for this module
        for msg_type in module.subs:
            self._unsubscribe(module, msg_type)

        # Discard from logger module set if needed
        self.logger_modules.discard(module)

        # Drop from our module mapping and socket list
        del self.modules[module.conn]
        if module.conn in self.sockets:
            self.sockets.remove(module.conn)

        self._closing.append(module)
        self._finish_removals()

    def _is_routed(self, module: Module) -> bool:
        """Report whether a module is still registered with the manager.

        Args:
            module: The module to check.

        Returns:
            True until the module is removed.
        """
        return self.modules.get(module.conn) is module

    def _finish_removals(self) -> None:
        """Close removed modules' sockets and send their GOODBYEs.

        Only a module that connected gets a GOODBYE, so each GOODBYE matches an
        earlier HELLO; a socket that never connected is just closed.

        Does nothing while a message is being forwarded, or while this is
        already running further up the stack. Sending a GOODBYE can remove
        more modules; they join the queue and are finished by the same loop,
        rather than by recursion.
        """
        if self._forward_depth or self._finishing_removals:
            return
        self._finishing_removals = True
        try:
            while self._closing:
                module = self._closing.pop(0)
                # Read before close(), which clears it.
                introduced = module.connected
                module.close()
                if introduced:
                    self.send_goodbye(module)
        finally:
            self._finishing_removals = False

    def _routing(self) -> _Routing:
        """Mark a forward in progress, and finish removals when it ends.

        Forwards nest: a send failure logs an error and sends FAILED_MESSAGE,
        and both are forwarded too. Removals wait until the outermost one ends.
        Use it as ``with self._routing():`` around the sends.

        Returns:
            The manager's one routing context, which can be entered again
            while it's in use.
        """
        return self._router

    def _drop_after_send_error(
        self, module: Module, header: Optional[MessageHeader], err: OSError
    ) -> None:
        """Remove a module whose send failed, and report the failure.

        Args:
            module: The module the send was for.
            header: Header of the message that wasn't delivered, or None when
                the failure was in sending queued bytes, which aren't
                reported with ``FAILED_MESSAGE``.
            err: The error the send raised.
        """
        self.remove_module(module)
        self.logger.error(f"Connection Error on write to {module!s} - {err!s}")
        print("x", end="", flush=True)
        if header is not None:
            # This could recurse: send_failed_message returns early when the
            # failed message is itself a FAILED_MESSAGE or a log message.
            self.send_failed_message(module, header, time.perf_counter())

    def _wait_writable(self, module: Module, timeout: Optional[float]) -> bool:
        """Wait until a module's connection can take more bytes.

        Args:
            module: The module to wait for.
            timeout: Seconds to wait, or None to wait as long as it takes.

        Returns:
            True if the connection is writable, False if the wait timed out.
        """
        _, writable, _ = select.select([], [module.conn], [], timeout)
        return bool(writable)

    def _drain_logger(self, module: Module) -> bool:
        """Wait until a logger module has taken every queued byte.

        Loggers are waited for, so that recordings are complete. The wait is
        bounded by ``logger_timeout`` when it is set.

        Args:
            module: The logger module.

        Returns:
            True when everything was sent; False if ``logger_timeout`` passed
            first.

        Raises:
            OSError: The connection failed.
        """
        deadline = (
            None
            if self.logger_timeout is None
            else time.monotonic() + self.logger_timeout
        )
        while not module.flush():
            remaining = None if deadline is None else deadline - time.monotonic()
            if remaining is not None and remaining <= 0:
                return False
            if not self._wait_writable(module, remaining):
                return False
        return True

    def _send_to_logger(
        self, module: Module, header: MessageHeader, wire: bytes
    ) -> None:
        """Send a message to a logger module, waiting for it if needed.

        Args:
            module: The logger module.
            header: The message's header, for reporting a failure.
            wire: The message's header and payload, in one buffer.
        """
        try:
            module.enqueue(wire)
            drained = self._drain_logger(module)
        except OSError as err:
            self._drop_after_send_error(module, header, err)
            return
        if drained:
            module.drops = 0
            return
        # Removed before logging: the log message is forwarded to loggers too,
        # and would otherwise wait for this one again. Its GOODBYE still comes
        # after the log record, when the forward finishes.
        self.remove_module(module)
        self.logger.error(
            f"DROPPING - {module!s} - Logger module did not accept data within {self.logger_timeout} s."
        )
        self.send_failed_message(module, header, time.perf_counter())

    def _flush_module(self, module: Module) -> None:
        """Send a module's queued bytes, as far as its connection takes them.

        A failure drops the module, and doesn't stop the manager.

        Args:
            module: The module, whose connection is writable.
        """
        try:
            module.flush()
        except OSError as err:
            self._drop_after_send_error(module, None, err)
        except Exception:
            self.logger.exception(
                f"DROPPING - {module!s} - Unexpected error while sending to it."
            )
            self.remove_module(module)

    def disconnect_module(self, src_module: Module):
        """Disconnect module

        Args:
            src_module (Module): Module object to disconnect
        """
        self.remove_module(src_module)

    def _unsubscribe(self, module: Module, msg_type: int) -> None:
        """Take a module off one type's subscriber set.

        A set left empty is deleted, so the table holds only types that have
        subscribers.

        Args:
            module: The module.
            msg_type: The message type.
        """
        subscribers = self.subscriptions.get(msg_type)
        if subscribers is None:
            return
        subscribers.discard(module)
        if not subscribers:
            del self.subscriptions[msg_type]

    def add_subscription(self, src_module: Module, msg: Message):
        """Add message subscription

        Args:
            src_module (Module): Subscribing module
            msg (Message): incoming SUBSCRIBE message
        """
        sub = cd.MDF_SUBSCRIBE.from_buffer(msg.data)

        if sub.msg_type == ALL_MESSAGE_TYPES:
            self.subscriptions[sub.msg_type].add(src_module)

            # Clear out the individual subs
            for sub_type in src_module.subs:
                if sub_type != ALL_MESSAGE_TYPES:
                    self._unsubscribe(src_module, sub_type)
            src_module.subs.clear()

            src_module.subs.add(sub.msg_type)
            self.logger.debug(f"SUBSCRIBE- {src_module!s} to ALL_MESSAGE_TYPES")
        else:
            # Ignore individual msg_types subs when subscribed to ALL_MESSAGE_TYPES
            if src_module.sub_all:
                return
            self.subscriptions[sub.msg_type].add(src_module)
            src_module.subs.add(sub.msg_type)
            self.logger.debug(f"SUBSCRIBE- {src_module!s} to MT:{sub.msg_type}")

    def remove_subscription(self, src_module: Module, msg: Message):
        """Remove message subscription

        Args:
            src_module (Module): Unsubscribing module
            msg (Message): incoming UNSUBSCRIBE message
        """
        unsub = cd.MDF_UNSUBSCRIBE.from_buffer(msg.data)

        if unsub.msg_type == ALL_MESSAGE_TYPES:
            self._unsubscribe(src_module, unsub.msg_type)

            # Clear out the individual subs
            for sub_type in src_module.subs:
                self._unsubscribe(src_module, sub_type)
            src_module.subs.clear()

            self.logger.debug(f"UNSUBSCRIBE- {src_module!s} from ALL_MESSAGE_TYPES")
        else:
            # Ignore individual msg_types unsubs when subscribed to ALL_MESSAGE_TYPES
            if src_module.sub_all:
                return
            self._unsubscribe(src_module, unsub.msg_type)
            src_module.subs.discard(unsub.msg_type)
            self.logger.debug(f"UNSUBSCRIBE- {src_module!s} from MT:{unsub.msg_type}")

    def resume_subscription(self, src_module: Module, msg: Message):
        """Resume message subscription

        Args:
            src_module (Module): Subscribing module
            msg (Message): incoming RESUME_SUBSCRIPTION message
        """
        self.add_subscription(src_module, msg)

    def pause_subscription(self, src_module: Module, msg: Message):
        """Pause message subscription

        Args:
            src_module (Module): Subscribing module
            msg (Message): incoming PAUSE_SUBSCRIPTION message
        """
        self.remove_subscription(src_module, msg)

    def register_module_ready(self, src_module: Module, msg: Message):
        """Handle MODULE_READY message and register PID

        Args:
            src_module (Module): Module that is ready
            msg (Message): Incoming MODULE_READY message
        """
        mr = cd.MDF_MODULE_READY.from_buffer(msg.data)
        src_module.pid = mr.pid

    def set_module_name(self, src_module: Module, msg: Message):
        """Set a module name

        Args:
            src_module (Module): Module that sent CLIENT_SET_NAME
            msg (Message): Incoming CLIENT_SET_NAME message
        """
        name_msg = cd.MDF_CLIENT_SET_NAME.from_buffer(msg.data)
        src_module.name = name_msg.name or ""
        self.logger.info(
            f"SET_NAME - {src_module.ipaddr} - ID({src_module.mod_id}) - {src_module.name}"
        )

    def read_message(self, sock: socket.socket) -> Optional[MessageHeader]:
        """Read whatever has arrived of a client's message, without blocking.

        Each client's bytes go into its own buffer, a section at a time: a
        read never asks for more than the rest of the current header or
        payload, so the next message's bytes stay in the kernel's buffer. A
        message that is still incomplete waits there while other clients are
        served, and is picked up when more bytes arrive.

        A client is dropped if its header announces a negative or oversized
        payload, which is checked once the header is complete; if it sends a
        core message whose size doesn't match its core definition, checked
        once the whole message is in; or if it closes its connection.

        Args:
            sock (socket.socket): socket to read from

        Returns:
            MessageHeader: header of the message this read completed, with its
            payload in ``data_buffer``, or None if no message was completed or
            the client was dropped

        Raises:
            ConnectionError: The connection was reset.
        """
        mod = self.modules[sock]
        header_size = self.header_size
        while True:
            have = mod._rx_have
            need = mod._rx_need
            try:
                nbytes = sock.recv_into(mod._rx_view[have:need], need - have)
            except BlockingIOError:
                # Nothing to read after all: readiness is only a hint.
                return None

            if nbytes == 0:
                self._drop_closed(mod)
                return None

            have += nbytes
            mod._rx_have = have
            mod._rx_last = time.monotonic()
            if have < need:
                # The rest hasn't arrived; wait for select() to report more.
                return None

            if mod._rx_header_done:
                break

            (data_size,) = _NUM_DATA_BYTES.unpack_from(mod._rx, _NUM_DATA_BYTES_OFFSET)
            if data_size < 0 or data_size > len(self.data_buffer):
                msg_type = self.header_cls.from_buffer_copy(
                    mod._rx_view[:header_size]
                ).msg_type
                self.logger.error(
                    f"DROPPING - {mod!s} - Invalid num_data_bytes ({data_size}) for MT={msg_type}; it must be 0 to {len(self.data_buffer)}. Header may be corrupted."
                )
                self.remove_module(mod)
                return None
            mod._rx_header_done = True
            if not data_size:
                break
            mod._rx_reserve(header_size + data_size)
            mod._rx_need = header_size + data_size
            # Go round again: the payload has often arrived too.

        # The whole message is in. Copy it to the shared buffers that the
        # processing code reads, and get ready for the next one.
        size = mod._rx_need
        self.header_view[:] = mod._rx_view[:header_size]
        if size > header_size:
            self.data_view[: size - header_size] = mod._rx_view[header_size:size]
        mod._rx_reset()
        header = self.decode_header()

        # Checked after the payload is read, so that a dropped client's socket
        # closes with nothing left unread, which ends the connection cleanly
        # rather than with a reset.
        if not self._core_size_matches(mod, header):
            return None

        return header

    def _drop_quietly(self, module: Module, message: str) -> None:
        """Drop a module and log why, without sending it the log message.

        The module is removed first, so the log message isn't forwarded to
        it: a closed connection would fail the send, and a stalled logger
        could be waited for. Removing it inside ``_routing()`` defers its
        GOODBYE until the log message has gone out.

        Args:
            module: The module to drop.
            message: The warning to log.
        """
        with self._routing():
            self.remove_module(module)
            self.logger.warning(message)

    def _drop_closed(self, mod: Module) -> None:
        """Drop a client whose connection was closed.

        Args:
            mod: The client's module.
        """
        if mod._rx_have:
            reason = f"Connection closed mid-message, after {mod._rx_have} of {mod._rx_need} bytes."
        else:
            reason = "Connection closed by the client."
        self._drop_quietly(mod, f"DROPPING - {mod!s} - {reason}")

    def _drop_stalled(self, now: float) -> None:
        """Drop clients that stalled partway through sending a message.

        A client is stalled when it has sent part of a message and nothing
        more for ``stall_timeout`` seconds. Does nothing when ``stall_timeout``
        is None.

        Args:
            now: The current ``time.monotonic()`` reading.
        """
        if self.stall_timeout is None:
            return
        for module in list(self.modules.values()):
            if not module._rx_have or not self._is_routed(module):
                continue
            idle = now - module._rx_last
            if idle < self.stall_timeout:
                continue
            try:
                self._drop_quietly(
                    module,
                    f"DROPPING - {module!s} - Stalled mid-message for {idle:.1f} s, after {module._rx_have} of {module._rx_need} bytes.",
                )
            except Exception:
                self.logger.exception(
                    f"Unexpected error while dropping stalled module {module!s}."
                )

    def _core_size_matches(self, mod: Module, header: MessageHeader) -> bool:
        """Check a core message's size against its core definition.

        User message types pass unchecked: the manager doesn't know their
        definitions and forwards them as they are. Core types must match, and
        a client that sends an unknown core type or a mismatched size is
        dropped, because its core definitions don't match the manager's.

        Args:
            mod: The module that sent the message.
            header: The message's header.

        Returns:
            True if the message may be processed, False if the client was
            dropped.
        """
        msg_type = header.msg_type
        if msg_type >= _FIRST_USER_MSG_TYPE:
            return True

        data_cls = self._core_defs.get(msg_type)
        if data_cls is None:
            self.logger.critical(
                f"DROPPING - {mod!s} - Unknown core_def MT={msg_type} received."
            )
            self.remove_module(mod)
            return False

        if header.num_data_bytes != data_cls.type_size:
            self.logger.error(
                f"DROPPING - {mod!s} - {data_cls.type_name} (MT={msg_type}) announced {header.num_data_bytes} data bytes, but its core definition has {data_cls.type_size}. The client's core definitions don't match the manager's."
            )
            self.remove_module(mod)
            return False

        return True

    def forward_message(
        self,
        src_module: Module,
        header: MessageHeader,
        data: Union[bytes, memoryview, MessageData],
    ):
        """Forward a message from other modules

        The given message will be forwarded to:

            - all subscribed logger modules
            - if the message has a destination address, and it is subscribed to by that destination it will be forwarded only there
            - if the message has no destination address, it will be forwarded to all subscribed modules or those subscribed to ALL_MESSAGE_TYPES

        Args:
            src_module (Module): Module where message originated from
            header (MessageHeader): Message Header
            data (Union[bytes, MessageData]): Message Data
        """

        src_name = src_module.name or f"Module({src_module.mod_id})"

        dest_mod_id = header.dest_mod_id
        dest_host_id = header.dest_host_id

        # Verify that the module & host ids are valid
        if dest_mod_id < 0 or dest_mod_id > cd.MAX_MODULE_ID:
            self.logger.error(
                f"MessageManager::forward_message: Got invalid dest_mod_id [{dest_mod_id}] from {src_name}"
            )
            return

        # ALL_HOSTS is valid too. Host IDs don't affect routing otherwise.
        if dest_host_id != cd.ALL_HOSTS and (
            dest_host_id < 0 or dest_host_id > cd.MAX_HOSTS
        ):
            self.logger.error(
                f"MessageManager::forward_message: Got invalid dest_host_id [{dest_host_id}] from {src_name}"
            )
            return

        # The subscribers to this message type and to every type. get(), not
        # [], so that a type nobody subscribes to doesn't add an entry to the
        # table. The two sets never share a module: subscribing to
        # ALL_MESSAGE_TYPES drops a module's other subscriptions.
        by_type = self.subscriptions.get(header.msg_type)
        by_all = self.subscriptions.get(ALL_MESSAGE_TYPES)
        # A snapshot, as a tuple: a failed send removes modules from the sets,
        # and modules removed while it's in use are skipped below.
        if by_type and by_all:
            subscribers: Tuple[Module, ...] = (*by_type, *by_all)
        elif by_type:
            subscribers = tuple(by_type)
        elif by_all:
            subscribers = tuple(by_all)
        else:
            return

        modules = self.modules
        with self._routing():
            # Header and payload in one buffer, built once and shared by every
            # recipient: one send per recipient instead of two.
            wire: Optional[bytes] = None

            for module in subscribers:
                # As _is_routed(), without a call per recipient.
                if modules.get(module.conn) is not module:
                    continue

                # Only destinations of the message take part. Other modules
                # aren't sent it, so they can't count as drops either.
                if not (
                    dest_mod_id == 0 or module.mod_id == dest_mod_id or module.is_logger
                ):
                    continue

                if wire is None:
                    # join() copies each part once; bytes() + bytes() would
                    # copy them twice more.
                    wire = b"".join((header, data))

                if module.is_logger:
                    self._send_to_logger(module, header, wire)
                    continue

                try:
                    sent = module.try_send(wire)
                except OSError as err:
                    self._drop_after_send_error(module, header, err)
                    continue

                if sent:
                    module.drops = 0
                else:
                    # A module that can't take the message now misses it; it
                    # isn't waited for and isn't dropped.
                    module.drops += 1
                    print("x", end="", flush=True)
                    self.send_failed_message(module, header, time.perf_counter())

    def send_to_loggers(
        self,
        header: MessageHeader,
        payload: Union[bytes, MessageData],
        *,
        exclude: Optional[Module] = None,
    ):
        """Forward message to registered logger modules

        Args:
            header (MessageHeader): Message header to send
            payload (Union[bytes, MessageData]): Message data to send
            exclude (Module, optional): A logger not to send it to, because it
                was already sent the message directly.
        """
        with self._routing():
            wire = b"".join((header, payload))
            # A snapshot, because a failed send removes the logger from the set.
            for module in list(self.logger_modules):
                if module is exclude or not self._is_routed(module):
                    continue
                self._send_to_logger(module, header, wire)

    def send_message(
        self,
        msg_data: MessageData,
        dest_mod_id: int = 0,
        dest_host_id: int = 0,
        timeout: float = 0,
    ):
        """Send a message originating from MessageManager module

        Args:
            msg_data (MessageData): Object containing the message to send
            dest_mod_id (int, optional): Specific module ID to send to. Defaults to 0 (broadcast).
            dest_host_id (int, optional): Specific host ID to send to. Defaults to 0 (broadcast).
            timeout (float, optional): Reserved. Defaults to 0.
        """
        header = self.header_cls()
        header.msg_type = msg_data.type_id
        header.send_time = time.perf_counter()
        header.src_mod_id = cd.MID_MESSAGE_MANAGER
        header.dest_mod_id = dest_mod_id
        header.dest_host_id = dest_host_id
        header.num_data_bytes = msg_data.type_size
        header.msg_count = 0  # messages from the manager carry no count

        self.forward_message(self.mm_module, header, msg_data)

    def send_ack(self, src_module: Module):
        """Send ACKNOWLEDGE signal header

        Args:
            src_module (Module): Module to send ACK to
        """
        header = self.header_cls()
        header.msg_type = cd.MT_ACKNOWLEDGE
        header.send_time = time.perf_counter()
        header.src_mod_id = cd.MID_MESSAGE_MANAGER
        header.dest_mod_id = src_module.mod_id
        header.num_data_bytes = 0
        header.msg_count = 0  # messages from the manager carry no count

        # Queued behind anything not yet sent rather than dropped: the client
        # is waiting for it.
        try:
            src_module.send_message(header, b"")
        except OSError as err:
            self._drop_after_send_error(src_module, header, err)

        # Always forward to logger modules, except the requester: a logger
        # sent its own ACK twice would take the copy as the reply to its next
        # request.
        self.send_to_loggers(header, b"", exclude=src_module)

    def send_failed_message(
        self,
        dest_module: Module,
        header: MessageHeader,
        time_of_failure: float,
    ):
        """Send FAILED_MESSAGE

        Args:
            dest_module (Module): Intended destination
            header (MessageHeader): Header of failed message
            time_of_failure (float): Time of send failure
        """
        # Avoid infinite recursion
        if header.msg_type in (
            cd.MT_FAILED_MESSAGE,
            cd.MT_RTMA_LOG,
            cd.MT_RTMA_LOG_CRITICAL,
            cd.MT_RTMA_LOG_ERROR,
            cd.MT_RTMA_LOG_WARNING,
            cd.MT_RTMA_LOG_INFO,
            cd.MT_RTMA_LOG_DEBUG,
        ):
            return

        out_header = self.header_cls()
        data = cd.MDF_FAILED_MESSAGE()
        out_header.msg_type = cd.MT_FAILED_MESSAGE
        out_header.send_time = time.perf_counter()
        out_header.src_mod_id = cd.MID_MESSAGE_MANAGER
        out_header.num_data_bytes = ctypes.sizeof(data)
        out_header.msg_count = 0  # messages from the manager carry no count

        data.dest_mod_id = dest_module.mod_id
        data.time_of_failure = time_of_failure

        # Copy the values into the RTMA_MSG_HEADER
        for fname, ftype, *_ in data.msg_header._fields_:
            setattr(data.msg_header, fname, getattr(header, fname))

        # send to logger modules AND modules subscribed to FAILED_MESSAGE
        self.forward_message(self.mm_module, out_header, data)

    def send_goodbye(self, module: Module):
        """Send GOODBYE

        Args:
            module (Module): Closed module object
        """
        self.logger.debug("GOODBYE")
        msg = cd.MDF_GOODBYE()
        msg.pid = module.pid
        msg.mod_id = module.mod_id
        msg.port = module.port
        msg.name = module.name
        msg.addr = module.addr
        self.send_message(msg)

    def send_hello(self, module: Module, dest_mod_id: int = 0):
        """Send HELLO, for a module that has connected

        A module that hasn't connected has nothing to introduce, and would get
        no GOODBYE later, so nothing is sent for it.

        Args:
            module (Module): Module object to send info for
        """
        if not module.connected:
            return
        self.logger.debug("HELLO")
        msg = cd.MDF_HELLO()
        msg.pid = module.pid
        msg.mod_id = module.mod_id
        msg.port = module.port
        msg.name = module.name
        msg.addr = module.addr
        self.send_message(msg, dest_mod_id=dest_mod_id)

    def send_introductions(self, dest_module: Module):
        """Send a module a HELLO for every connected module, itself included.

        The manager's own entry and sockets that haven't connected are left
        out. A send that fails drops its module without stopping the rest,
        and the introductions stop if the requester itself is dropped.

        Args:
            dest_module (Module): The module that sent INTRODUCE.
        """
        self.logger.info(f"INTRODUCE -> {dest_module.name}")
        # One forward for all the HELLOs, so that modules dropped meanwhile
        # are closed, and get their GOODBYE, after the last one.
        with self._routing():
            # A snapshot: a failed send removes a module from self.modules.
            for module in list(self.modules.values()):
                if not self._is_routed(dest_module):
                    break
                if module is self.mm_module or not module.connected:
                    continue
                if not self._is_routed(module):
                    continue
                self.send_hello(module, dest_mod_id=dest_module.mod_id)

    def decode_core_message(
        self, src_module: Module, hdr: MessageHeader
    ) -> Union[Message, None]:
        data_cls = self._core_defs.get(hdr.msg_type)
        if data_cls:
            data = data_cls.from_buffer(self.data_buffer)
            return Message(hdr, data)
        else:
            self.logger.critical(
                f"Unknown core_def MT={hdr.msg_type} received from {src_module.name}"
            )
            self.remove_module(src_module)
            return None

    def process_core_message(self, src_module: Module, header: MessageHeader):
        """Process incoming core message

        Args:
            src_module (Module): Message source module
            header (MessageHeader): Message header of the incoming message
        """
        msg_type = header.msg_type
        if msg_type >= _FIRST_USER_MSG_TYPE:
            return

        core_msg = self.decode_core_message(src_module, header)
        if core_msg is None:
            return

        if msg_type == cd.MT_CONNECT or msg_type == cd.MT_CONNECT_V2:
            if src_module.connected:
                self.update_connection(src_module, core_msg)
            elif self.connect_module(src_module, core_msg):
                self.send_ack(src_module)
                self.send_hello(src_module)
                if msg_type == cd.MT_CONNECT:
                    self.logger.info(f"CONNECT - {src_module!s}")
                else:
                    self.logger.info(f"CONNECT v2 - {src_module!s}")
        elif msg_type == cd.MT_DISCONNECT:
            self.disconnect_module(src_module)
            self.logger.info(f"DISCONNECT - {src_module!s}")
        elif msg_type == cd.MT_SUBSCRIBE:
            self.add_subscription(src_module, core_msg)
            self.send_ack(src_module)
        elif msg_type == cd.MT_UNSUBSCRIBE:
            self.remove_subscription(src_module, core_msg)
            self.send_ack(src_module)
        elif msg_type == cd.MT_PAUSE_SUBSCRIPTION:
            self.pause_subscription(src_module, core_msg)
            self.send_ack(src_module)
        elif msg_type == cd.MT_RESUME_SUBSCRIPTION:
            self.resume_subscription(src_module, core_msg)
            self.send_ack(src_module)
        elif msg_type == cd.MT_CLIENT_SET_NAME:
            self.set_module_name(src_module, core_msg)
            self.send_hello(src_module)
        elif msg_type == cd.MT_MODULE_READY:
            self.register_module_ready(src_module, core_msg)
            self.send_hello(src_module)
        elif msg_type == cd.MT_INTRODUCE:
            self.send_introductions(src_module)

    def process_message(self, src_module: Module, header: MessageHeader):
        """Process incoming message

        Args:
            src_module (Module): Message source module
            header (MessageHeader): Message header of the incoming message
        """

        # A module must connect before it does anything else.
        if not src_module.connected and header.msg_type not in (
            cd.MT_CONNECT,
            cd.MT_CONNECT_V2,
        ):
            self._drop_quietly(
                src_module,
                f"DROPPING - {src_module!s} - Sent MT={header.msg_type} before CONNECT; a module must connect first.",
            )
            return

        # Handle any internal core messages that come through
        self.process_core_message(src_module, header)

        # A message whose handling dropped its sender, such as a refused
        # CONNECT, isn't passed on. DISCONNECT is, since it drops its sender by
        # design.
        if not self._is_routed(src_module) and header.msg_type != cd.MT_DISCONNECT:
            return

        # Forward all messages that come through to MM
        # %-style arguments, so the text is only built when debug is on.
        self.logger.debug("FORWARD - msg_type:%d from %s", header.msg_type, src_module)
        data = self.data_view[: header.num_data_bytes]
        self.forward_message(src_module, header, data)

    def close(self):
        """Close manager server"""
        self._keep_running = False

    def _accept_connection(self) -> None:
        """Accept a pending connection and register it as a module.

        A connection that fails while being accepted or set up is logged and
        discarded; the manager keeps running.
        """
        try:
            conn, address = self.listen_socket.accept()
        except OSError as err:
            self.logger.warning(f"Failed to accept a new connection - {err!s}")
            return

        refusal = None
        if self._max_sockets is not None and len(self.modules) >= self._max_sockets:
            refusal = f"the limit of {self._max_sockets} sockets that select() can watch is reached"
        elif self._max_fd is not None and conn.fileno() >= self._max_fd:
            refusal = f"its descriptor ({conn.fileno()}) is beyond what select() can watch (below {self._max_fd})"
        if refusal is not None:
            self.logger.warning(
                f"Refusing connection from {address[0]}:{address[1]} - {refusal}."
            )
            conn.close()
            return

        self.logger.info(f"New connection accepted from {address[0]}:{address[1]}")

        try:
            # Disable Nagle Algorithm
            conn.setsockopt(socket.getprotobyname("tcp"), socket.TCP_NODELAY, 1)
            # Set explicitly: whether an accepted socket inherits the listening
            # socket's mode differs between operating systems.
            conn.setblocking(False)
        except OSError as err:
            self.logger.warning(
                f"Closing new connection from {address[0]}:{address[1]} - {err!s}"
            )
            conn.close()
            return

        self.sockets.append(conn)
        self.modules[conn] = Module(conn, address, self.header_cls)

    def _handle_client(self, client_socket: socket.socket, src: Module) -> None:
        """Read and process one message from a client.

        This is the boundary for failures caused by one client. A connection
        error disconnects it, and any other exception is logged with its
        traceback and drops it, so the manager keeps serving the others.

        Args:
            client_socket: The client's socket, which has data to read.
            src: The client's module.
        """
        try:
            msg_hdr = self.read_message(client_socket)
            if msg_hdr is not None:
                self.process_message(src, msg_hdr)
        except ConnectionError as err:
            self.disconnect_module(src)
            self.logger.error(
                f"Connection Error on read, disconnecting  {src!s} - {err!s}"
            )
        except Exception:
            self.logger.exception(
                f"DROPPING - {src!s} - Unexpected error while handling its message."
            )
            self.remove_module(src)

    def run(self):
        """Start the message manager server

        Runs until :meth:`close` is called or ``KeyboardInterrupt``. A failure
        caused by one client drops that client and doesn't stop the loop.
        """
        self._keep_running = True
        next_stall_check = 0.0
        try:
            with disable_message_validation():
                while self._keep_running:
                    # Wait for data to read, and for room in the connections
                    # that have bytes queued. The read list always holds the
                    # listening socket, which matters on Windows, where
                    # select() rejects three empty lists.
                    pending = [m.conn for m in self.modules.values() if m._outbox]
                    rlist, wlist, _ = select.select(
                        self.modules.keys(), pending, [], self.read_timeout
                    )

                    for client_socket in wlist:
                        module = self.modules.get(client_socket)
                        if module is not None:
                            self._flush_module(module)

                    # Check for an incoming connection request
                    if self.listen_socket in rlist:
                        rlist.remove(self.listen_socket)
                        self._accept_connection()

                    # Randomly select the order of sockets with data.
                    random.shuffle(rlist)

                    for client_socket in rlist:
                        # Check that module is still active
                        src = self.modules.get(client_socket)
                        if src is not None:
                            self._handle_client(client_socket, src)

                    # Once per read_timeout, traffic or not: select() wakes
                    # at least that often.
                    now = time.monotonic()
                    if now >= next_stall_check:
                        self._drop_stalled(now)
                        next_stall_check = now + self.read_timeout

        except KeyboardInterrupt:
            self.logger.info("Stopping Message Manager")
        finally:
            for sock in list(self.modules):
                sock.close()
            for module in self._closing:
                module.close()


def _positive_seconds(text: str) -> float:
    """Parse a command-line duration that must be positive.

    Args:
        text: The argument as given.

    Returns:
        The number of seconds.

    Raises:
        argparse.ArgumentTypeError: It isn't a positive number.
    """
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {text!r}") from None
    if not value > 0:
        raise argparse.ArgumentTypeError(f"must be positive: {text!r}")
    return value


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse the manager's command line.

    Args:
        argv: The arguments, without the program name. Defaults to
            ``sys.argv[1:]``.

    Returns:
        The parsed arguments.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-a",
        "--addr",
        type=str,
        default="",
        help="Listener address. IP address/hostname as a string. Default is '' which is evaluated as socket.INADDR_ANY.",
    )
    parser.add_argument(
        "-p", "--port", type=int, default=7111, help="Listener port. Default is 7111."
    )
    parser.add_argument("-d", "--debug", action="store_true", help="Debug mode")
    parser.add_argument(
        "--log-level",
        dest="log_level",
        choices=["DEBUG", "INFO", "WARN", "ERROR"],
        default="INFO",
        help="Logging Level",
    )
    stall = parser.add_mutually_exclusive_group()
    stall.add_argument(
        "--stall-timeout",
        type=_positive_seconds,
        default=DEFAULT_STALL_TIMEOUT,
        metavar="SECONDS",
        help=f"Drop a client that stops partway through sending a message for this long. Default is {DEFAULT_STALL_TIMEOUT:g}.",
    )
    stall.add_argument(
        "--no-stall-timeout",
        dest="stall_timeout",
        action="store_const",
        const=None,
        help="Never drop a client that stops partway through a message, for example at a debugger breakpoint.",
    )
    parser.add_argument(
        "--logger-timeout",
        type=_positive_seconds,
        default=None,
        metavar="SECONDS",
        help="Drop a logger module that can't take a message for this long. By default the manager waits as long as it takes.",
    )
    return parser.parse_args(argv)


def main():
    args = _parse_args()

    if args.addr:  # a non-empty host address was passed in.
        ip_addr = args.addr
    else:
        ip_addr = ""  # socket.INADDR_ANY

    if args.log_level == "DEBUG":
        level = logging.DEBUG
    elif args.log_level == "INFO":
        level = logging.INFO
    elif args.log_level == "WARN":
        level = logging.WARN
    elif args.log_level == "ERROR":
        level = logging.ERROR
    else:
        print("Unknown log level. Using INFO instead")
        level = logging.INFO

    with disable_message_validation():
        msg_mgr = MessageManager(
            ip_address=ip_addr,
            port=args.port,
            log_level=level,
            debug=args.debug,
            stall_timeout=args.stall_timeout,
            logger_timeout=args.logger_timeout,
        )

        msg_mgr.run()


if __name__ == "__main__":
    main()
