from collections import defaultdict
import socket
import select
import argparse
import logging
import time
import random
from dataclasses import dataclass, field
import ctypes
from typing import Dict, List, Tuple, Set, ClassVar

import pyrtma.core as rtma
from pyrtma.message import RTMA_MESSAGE, RTMA_MSG_HEADER


@dataclass
class RTMA_Module:

    conn: socket.socket
    address: Tuple[str, int]
    id: int = 0
    connected: bool = False
    is_logger: bool = False

    def send_message(self, msg: RTMA_MESSAGE):
        msg_size = RTMA_MESSAGE.header_size + msg.header.num_data_bytes
        payload = memoryview(msg).cast("b")[:msg_size]
        self.conn.sendall(payload)

    def send_ack(self):
        # Just send a header
        header = RTMA_MSG_HEADER()
        header.msg_type = rtma.MT["ACKNOWLEDGE"]
        header.send_time = time.time()
        header.src_mod_id = rtma.MID_MESSAGE_MANAGER
        header.dest_mod_id = self.id
        header.num_data_bytes = 0

        payload = memoryview(header).cast("b")
        self.conn.sendall(payload)

    def close(self):
        self.conn.close()

    def __str__(self):
        return f"Module ID: {self.id} @ {self.address[0]}:{self.address[1]}"


