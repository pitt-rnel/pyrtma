import logging
import select
import errno
import struct
import argparse
import importlib
import pathlib
import sys
import json
import time
from rich.logging import RichHandler

from pyrtma import Client, Message, MessageHeader, get_msg_cls
from pyrtma.exceptions import RTMAMessageError
import pyrtma.core_defs as cd

from socket import error as SocketError
from socketserver import TCPServer
from websocket_server import (  # type: ignore
    WebsocketServer,
    WebSocketHandler,
    logger,
    OPCODE,
    MASKED,
    FIN,
    PAYLOAD_LEN,
    OPCODE_CLOSE_CONN,
    OPCODE_BINARY,
    OPCODE_CONTINUATION,
    OPCODE_PING,
    OPCODE_PONG,
    OPCODE_TEXT,
)

from typing import Optional, List, Callable, Any, Dict, cast

# use rich logging
logging.getLogger().removeHandler(logging.getLogger().handlers[0])
logging.getLogger().addHandler(RichHandler())


class RTMAWebSocketHandler(WebSocketHandler):
    """RTMA Web Socket Handler class"""

    disable_nagle_algorithm = True

    def __init__(self, socket, addr, server):
        """RTMA Web Socket Handler

        Initializes and handles RTMA Proxy connection

        Args:
            socket: socket object
            addr: client address
            server: server object
        """
        # Initialize RTMA Proxy connection
        self.mm_ip = server.mm_ip
        self.proxy = Client()

        WebSocketHandler.__init__(self, socket, addr, server)

    def handle(self):
        """Handle RTMA proxy connection"""
        if not self.handshake_done:
            self.handshake()

        if not self.valid_client:
            logger.error("Websocket handshake failed.")
            return

        # Establish the underlying socket connection with MessageManger Server
        self.proxy._socket_connect(self.mm_ip)

        log_str = (
            "New Client:\n"
            + f"ws: {self.request.getsockname()[0]}:{self.request.getsockname()[1]} -> {self.request.getpeername()[0]}:{self.request.getpeername()[1]}\n"
            + f"rtma: {self.proxy.sock.getsockname()[0]}:{self.proxy.sock.getsockname()[1]} -> {self.proxy.sock.getpeername()[0]}:{self.proxy.sock.getpeername()[1]}\n"
        )
        logger.info(log_str)

        # Message Loop
        while self.keep_alive and self.proxy.connected:
            rd, _, _ = select.select([self.rfile, self.proxy.sock], [], [], 0.100)

            if self.rfile in rd:
                self.read_ws_message()

            if self.proxy.sock in rd and self.proxy.connected:
                try:
                    msg = self.proxy.read_message(timeout=None, ack=True)
                except RTMAMessageError as e:
                    error_json = json.dumps(
                        {"rtma_msg_error": str(e)}, separators=(",", ":")
                    )
                    self.send_message(error_json)
                    logger.error(e, stack_info=False)
                    continue

                if msg is not None:
                    # Pass message thru websocket as json
                    _, wd, _ = select.select([], [self.wfile], [], 0)
                    if self.wfile in wd:
                        logger.debug(
                            f"Forwarding message type {get_msg_cls(msg.header.msg_type).type_name} to ws"
                        )
                        self.send_message(msg.to_json(minify=True))
                    else:
                        self.send_failed_message(msg.header, time.perf_counter())
                        logger.warning(
                            f"Failed to foward message type {get_msg_cls(msg.header.msg_type).type_name} to ws. Mod ID = {self.proxy.module_id}"
                        )

    def pong_received(self, msg: str):
        """Log that pong was received

        Args:
            msg (str): Ignored
        """
        logger.info("Websocket PONG received.")

    def handle_connect(self, msg: Message):
        logger.debug("Received CONNECT")

        # self.proxy._module_id = msg.header.src_mod_id
        # self.proxy._host_id = msg.header.src_host_id
        msg.data = cast(cd.MDF_CONNECT, msg.data)
        ack_msg = self.proxy._connect_helper(
            bool(msg.data.logger_status), bool(msg.data.daemon_status)
        )
        # forward ack
        # Pass message thru websocket as json
        _, wd, _ = select.select([], [self.wfile], [], 0)
        if self.wfile in wd:
            logger.debug(
                f"Forwarding ACK from connect to ws. Mod ID = {self.proxy.module_id}"
            )
            self.send_message(ack_msg.to_json(minify=True))
        else:
            self.send_failed_message(ack_msg.header, time.perf_counter())
            logger.warning(
                f"Failed to foward ACK to ws. Mod ID = {self.proxy.module_id}."
            )

    def process_json_message(self, message: str):
        """Process incoming json message

        Called when a client receives a message over websocket

        Args:
            message (str): JSON message string
        """
        if message == "PING":
            self.send_message("PONG")
            return

        try:
            msg = Message.from_json(message)

            if msg.header.msg_type == cd.MT_DISCONNECT:
                self.proxy.disconnect()
                logger.info("Received disconnect, disconnected proxy from MM.")
            elif msg.header.msg_type == cd.MT_SUBSCRIBE:
                msg.data = cast(cd.MDF_SUBSCRIBE, msg.data)
                self.proxy.subscribe([msg.data.msg_type])
                logger.info(
                    f"Received SUBSCRIBE: {get_msg_cls(msg.data.msg_type).type_name}"
                )
            elif msg.header.msg_type == cd.MT_UNSUBSCRIBE:
                msg.data = cast(cd.MDF_UNSUBSCRIBE, msg.data)
                self.proxy.unsubscribe([msg.data.msg_type])
                logger.info(
                    f"Received UNSUBSCRIBE: {get_msg_cls(msg.data.msg_type).type_name}"
                )
            elif msg.header.msg_type == cd.MT_PAUSE_SUBSCRIPTION:
                msg.data = cast(cd.MDF_PAUSE_SUBSCRIPTION, msg.data)
                self.proxy.pause_subscription([msg.data.msg_type])
                logger.info(
                    f"Received PAUSE_SUBSCRIPTION: {get_msg_cls(msg.data.msg_type).type_name}"
                )
            elif msg.header.msg_type == cd.MT_RESUME_SUBSCRIPTION:
                msg.data = cast(cd.MDF_RESUME_SUBSCRIPTION, msg.data)
                self.proxy.resume_subscription([msg.data.msg_type])
                logger.info(
                    f"Received RESUME_SUBSCRIPTION: {get_msg_cls(msg.data.msg_type).type_name}"
                )
            elif msg.header.msg_type == cd.MT_CONNECT:
                self.handle_connect(msg)
                logger.info(
                    f"Proxy CONNECTED, assigned module ID {self.proxy.module_id}"
                )
            else:
                self.proxy.forward_message(msg.header, msg.data or None)
                logger.debug(
                    f"Forwarded message type {get_msg_cls(msg.header.msg_type).type_name} from ws"
                )
        except RTMAMessageError as e:
            error_json = json.dumps({"rtma_msg_error": str(e)}, separators=(",", ":"))
            self.send_message(error_json)
            logger.error(e, stack_info=False)
            return

    def read_ws_message(self) -> Optional[str]:
        """Read websocket message

        Returns:
            Optional[str]: Websocket message string
        """
        try:
            b1, b2 = self.read_bytes(2)
        except SocketError as e:  # to be replaced with ConnectionResetError for py3
            if e.errno == errno.ECONNRESET:
                logger.info("Client closed connection.")
                self.keep_alive = 0
                return None
            b1, b2 = 0, 0
        except ValueError as e:
            b1, b2 = 0, 0

        fin = b1 & FIN
        opcode = b1 & OPCODE
        masked = b2 & MASKED
        payload_length = b2 & PAYLOAD_LEN
        opcode_handler: Callable[[str], None]

        if opcode == OPCODE_CLOSE_CONN:
            logger.info("Client asked to close connection.")
            self.keep_alive = 0
            return None
        if not masked:
            logger.warning("Client must always be masked.")
            self.keep_alive = 0
            return None
        if opcode == OPCODE_CONTINUATION:
            logger.warning("Continuation frames are not supported.")
            return None
        elif opcode == OPCODE_BINARY:
            logger.warning("Binary frames are not supported.")
            return None
        elif opcode == OPCODE_TEXT:
            opcode_handler = self.process_json_message
        elif opcode == OPCODE_PING:
            opcode_handler = self.send_pong
        elif opcode == OPCODE_PONG:
            opcode_handler = self.pong_received
        else:
            logger.warning("Unknown opcode %#x." % opcode)
            self.keep_alive = 0
            return None

        if payload_length == 126:
            payload_length = struct.unpack(">H", self.rfile.read(2))[0]
        elif payload_length == 127:
            payload_length = struct.unpack(">Q", self.rfile.read(8))[0]

        masks = self.read_bytes(4)
        message_bytes = bytearray()
        for message_byte in self.read_bytes(payload_length):
            message_byte ^= masks[len(message_bytes) % 4]
            message_bytes.append(message_byte)

        opcode_handler(message_bytes.decode("utf8"))
        return message_bytes.decode("utf8")

    def send_failed_message(self, header: MessageHeader, time_of_failure: float):
        """Send FAILED_MESSAGE when we cannot forward to websocket"""
        data = cd.MDF_FAILED_MESSAGE()
        data.dest_mod_id = self.proxy.module_id
        data.time_of_failure = time_of_failure

        # Copy the values into the RTMA_MSG_HEADER
        for fname, ftype in data.msg_header._fields_:
            setattr(data.msg_header, fname, getattr(header, fname))

        if (
            data.msg_header.msg_type == cd.MT_FAILED_MESSAGE
        ):  # avoid unlikely infinite recursion
            return

        self.proxy.send_message(data)

    def finish(self):
        """Close RTMA connection"""
        # Disconnect on behalf of the web client if still connected here
        if self.proxy.connected:
            self.proxy.disconnect()
            logger.debug("Disconnected proxy from MM.")

        super().finish()


