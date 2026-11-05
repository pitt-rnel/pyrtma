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
from contextlib import contextmanager


from .client_logging import RTMALogger, ClientLike
from .validators import disable_message_validation
from .message import Message
from .header import MessageHeader, get_header_cls
from .message_data import MessageData
from .core_defs import ALL_MESSAGE_TYPES
from . import core_defs as cd

from typing import Dict, Iterator, List, Tuple, Set, Type, Union, Optional
from itertools import chain
from dataclasses import dataclass, field
from collections import defaultdict

# Message types below this are core types, defined in core_defs. The manager
# checks their size and acts on some of them; it forwards other types as is.
_FIRST_USER_MSG_TYPE: int = cd.MAX_RTMA_MSG_TYPE + 1


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

    def send_message(
        self, header: MessageHeader, payload: Union[bytes, memoryview, MessageData]
    ):
        """Send a message

        The header is sent unchanged, so the recipient sees the sender's
        ``msg_count``. ``Module.msg_count`` counts the messages sent to this
        module, for tracking only; it is not written into the header, which the
        manager shares between all recipients of a message.

        Args:
            header (MessageHeader): Message header
            payload (Union[bytes, memoryview, MessageData]): Message data
        """
        self.msg_count += 1

        self.conn.sendall(header)
        self.conn.sendall(payload)

    def send_ack(self):
        """Send ACKNOWLEDGE signal header"""
        # Just send a header
        header = self.header_cls()
        header.msg_type = cd.MT_ACKNOWLEDGE
        header.send_time = time.perf_counter()
        header.src_mod_id = cd.MID_MESSAGE_MANAGER
        header.dest_mod_id = self.mod_id
        header.num_data_bytes = 0
        header.msg_count = 0  # messages from the manager carry no count

        self.msg_count += 1

        self.conn.sendall(header)

    def close(self):
        """Close connection"""
        self.conn.close()
        self.connected = False

    def __str__(self):
        return f"{self.name or 'ID'}({self.mod_id}) @ {self.ipaddr}"

    def __hash__(self):
        return self.conn.__hash__()