class MessageManager:
    def __init__(self, ip_address: str, port: int, debug=False):

        self.ip_address = ip_address
        self.port = port
        self.timeout = 0.200
        self._debug = debug
        self.logger = logging.getLogger(f"MessageManager@{ip_address}:{port}")

        # Create the tcp listening socket
        self.listen_socket = socket.socket(
            family=socket.AF_INET, type=socket.SOCK_STREAM, proto=socket.IPPROTO_TCP
        )
        self.listen_socket.bind((ip_address, port))
        self.listen_socket.listen(socket.SOMAXCONN)
        self.modules: Dict[socket.socket, RTMA_Module] = {}
        self.logger_modules: Set[RTMA_Module] = set()

        self.subscriptions: Dict[int, Set[RTMA_Module]] = defaultdict(set)
        self.sockets = [self.listen_socket]
        self.start_time = time.time()

        # Disable Nagle Algorithm
        self.listen_socket.setsockopt(
            socket.getprotobyname("tcp"), socket.TCP_NODELAY, 1
        )

        # Add message manager to its module list
        mm_module = RTMA_Module(
            conn=self.listen_socket,
            address=(ip_address, port),
            id=0,
            connected=True,
            is_logger=False,
        )

        self.modules[self.listen_socket] = mm_module

        self.header_size = rtma.constants["HEADER_SIZE"]
        self.recv_buffer = bytearray(ctypes.sizeof(RTMA_MESSAGE))
        self.data_view = memoryview(self.recv_buffer[self.header_size :])

        # Address Reuse allowed for testing
        if debug:
            self.listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        self.logger.info("Message Manager Initialized.")

    def assign_module_id(self):
        current_ids = [mod.id for mod in self.modules.values()]
        next_id = max(current_ids) + 1

        if next_id > 100:
            return next_id
        else:
            return 10

    def connect_module(self, src_module: RTMA_Module, msg: RTMA_MESSAGE):
        if src_module.id == 0:
            src_module.id = self.assign_module_id()

        # Convert the data blob into the correct msg struct
        connect_info = rtma.CONNECT.from_buffer(msg.data)
        src_module.is_logger = connect_info.logger_status == 1
        src_module.connected = True
        if src_module.is_logger:
            self.logger_modules.add(src_module)
        src_module.send_ack()

    def remove_module(self, module: RTMA_Module):
        # Drop all subscriptions for this module
        for msg_type, subscriber_set in self.subscriptions.items():
            subscriber_set.discard(module)

        # Discard from logger module set if needed
        self.logger_modules.discard(module)

        # Drop from our module mapping
        module.close()
        del self.modules[module.conn]

    def disconnect_module(self, src_module: RTMA_Module):
        src_module.send_ack()
        self.remove_module(src_module)

    def add_subscription(self, src_module: RTMA_Module, msg: RTMA_MESSAGE):
        msg_type_id = rtma.SUBSCRIBE.from_buffer(msg.data).value
        self.subscriptions[msg_type_id].add(src_module)

    def remove_subscription(self, src_module: RTMA_Module, msg: RTMA_MESSAGE):
        msg_type_id = rtma.UNSUBSCRIBE.from_buffer(msg.data).value
        # Silently let modules unsubscribe from messages that they are not subscribed to.
        self.subscriptions[msg_type_id].discard(src_module)

    def resume_subscription(self, src_module: RTMA_Module, msg: RTMA_MESSAGE):
        self.add_subscription(src_module, msg)

    def pause_subscription(self, src_module: RTMA_Module, msg: RTMA_MESSAGE):
        self.remove_subscription(src_module, msg)

    def read_message(self, sock: socket.socket) -> RTMA_MESSAGE:
        # Read RTMA Header Section
        hdr_size = rtma.constants["HEADER_SIZE"]
        nbytes = sock.recv_into(self.recv_buffer, self.header_size, socket.MSG_WAITALL)
        msg = RTMA_MESSAGE.from_buffer(self.recv_buffer)

        # Read Data Section
        if msg.num_data_bytes > 0:
            nbytes = sock.recv_into(
                msg.data, msg.header.num_data_bytes, socket.MSG_WAITALL
            )

        return msg

    def forward_message(self, msg: RTMA_MESSAGE, wlist: List[socket.socket]):
        """ Forward a message from other modules
        The given message will be forwarded to:
            - all subscribed logger modules (ALWAYS)
            - if the message has a destination address, and it is subscribed to by that destination it will be forwarded only there
            - if the message has no destination address, it will be forwarded to all subscribed modules
        """

        dest_mod_id = msg.header.dest_mod_id
        dest_host_id = msg.header.dest_host_id

        # Verify that the module & host ids are valid
        if dest_mod_id < 0 or dest_mod_id > rtma.constants["MAX_MODULES"]:
            self.logger.error(
                f"MessageManager::forward_message: Got invalid dest_mod_id [{dest_mod_id}]"
            )

        if dest_host_id < 0 or dest_host_id > rtma.constants["MAX_HOSTS"]:
            self.logger.error(
                f"MessageManager::forward_message: Got invalid dest_host_id [{dest_host_id}]"
            )

        # Always forward to logger modules
        for module in self.logger_modules:
            if module.conn not in wlist:
                # Block until logger is ready
                select.select([], [module.conn], [], None)
            module.send_message(msg)

        # Subscriber set for this message type
        subscribers = self.subscriptions[msg.header.msg_type]

        # Send to a specific destination if it is subscribed
        if dest_mod_id > 0:
            for module in subscribers:
                if module.id == dest_mod_id:
                    if module.conn in wlist:
                        module.send_message(msg)
                        return
                    else:
                        print("x", end="")
                        return

        # Send to all subscribed modules
        for module in subscribers:
            if module.id == msg.header.dest_mod_id:
                if module.conn in wlist:
                    module.send_message(msg)
                else:
                    print("x", end="")

    def process_message(
        self, src_module: RTMA_Module, msg: RTMA_MESSAGE, wlist: List[socket.socket]
    ):
        msg_name = rtma.MT_BY_ID.get(msg.header.msg_type)

        if msg_name == "CONNECT":
            self.connect_module(src_module, msg)
            self.logger.info(f"CONNECT - {src_module!s}")
        elif msg_name == "DISCONNECT":
            self.disconnect_module(src_module)
            self.logger.info(f"DISCONNECT - {src_module!s}")
        elif msg_name == "SUBSCRIBE":
            self.add_subscription(src_module, msg)
            self.logger.info(f"SUBSCRIBE- {src_module!s} to {msg.msg_name}")
        elif msg_name == "UNSUBSCRIBE":
            self.remove_subscription(src_module, msg)
            self.logger.info(f"UNSUBSCRIBE - {src_module!s} from {msg.msg_name}")
        elif msg_name == "PAUSE_SUBSCRIPTION":
            self.logger.info(f"PAUSE_SUBSCRIPTION - {src_module!s} to {msg.msg_name}")
            self.pause_subscription(src_module, msg)
        elif msg_name == "RESUME_SUBSCRIPTION":
            self.resume_subscription(src_module, msg)
            self.logger.info(f"RESUME_SUBSCRIPTION - {src_module!s} to {msg.msg_name}")
        else:
            self.logger.info(f"FORWARD - {msg.msg_name} from {src_module!s}")
            self.forward_message(msg, wlist)

    def run(self):
        while True:
            try:
                rlist, wlist, xlist = select.select(
                    self.modules.keys(), self.modules.keys(), [], self.timeout
                )

                # Check for an incoming connection request
                try:
                    listen_socket = rlist.remove(self.listen_socket)
                    (conn, address) = listen_socket.accept()
                    self.logger.info(
                        f"New connection accpeted from {address[0]}:{address[1]}"
                    )
                    self.sockets.append(conn)
                    self.modules[conn] = RTMA_Module(conn, address)
                except ValueError:
                    pass

                # Randomly select the order of sockets with data.
                random.shuffle(rlist)

                # Read the incoming messages, process, and distribute
                for client_socket in rlist:
                    msg = self.read_message(client_socket)
                    src = self.modules[client_socket]
                    self.process_message(src, msg, wlist)
            except KeyboardInterrupt:
                self.logger.info("Stopping Message Mangger")
                break
            finally:
                for mod in self.modules:
                    mod.close()


if __name__ == "__main__":

    msg_mgr = MessageManager("127.0.0.1", 7111, debug=True)

    msg_mgr.run()