class WebMessageManager(WebsocketServer):
    """WebMessageManager class"""

    def __init__(
        self,
        host="",
        port=0,
        mm_ip: str = "127.0.0.1:7111",
        loglevel: int = logging.WARNING,
        key=None,
        cert=None,
    ):
        """WebMessageManager class

        Args:
            host (str, optional): IP for WebMessageManager to listen for connections. Defaults to "" (any local IP).
            port (int, optional): Port for WebMessageManager to bind to. Defaults to 0.
            mm_ip (str, optional): Address for RTMA MessageManager. Defaults to "127.0.0.1:7111".
            loglevel (int, optional): Loging level. Defaults to logging.WARNING.
            key (optional): Path to SSL key. Defaults to None.
            cert (optional): Path to SSL cert. Defaults to None.
        """

        logger.setLevel(loglevel)
        TCPServer.__init__(self, (host, port), RTMAWebSocketHandler)
        self.host = host
        self.port = self.socket.getsockname()[1]

        self.key = key
        self.cert = cert

        self.clients: List[dict] = []
        self.id_counter = 0
        self.thread = None

        self._deny_clients = False

        self.set_fn_new_client(ws_client_connect)
        self.set_fn_client_left(ws_client_disconnect)

        self.mm_ip = mm_ip


def ws_client_connect(client: Dict[str, Any], server: WebMessageManager):
    """Websocket client connect

        Called for every client connecting (after handshake)
    Args:
        client (Dict[str, Any]): Client dictionary
        server: WebMessageManager Server object
    """
    logger.info(f"Client connected -> id: {client['id']}")


