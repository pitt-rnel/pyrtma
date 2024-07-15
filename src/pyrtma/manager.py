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
import typing
import tempfile

import graphviz

from .client_logging import RTMALogger, ClientLike
from .validators import disable_message_validation
from .message import Message, get_msg_defs
from .header import MessageHeader, get_header_cls
from .message_data import MessageData
from .context import get_core_defs, get_context
from .core_defs import ALL_MESSAGE_TYPES
from . import core_defs as cd

from typing import Dict, List, Tuple, Set, Type, Union, Optional
from itertools import chain
from dataclasses import dataclass, field
from collections import defaultdict, Counter


@dataclass
class Module:
    """Module dataclass

    Used internally by MessageManager to manage connections to each client module.
    """

    uid: int
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
    unique: bool = True
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

    def send_message(self, header: MessageHeader, payload: Union[bytes, MessageData]):
        """Send a message

        Args:
            header (MessageHeader): Message header
            payload (Union[bytes, MessageData]): Message data
        """
        self.msg_count += 1
        header.msg_count = self.msg_count

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

        self.msg_count += 1
        header.msg_count = self.msg_count

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

    TRAFFIC_INTERVAL = 1.0
    INFO_INTERVAL = 5.0
    _keep_running = True

    def __init__(
        self,
        ip_address: str = "",  # "" equivalent to socket.INADDR_ANY
        port: int = 7111,
        timecode=False,
        log_level=logging.INFO,
        debug=False,
        send_msg_timing=True,
        enable_graph=False,
    ):
        """MessageManager class

        RTMA Message Manager server implemented in python.

        Args:
            ip_address (str, optional): server IP address. Defaults to "".
            timecode (bool, optional): Flag to use message header with timecode values. Defaults to False.
            debug (bool, optional): Flag for debug mode. Defaults to False.
            send_msg_timing (bool, optional): Flag to send TIMING_MSG. Defaults to True.
        """
        self.ip_address = ip_address
        self.port = port

        self.header_cls = get_header_cls(timecode)
        self.header_size = ctypes.sizeof(self.header_cls)
        self.header_buffer = bytearray(self.header_size)
        self.header_view = memoryview(self.header_buffer)

        self.read_timeout = 0.200
        self.write_timeout = 0  # c++ message manager uses timeout = 0 for all modules except logger modules, which uses -1 (blocking)
        self._debug = debug
        self.b_send_msg_timing = send_msg_timing

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
        self.next_dynamic_mod_id_offset = 0

        self.subscriptions: Dict[int, Set[Module]] = defaultdict(set)
        self.sockets = [self.listen_socket]
        self.start_time = time.time()

        # dictionary of message type ids and message counts, reset each time timing_message is sent
        self.message_counts: typing.Counter[int] = Counter()
        self.t_last_message_count = time.perf_counter()
        self.min_timing_message_period = 0.9

        self.last_client_info: float = time.perf_counter()
        self.traffic_counter: typing.Counter[int] = Counter()
        self.traffic_start: float = time.perf_counter()
        self.traffic_seqno: int = 1

        # Disable Nagle Algorithm
        self.listen_socket.setsockopt(
            socket.getprotobyname("tcp"), socket.TCP_NODELAY, 1
        )

        self._uid = 0
        self.wlist: List[socket.socket] = []

        # Add message manager to its module list
        self.mm_module = Module(
            uid=0,
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

        # Address Reuse allowed for testing
        if debug:
            self.listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.graph = RTMAGraph()
        self.graph.enabled = enable_graph

        self.logger.info("Message Manager Initialized.")

    @property
    def connected(self) -> bool:
        return True

    @property
    def logger(self) -> RTMALogger:
        return self._logger

    def generate_uid(self) -> int:
        self._uid += 1
        return self._uid

    def assign_module_id(self) -> int:
        """Assign module ID dynamically to connecting module

        Raises:
            RuntimeError: Exceeded maximum number of allowed dynamic modules

        Returns:
            int: module ID
        """
        current_ids = [mod.mod_id for mod in self.modules.values()]

        MAX_DYN_IDS = cd.MAX_MODULES - cd.DYN_MOD_ID_START
        for i in range(0, MAX_DYN_IDS):
            mod_id = self.next_dynamic_mod_id_offset + cd.DYN_MOD_ID_START
            self.next_dynamic_mod_id_offset += 1
            if self.next_dynamic_mod_id_offset == MAX_DYN_IDS:
                self.next_dynamic_mod_id_offset = 0

            # check if mod id is already used, if it is, continue looping until we find an unused one
            if mod_id not in current_ids:
                return mod_id

        # if we exit loop without returning, we failed to find a valid id
        self.logger.error(
            f"MessageManager::assign_module_id: All valid dynamic IDs are in use"
        )

        raise RuntimeError("Exceeded maximum limit of allowed modules.")

    @property
    def header(self) -> MessageHeader:
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
            module.unique = msg.data.allow_multiple == 0
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
        module.is_daemon = msg.data.daemon_status == 1

        if module.mod_id != 0:
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
                    if m.unique:
                        self.logger.error(
                            f"SET_ID - {module.ipaddr} - ID({module.mod_id}) - ID already in use. Closing connection."
                        )
                        self.remove_module(module)
                        return False

                    if module.unique:
                        self.logger.error(
                            f"SET_ID - {module.ipaddr} - ID({module.mod_id}) - ID already in use. Closing connection."
                        )
                        self.remove_module(module)
                        return False

                if module.name:
                    if (m.unique or module.unique) and (m.name == module.name):
                        self.logger.error(
                            f"SET_NAME - {module.ipaddr} - ID({module.mod_id}) - {module.name} - Name already in use."
                        )
                        self.remove_module(module)
                        return False

                    self.logger.debug(
                        f"SET_NAME - {module.ipaddr} - ID({module.mod_id}) - {module.name}"
                    )

        else:
            module.mod_id = self.assign_module_id()

        module.connected = True

        if module.is_logger:
            self.logger_modules.add(module)

        return True

    def remove_module(self, module: Module):
        """Remove connected module

        Args:
            module (Module): Module object to remove
        """
        # Drop all subscriptions for this module
        for msg_type in module.subs:
            self.subscriptions[msg_type].discard(module)

        # Discard from logger module set if needed
        self.logger_modules.discard(module)

        # Drop from our module mapping
        module.close()

        self.send_client_close(module)
        del self.modules[module.conn]

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
        name_msg = cd.MDF_CLIENT_SET_NAME.from_buffer(msg.data)
        src_module.name = name_msg.name or ""
        self.logger.info(
            f"SET_NAME - {src_module.ipaddr} - ID({src_module.mod_id}) - {src_module.name}"
        )

    def read_message(self, sock: socket.socket) -> bool:
        """Read an incoming message

        Args:
            sock (socket.socket): socket to read from

        Returns:
            bool: Success code
        """
        # Read RTMA Header Section
        nbytes = sock.recv_into(
            self.header_buffer, self.header_size, socket.MSG_WAITALL
        )

        if nbytes != self.header_size:
            mod = self.modules[sock]
            self.remove_module(mod)
            self.logger.warning(
                f"DROPPING - {mod!s} - No header returned from sock.recv_into."
            )
            return False

        # Read Data Section
        data_size = self.header.num_data_bytes
        if data_size:
            nbytes = sock.recv_into(self.data_buffer, data_size, socket.MSG_WAITALL)

            if nbytes != data_size:
                mod = self.modules[sock]
                self.remove_module(mod)
                self.logger.warning(
                    f"DROPPING - {mod!s} - No data returned from sock.recv_into."
                )
                return False

        return True

    def forward_message(
        self,
        src_module: Module,
        header: MessageHeader,
        data: Union[bytes, MessageData],
        count: bool = True,
    ):
        """Forward a message from other modules

        The given message will be forwarded to:

            - all subscribed logger modules
            - if the message has a destination address, and it is subscribed to by that destination it will be forwarded only there
            - if the message has no destination address, it will be forwarded to all subscribed modules or those subscribed to ALL_MESSAGE_TYPES

        Args:
            header (MessageHeader): Message Header
            data (Union[bytes, MessageData]): Message Data
        """

        # message counts (Skip traffic count)
        if header.msg_type not in (cd.MT_MESSAGE_TRAFFIC, cd.MT_FAILED_MESSAGE):
            if self.b_send_msg_timing:
                self.message_counts[header.msg_type] += 1
            self.traffic_counter[header.msg_type] += 1

        dest_mod_id = header.dest_mod_id
        dest_host_id = header.dest_host_id

        # Verify that the module & host ids are valid
        if dest_mod_id < 0 or dest_mod_id > cd.MAX_MODULES:
            self.logger.error(
                f"MessageManager::forward_message: Got invalid dest_mod_id [{dest_mod_id}]"
            )
            return

        if dest_host_id < 0 or dest_host_id > cd.MAX_HOSTS:
            self.logger.error(
                f"MessageManager::forward_message: Got invalid dest_host_id [{dest_host_id}]"
            )
            return

        # Subscriber set for this message type
        subscribers = list(
            chain(
                self.subscriptions[header.msg_type],
                self.subscriptions[ALL_MESSAGE_TYPES],
            )
        )

        for n in range(len(subscribers)):
            module = subscribers[n]
            if module.conn in self.wlist:
                try:
                    if (
                        dest_mod_id == 0
                        or (module.mod_id == dest_mod_id)
                        or module.is_logger
                    ):
                        module.send_message(header, data)
                        self.graph.update(
                            src_module, module, header.msg_type, header.send_time
                        )
                        module.drops = 0
                except ConnectionError as err:
                    self.remove_module(module)
                    self.logger.error(
                        f"Connection Error on write to {module!s} - {err!s}"
                    )
                    print("x", end="", flush=True)
                    self.send_failed_message(module, header, time.perf_counter())
            elif module.is_logger:
                # Block until logger is ready
                select.select([], [module.conn], [], None)

                try:
                    module.send_message(header, data)
                    self.graph.update(
                        src_module, module, header.msg_type, header.send_time
                    )
                    module.drops = 0
                except ConnectionError as err:
                    self.remove_module(module)
                    self.logger.error(
                        f"Connection Error on write to {module!s} - {err!s}"
                    )
                    print("x", end="", flush=True)
                    # this could result in infinite recursion,
                    # this is prevented by send_failed_message returning if
                    # failed message type is failed_message.
                    self.send_failed_message(module, header, time.perf_counter())

            else:
                module.drops += 1
                print("x", end="", flush=True)
                self.send_failed_message(module, header, time.perf_counter())

    def send_to_loggers(
        self,
        header: MessageHeader,
        payload: Union[bytes, MessageData],
    ):
        """Forward message to registered logger modules

        Args:
            header (MessageHeader): Message header to send
            payload (Union[bytes, MessageData]): Message data to send
            wlist (List[socket.socket]): Sockets ready for writing
        """
        for module in self.logger_modules:
            if module.conn not in self.wlist:
                # Block until logger is ready
                select.select([], [module.conn], [], None)
            try:
                module.send_message(header, payload)
                module.drops = 0
            except ConnectionError as err:
                self.remove_module(module)
                self.logger.error(f"Connection Error on write to {module!s} - {err!s}")
                print("x", end="", flush=True)
                # this could result in infinite recursion,
                # this is prevented by send_failed_message returning if
                # failed message type is failed_message.
                self.send_failed_message(module, header, time.perf_counter())

    def send_message(
        self,
        msg_data: MessageData,
        dest_mod_id: int = 0,
        dest_host_id: int = 0,
        timeout: float = 0,
    ):
        header = self.header_cls()
        header.msg_type = msg_data.type_id
        header.send_time = time.perf_counter()
        header.src_mod_id = cd.MID_MESSAGE_MANAGER
        header.dest_mod_id = dest_mod_id
        header.num_data_bytes = msg_data.type_size

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

        try:
            src_module.send_message(header, b"")
        except ConnectionError as err:
            self.remove_module(src_module)
            self.logger.error(f"Connection Error on write to {src_module!s} - {err!s}")
            print("x", end="", flush=True)
            self.send_failed_message(src_module, header, time.perf_counter())

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

        data.dest_mod_id = dest_module.mod_id
        data.time_of_failure = time_of_failure

        # Copy the values into the RTMA_MSG_HEADER
        for fname, ftype, *_ in data.msg_header._fields_:
            setattr(data.msg_header, fname, getattr(header, fname))

        # send to logger modules AND modules subscribed to FAILED_MESSAGE
        self.forward_message(self.mm_module, out_header, data)

    def send_timing_message(self):
        """Send TIMING_MESSAGE"""
        data = cd.MDF_TIMING_MESSAGE()
        for mt, count in self.message_counts.items():
            data.timing[mt] = count
        self.message_counts.clear()

        for mod in self.modules.values():
            data.ModulePID[mod.mod_id] = mod.pid

        self.send_message(data)

    def send_traffic(self):
        self.logger.debug("MESSAGE_TRAFFIC")
        data = cd.MDF_MESSAGE_TRAFFIC()
        now = time.perf_counter()
        sub_seqno = 1
        nsent = 0
        i = -1
        for n, (mt, count) in enumerate(self.traffic_counter.items()):
            data.seqno = self.traffic_seqno
            data.sub_seqno = sub_seqno
            data.start_timestamp = self.traffic_start
            data.end_timestamp = now

            i = n % cd.MESSAGE_TRAFFIC_SIZE
            data.msg_type[i] = mt
            data.msg_count[i] = count

            if (n % cd.MESSAGE_TRAFFIC_SIZE) == 0:
                nsent = n
                self.send_message(data)
                sub_seqno += 1

        # Send any remaining
        if i >= 0:
            i += 1
            if nsent < len(self.traffic_counter):
                data.msg_type[i:] = [-1 for _ in range(cd.MESSAGE_TRAFFIC_SIZE - i)]
                self.send_message(data)

        self.traffic_counter.clear()
        self.traffic_start = now
        self.traffic_seqno += 1

    def send_client_close(self, module: Module):
        self.logger.debug("CLIENT_CLOSE")
        msg = cd.MDF_CLIENT_CLOSED()
        msg.uid = module.uid
        msg.pid = module.pid
        msg.mod_id = module.mod_id
        msg.is_logger = module.is_logger
        msg.is_unique = module.unique
        msg.port = module.port
        msg.name = module.name
        msg.addr = module.addr
        self.send_message(msg)

    def send_client_info(self, module: Module):
        self.logger.debug("CLIENT_INFO")
        msg = cd.MDF_CLIENT_INFO()
        msg.uid = module.uid
        msg.pid = module.pid
        msg.mod_id = module.mod_id
        msg.is_logger = module.is_logger
        msg.is_unique = module.unique
        msg.port = module.port
        msg.name = module.name
        msg.addr = module.addr
        self.send_message(msg)

    def send_active_clients(self):
        self.logger.debug("ACTIVE_CLIENTS")
        msg = cd.MDF_ACTIVE_CLIENTS()
        msg.timestamp = time.perf_counter()

        for i, (sock, module) in enumerate(self.modules.items()):
            # if sock == self.listen_socket:
            #     continue
            msg.client_mod_id[i] = module.mod_id
            msg.client_pid[i] = module.pid
            self.send_client_info(module)

        msg.num_clients = len(self.modules) - 1
        self.send_message(msg)
        self.last_client_info = msg.timestamp

    @property
    def message(self) -> Message:
        hdr = self.header
        data_cls = get_core_defs().get(hdr.msg_type)
        if data_cls:
            data = data_cls.from_buffer(self.data_buffer)
            return Message(
                hdr, get_core_defs()[hdr.msg_type].from_buffer(self.data_buffer)
            )
        else:
            raise RuntimeError(f"Unknown core_def MT={hdr.msg_type}")

    def process_message(self, src_module: Module):
        """Process incoming message

        Args:
            src_module (Module): Message source module
        """
        hdr = self.header
        msg_type = hdr.msg_type

        if msg_type == cd.MT_CONNECT or msg_type == cd.MT_CONNECT_V2:
            if self.connect_module(src_module, self.message):
                self.send_ack(src_module)
                self.send_client_info(src_module)
                if msg_type == cd.MT_CONNECT:
                    self.logger.info(f"CONNECT - {src_module!s}")
                else:
                    self.logger.info(f"CONNECT v2 - {src_module!s}")
        elif msg_type == cd.MT_DISCONNECT:
            self.disconnect_module(src_module)
            self.logger.info(f"DISCONNECT - {src_module!s}")
        elif msg_type == cd.MT_SUBSCRIBE:
            self.add_subscription(src_module, self.message)
            self.send_ack(src_module)
        elif msg_type == cd.MT_UNSUBSCRIBE:
            self.remove_subscription(src_module, self.message)
            self.send_ack(src_module)
        elif msg_type == cd.MT_PAUSE_SUBSCRIPTION:
            self.pause_subscription(src_module, self.message)
            self.send_ack(src_module)
        elif msg_type == cd.MT_RESUME_SUBSCRIPTION:
            self.resume_subscription(src_module, self.message)
            self.send_ack(src_module)
        elif msg_type == cd.MT_CLIENT_SET_NAME:
            self.set_module_name(src_module, self.message)
            self.send_client_info(src_module)
        elif msg_type == cd.MT_MODULE_READY:
            self.register_module_ready(src_module, self.message)
            self.send_client_info(src_module)
        else:
            self.logger.debug(f"FORWARD - msg_type:{hdr.msg_type} from {src_module!s}")
            data = self.data_view[: hdr.num_data_bytes]
            self.forward_message(src_module, hdr, data)

    def close(self):
        """Close manager server"""
        self._keep_running = False

    def run(self):
        """Start the message manager server"""
        try:
            with disable_message_validation():
                while self._keep_running:
                    rlist, _, _ = select.select(
                        self.modules.keys(), [], [], self.read_timeout
                    )

                    # Check for an incoming connection request
                    if len(rlist) > 0:
                        try:
                            rlist.remove(self.listen_socket)
                            (conn, address) = self.listen_socket.accept()
                            self.logger.info(
                                f"New connection accepted from {address[0]}:{address[1]}"
                            )

                            # Disable Nagle Algorithm
                            conn.setsockopt(
                                socket.getprotobyname("tcp"), socket.TCP_NODELAY, 1
                            )

                            self.sockets.append(conn)
                            self.modules[conn] = Module(
                                self.generate_uid(), conn, address, self.header_cls
                            )
                        except ValueError:
                            pass

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
                            if src:
                                try:
                                    got_msg = self.read_message(client_socket)
                                except ConnectionError as err:
                                    self.disconnect_module(src)
                                    self.logger.error(
                                        f"Connection Error on read, disconnecting  {src!s} - {err!s}"
                                    )
                                    continue

                                if got_msg:
                                    self.process_message(src)

                    now = time.perf_counter()

                    if (
                        self.b_send_msg_timing
                        and (now - self.t_last_message_count)
                        > self.min_timing_message_period
                    ):
                        self.send_timing_message()
                        self.t_last_message_count = now

                    if (now - self.traffic_start) > self.TRAFFIC_INTERVAL:
                        self.send_traffic()

                    if (now - self.last_client_info) > self.INFO_INTERVAL:
                        self.send_active_clients()
                        self.graph.build_graph()

        except KeyboardInterrupt:
            self.logger.info("Stopping Message Manager")
        finally:
            for mod in self.modules:
                mod.close()


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
    parser.add_argument(
        "-T",
        "--disable_timing_msg",
        action="store_true",
        help="Disable sending of TIMING_MESSAGE",
    )

    parser.add_argument(
        "--enable-graph",
        action="store_true",
        help="Enable building module graph output",
    )

    parser.add_argument(
        "--defs",
        dest="defs_file",
        type=str,
        default="",
        help="Path to python message definitions file",
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

    if args.defs_file:
        import pathlib
        import sys
        import importlib

        base = pathlib.Path(args.defs_file).absolute().parent
        fname = pathlib.Path(args.defs_file).stem

        sys.path.insert(0, (str(base.absolute())))
        importlib.import_module(fname)

    with disable_message_validation():
        msg_mgr = MessageManager(
            ip_address=ip_addr,
            port=args.port,
            timecode=args.timecode,
            log_level=level,
            debug=args.debug,
            send_msg_timing=(not args.disable_timing_msg),
            enable_graph=args.enable_graph,
        )

        msg_mgr.run()


class RTMAGraph:
    def __init__(self):
        self._enabled = False
        self.nodes: dict[int, Module] = dict()
        self.edges: dict[tuple[Module, Module], dict[int, list[float]]] = {}
        self.msg_defs = get_msg_defs()
        self.rtma = get_context()
        self.mid2name = {v: k for k, v in self.rtma.MID.items()}

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        if value:
            self._enabled = True
            self.clear()
        else:
            self._enabled = False

    def clear(self):
        self.edges.clear()

    def update(self, src: Module, dest: Module, msg_type: int, send_time: float):
        if not self._enabled:
            return

        # Ignore rtma control messages
        if msg_type < 100:
            return

        # Ignore anything send from MM
        if src == 0:
            return

        if self.nodes.get(src.mod_id) is None:
            self.nodes[src.mod_id] = src

        if self.nodes.get(dest.mod_id) is None:
            self.nodes[dest.mod_id] = dest

        dir = (src, dest)

        if self.edges.get(dir) is None:
            self.edges[dir] = {}
            self.edges[dir][msg_type] = [send_time]
        else:
            if self.edges[dir].get(msg_type) is None:
                self.edges[dir][msg_type] = [send_time]
            else:
                self.edges[dir][msg_type].append(send_time)

    def build_graph(
        self,
    ):
        output_dir = tempfile.gettempdir() + "/rtma_graph"

        dot = graphviz.Digraph(
            "rtma_graph", comment="RTMA Module Graph", format="svg", engine="dot"
        )

        for node in self.nodes.values():
            name = node.name or self.mid2name.get(node.mod_id) or f"MID({node.mod_id})"

            if node.connected:
                dot.node(f"{node.mod_id}", name)
            else:
                dot.node(f"{node.mod_id}", name, color="red")

        for (src, dest), edges in self.edges.items():
            for msg_type, times in edges.items():
                avg = sum(b - a for a, b in zip(times[:-1], times[1:])) / (len(times))

                try:
                    msg_name = self.msg_defs[msg_type].type_name
                except KeyError:
                    msg_name = f"{msg_type}"

                dot.edge(
                    f"{src.mod_id}",
                    f"{dest.mod_id}",
                    constraint="false",
                    labeltooltip=f"avg: {avg:0.3f} s",
                    label=msg_name,
                    labelfloat="true",
                    fontsize="10.0",
                )

        dot.render(directory=output_dir)
        self.clear()


if __name__ == "__main__":
    main()