class MessageManager(ClientLike):
    """MessageManager class

    RTMA Message Manager server implemented in python.
    """

    INFO_INTERVAL = 5.0

    def __init__(
        self,
        ip_address: str = "",  # "" equivalent to socket.INADDR_ANY
        port: int = 7111,
        timecode=False,
        log_level=logging.INFO,
        debug=False,
    ):
        """MessageManager class

        RTMA Message Manager server implemented in python.

        Args:
            ip_address (str, optional): server IP address. Defaults to "".
            port (int, optional): server port. Defaults to 7111.
            timecode (bool, optional): Flag to use message header with timecode values. Defaults to False.
            log_level (int, optional): logging level, defaults to logging.INFO.
            debug (bool, optional): Flag for debug mode. Defaults to False.
        """
        self._keep_running = False
        self.ip_address = ip_address
        self.port = port

        self.header_cls = get_header_cls(timecode)
        self.header_size = ctypes.sizeof(self.header_cls)
        self.header_buffer = bytearray(self.header_size)
        self.header_view = memoryview(self.header_buffer)

        self.read_timeout = 0.200
        self.write_timeout = 0  # c++ message manager uses timeout = 0 for all modules except logger modules, which uses -1 (blocking)
        self._debug = debug

        self._logger = RTMALogger(f"message_manager", self, logging.INFO)
        self.logger.set_all_levels(log_level)

        if ip_address == socket.INADDR_ANY:
            ip_address = ""  # bind and Module require a string input, '' is treated as INADDR_ANY by bind

        # Create the tcp listening socket
        self.listen_socket = socket.socket(
            family=socket.AF_INET, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
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
            module.mod_id = msg.data.mod_id
            module.pid = msg.data.pid
            module.name = msg.data.name
        elif isinstance(msg.data, cd.MDF_CONNECT):
            module.mod_id = msg.header.src_mod_id
        else:
            raise RuntimeError(
                f"MessageManager::connect_module: Uknown Connect message definition"
            )

        # fields common to v1 and v2
        module.is_logger = msg.data.logger_status == 1

        if module.mod_id == 0:
            module.mod_id = self.assign_module_id()
        else:
            if module.mod_id < 1 or module.mod_id > cd.DYN_MOD_ID_START:
                self.logger.error(
                    f"Invalid Module id specified: {module.mod_id}. User assigned ids must be in range or 1 - {cd.DYN_MOD_ID_START}"
                )
                self.remove_module(module)
                return False

            for m in self.modules.values():
                if m is module:
                    continue

                if m.mod_id == module.mod_id:
                    self.logger.error(
                        f"SET_ID - {module.ipaddr} - ID({module.mod_id}) - ID already in use. Closing connection."
                    )
                    self.remove_module(module)
                    return False

        module.connected = True

        if module.is_logger:
            self.logger_modules.add(module)

        return True

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
            self.subscriptions[msg_type].discard(module)

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
                module.close()
                self.send_goodbye(module)
        finally:
            self._finishing_removals = False

    @contextmanager
    def _routing(self) -> Iterator[None]:
        """Mark a forward in progress, and finish removals when it ends.

        Forwards nest: a send failure logs an error and sends FAILED_MESSAGE,
        and both are forwarded too. Removals wait until the outermost one ends.

        Yields:
            Nothing; the body sends the message.
        """
        self._forward_depth += 1
        try:
            yield
        finally:
            self._forward_depth -= 1
        self._finish_removals()

    def _drop_after_send_error(
        self, module: Module, header: MessageHeader, err: OSError
    ) -> None:
        """Remove a module whose send failed, and report the failure.

        Args:
            module: The module the send was for.
            header: Header of the message that wasn't delivered.
            err: The error the send raised.
        """
        self.remove_module(module)
        self.logger.error(f"Connection Error on write to {module!s} - {err!s}")
        print("x", end="", flush=True)
        # This could recurse: send_failed_message returns early when the
        # failed message is itself a FAILED_MESSAGE or a log message.
        self.send_failed_message(module, header, time.perf_counter())

    def disconnect_module(self, src_module: Module):
        """Disconnect module

        Args:
            src_module (Module): Module object to disconnect
        """
        self.remove_module(src_module)

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
                self.subscriptions[sub_type].discard(src_module)
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
            self.subscriptions[unsub.msg_type].discard(src_module)

            # Clear out the individual subs
            for sub_type in src_module.subs:
                self.subscriptions[sub_type].discard(src_module)
            src_module.subs.clear()

            self.logger.debug(f"UNSUBSCRIBE- {src_module!s} from ALL_MESSAGE_TYPES")
        else:
            # Ignore individual msg_types unsubs when subscribed to ALL_MESSAGE_TYPES
            if src_module.sub_all:
                return
            self.subscriptions[unsub.msg_type].discard(src_module)
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
        """Read an incoming message

        A client is dropped if its header announces a negative or oversized
        payload, which is checked before the payload is read, or if it sends a
        core message whose size doesn't match its core definition.

        Args:
            sock (socket.socket): socket to read from

        Returns:
            MessageHeader: message header of incoming message, or None if the
            client was dropped
        """
        # Read RTMA Header Section
        nbytes = sock.recv_into(
            self.header_buffer, self.header_size, socket.MSG_WAITALL
        )

        # Module that sent the message
        mod = self.modules[sock]

        if nbytes != self.header_size:
            self.remove_module(mod)
            self.logger.warning(
                f"DROPPING - {mod!s} - Wrong number of header bytes returned from sock.recv_into. Got ({nbytes})."
            )
            return

        header = self.decode_header()

        # Read Data Section into Internal Buffer
        data_size = header.num_data_bytes
        if data_size < 0 or data_size > len(self.data_buffer):
            self.logger.error(
                f"DROPPING - {mod!s} - Invalid num_data_bytes ({data_size}) for MT={header.msg_type}; it must be 0 to {len(self.data_buffer)}. Header may be corrupted."
            )
            self.remove_module(mod)
            return None

        if data_size:
            nbytes = sock.recv_into(self.data_buffer, data_size, socket.MSG_WAITALL)

            if nbytes != data_size:
                self.logger.warning(
                    f"DROPPING - {mod!s} - Wrong number of data bytes returned from sock.recv_into. Got ({nbytes})"
                )
                self.remove_module(mod)
                return

        # Checked after the payload is read, so that a dropped client's socket
        # closes with nothing left unread, which ends the connection cleanly
        # rather than with a reset.
        if not self._core_size_matches(mod, header):
            return None

        return header

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

        if dest_host_id < 0 or dest_host_id > cd.MAX_HOSTS:
            self.logger.error(
                f"MessageManager::forward_message: Got invalid dest_host_id [{dest_host_id}] from {src_name}"
            )
            return

        with self._routing():
            # Subscriber list for this message type. It's a snapshot: modules
            # removed while it's in use are skipped below.
            subscribers = list(
                chain(
                    self.subscriptions[header.msg_type],
                    self.subscriptions[ALL_MESSAGE_TYPES],
                )
            )

            for module in subscribers:
                if not self._is_routed(module):
                    continue

                # Only destinations of the message take part. Other modules
                # aren't sent it, so they can't count as drops either.
                if not (
                    dest_mod_id == 0 or module.mod_id == dest_mod_id or module.is_logger
                ):
                    continue

                if module.conn not in self.wlist:
                    if module.is_logger:
                        # Block until logger is ready
                        select.select([], [module.conn], [], None)
                    else:
                        module.drops += 1
                        print("x", end="", flush=True)
                        self.send_failed_message(module, header, time.perf_counter())
                        continue

                try:
                    module.send_message(header, data)
                    module.drops = 0
                except OSError as err:
                    self._drop_after_send_error(module, header, err)

    def send_to_loggers(
        self,
        header: MessageHeader,
        payload: Union[bytes, MessageData],
    ):
        """Forward message to registered logger modules

        Args:
            header (MessageHeader): Message header to send
            payload (Union[bytes, MessageData]): Message data to send
        """
        with self._routing():
            # A snapshot, because a failed send removes the logger from the set.
            for module in list(self.logger_modules):
                if not self._is_routed(module):
                    continue
                if module.conn not in self.wlist:
                    # Block until logger is ready
                    select.select([], [module.conn], [], None)
                try:
                    module.send_message(header, payload)
                    module.drops = 0
                except OSError as err:
                    self._drop_after_send_error(module, header, err)

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

        try:
            src_module.send_message(header, b"")
        except OSError as err:
            self._drop_after_send_error(src_module, header, err)

        # Always forward to logger modules
        self.send_to_loggers(header, b"")

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
        """Send HELLO

        Args:
            module (Module): Module object to send info for
        """
        self.logger.debug("HELLO")
        msg = cd.MDF_HELLO()
        msg.pid = module.pid
        msg.mod_id = module.mod_id
        msg.port = module.port
        msg.name = module.name
        msg.addr = module.addr
        self.send_message(msg, dest_mod_id=dest_mod_id)

    def send_introductions(self, dest_module: Module):
        self.logger.info(f"INTRODUCE -> {dest_module.name}")
        for module in self.modules.values():
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
            if self.connect_module(src_module, core_msg):
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

        # Handle any internal core messages that come through
        self.process_core_message(src_module, header)

        # Forward all messages that come through to MM
        self.logger.debug(f"FORWARD - msg_type:{header.msg_type} from {src_module!s}")
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

        self.logger.info(f"New connection accepted from {address[0]}:{address[1]}")

        try:
            # Disable Nagle Algorithm
            conn.setsockopt(socket.getprotobyname("tcp"), socket.TCP_NODELAY, 1)
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
        try:
            with disable_message_validation():
                while self._keep_running:
                    rlist, _, _ = select.select(
                        self.modules.keys(), [], [], self.read_timeout
                    )
                    if not rlist:
                        continue

                    # Check for an incoming connection request
                    if self.listen_socket in rlist:
                        rlist.remove(self.listen_socket)
                        self._accept_connection()

                    # Randomly select the order of sockets with data.
                    random.shuffle(rlist)

                    # Check whichs clients are ready to receive data
                    self.wlist.clear()
                    if rlist:
                        _, self.wlist, _ = select.select(
                            [], self.modules.keys(), [], self.write_timeout
                        )

                    for client_socket in rlist:
                        # Check that module is still active
                        src = self.modules.get(client_socket)
                        if src is not None:
                            self._handle_client(client_socket, src)

        except KeyboardInterrupt:
            self.logger.info("Stopping Message Manager")
        finally:
            for sock in list(self.modules):
                sock.close()
            for module in self._closing:
                module.close()


def main():
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
    parser.add_argument(
        "-t", "--timecode", action="store_true", help="Use timecode in message header"
    )

    args = parser.parse_args()

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
            timecode=args.timecode,
            log_level=level,
            debug=args.debug,
        )

        msg_mgr.run()


if __name__ == "__main__":
    main()