def ws_client_disconnect(client: Dict[str, Any], server: WebMessageManager):
    """Websocket client disconnect

        Called for every client disconnecting
    Args:
        client (Dict[str, Any]): Client dictionary
        server: WebMessageManager Server object
    """
    logger.info(f"Client disconnected -> id: {client['id']}\n")


def main():
    """Main function for starting web_manager"""

    parser = argparse.ArgumentParser(description="Websocket Message Manager")

    parser.add_argument(
        "-m",
        "--mm-ip",
        default="127.0.0.1:7111",
        dest="mm_ip",
        type=str,
        help="IP address of Message Manager. Defaults to 127.0.0.1:7111.",
    )

    parser.add_argument(
        "--host",
        default="",
        dest="host",
        type=str,
        help='Host IP address, defaults to "" (any local IP).',
    )

    parser.add_argument(
        "-p",
        "--port",
        default=5678,
        dest="port",
        type=int,
        help="Port to listen for websocket clients. Defaults to 5678.",
    )

    parser.add_argument(
        "-d",
        "--defs",
        dest="defs_file",
        type=str,
        help="Path to python message definitions file. Required argument.",
    )

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    args = parser.parse_args()

    websocket_server = WebMessageManager(
        host=args.host,
        port=args.port,
        loglevel=logging.INFO,
        mm_ip=args.mm_ip,
    )

    base = pathlib.Path(args.defs_file).absolute().parent
    fname = pathlib.Path(args.defs_file).stem

    sys.path.insert(0, (str(base.absolute())))
    importlib.import_module(fname)

    websocket_server.run_forever()


if __name__ == "__main__":
    main()
