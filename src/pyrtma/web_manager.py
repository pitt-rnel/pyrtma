import logging
import select
import errno
import struct
import argparse
import os
import sys
import json
import time
import socket
import pyrtma.core_defs as cd
from rich.logging import RichHandler

from pyrtma import (
    Client,
    Message,
    MessageHeader,
    ClientError,
    MessageDefinitions,
    load_message_definitions,
)
from pyrtma.exceptions import RTMAMessageError

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

from typing import Callable, Any, Sequence, cast


class RTMAWebSocketHandler(WebSocketHandler):
    """RTMA Web Socket Handler class"""

    disable_nagle_algorithm = True

    #: Whether the proxy has connected to the message manager for the web
    #: client. Set by the web client's first CONNECT or CONNECT_V2.
    rtma_connected: bool = False

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
        self.proxy = Client(definitions=server.definitions)
        # The proxy's records propagate to the root logger, which main() gives
        # a console handler, so its own console handler would print each of
        # them a second time.
        self.proxy.logger.enable_console = False

        WebSocketHandler.__init__(self, socket, addr, server)

    @property
    def ws_ready_to_send(self):
        if self.keep_alive:
            _, wd, _ = select.select([], [self.wfile], [], 0)
            return self.wfile in wd
        else:
            return False

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
                self.read_proxy_message()

    def read_proxy_message(self) -> None:
        """Pass a message from the message manager on to the websocket.

        Called when the proxy's socket is readable. The read doesn't wait for
        a further message, so a message the proxy is no longer subscribed to,
        which is dropped, doesn't hold up input from the websocket.
        """
        try:
            msg = self.proxy.read_message(timeout=0, ack=True)
        except RTMAMessageError as e:
            error_json = json.dumps({"rtma_msg_error": str(e)}, separators=(",", ":"))
            if self.ws_ready_to_send:
                self.send_message(error_json)
            logger.error(e, stack_info=False)
            return

        if msg is not None and self.keep_alive:
            # Pass message thru websocket as json
            if self.ws_ready_to_send:
                logger.debug(
                    f"Forwarding message type {self.proxy.get_msg_cls(msg.header.msg_type).type_name} to ws"
                )
                self.send_message(msg.to_json(minify=True))
            else:
                if self.proxy.connected:
                    self.send_failed_message(msg.header, time.perf_counter())
                logger.warning(
                    f"Failed to foward message type {self.proxy.get_msg_cls(msg.header.msg_type).type_name} to ws. Mod ID = {self.proxy.module_id}"
                )

    def pong_received(self, msg: str):
        """Log that pong was received

        Args:
            msg (str): Ignored
        """
        logger.info("Websocket PONG received.")

    def _connect_proxy(self, logger_status: bool, requested_id: int) -> None:
        """Connect the proxy to the message manager and pass the ACK on.

        The proxy always takes a dynamic module ID. A web client's request
        for a static ID is logged and ignored: a page that closes without
        closing its websocket would hold the ID until the connection timed
        out, so a reloaded page would be refused.

        Args:
            logger_status: Whether the web client connects as a logger.
            requested_id: The module ID the web client asked for, or 0.

        Raises:
            ClientError: The connection failed, for example
                ``AcknowledgementTimeout``.
        """
        if requested_id != 0:
            logger.warning(
                f"Web client asked for module ID {requested_id}; the web manager assigns dynamic IDs only."
            )
        ack_msg = self.proxy._connect_helper(logger_status)
        self.rtma_connected = True
        logger.info(f"Proxy CONNECTED, assigned module ID {self.proxy.module_id}")

        # forward ack
        # Pass message thru websocket as json
        if self.ws_ready_to_send:
            logger.debug(
                f"Forwarding ACK from connect to ws. Mod ID = {self.proxy.module_id}"
            )
            self.send_message(ack_msg.to_json(minify=True))
        else:
            self.send_failed_message(ack_msg.header, time.perf_counter())
            logger.warning(
                f"Failed to foward ACK to ws. Mod ID = {self.proxy.module_id}."
            )

    def handle_connect(self, msg: Message) -> None:
        """Connect the proxy for a web client's CONNECT.

        CONNECT asks for a module ID in its header. A CONNECT after the
        web client has connected carries nothing new and is ignored, as the
        message manager ignores it.

        Args:
            msg: The web client's CONNECT.

        Raises:
            ClientError: The connection failed.
        """
        logger.debug("Received CONNECT")
        data = cast(cd.MDF_CONNECT, msg.data)
        if self.rtma_connected:
            logger.debug("Ignoring CONNECT from a web client that has connected.")
            return
        self._connect_proxy(bool(data.logger_status), msg.header.src_mod_id)

    def handle_connect_v2(self, msg: Message) -> None:
        """Connect the proxy for a web client's CONNECT_V2.

        The web client's name becomes the proxy's. A CONNECT_V2 after the web
        client has connected, such as one that follows its CONNECT, is passed
        on to update the name, without waiting for an ACK and without
        sending the web client a second one, as the message manager does.

        Args:
            msg: The web client's CONNECT_V2.

        Raises:
            ClientError: The connection failed.
        """
        logger.debug("Received CONNECT_V2")
        data = cast(cd.MDF_CONNECT_V2, msg.data)
        self.proxy._name = data.name
        if not self.rtma_connected:
            self._connect_proxy(bool(data.logger_status), data.mod_id)
            return

        self.proxy.logger.log_name = data.name or f"Module {self.proxy.module_id}"
        update = cd.MDF_CONNECT_V2()
        update.logger_status = data.logger_status
        update.pid = os.getpid()
        update.mod_id = self.proxy.module_id
        update.name = data.name
        self.proxy.send_message(update)
        logger.info(f"Proxy name updated to {data.name!r}")

    def process_json_message(self, message: str):
        """Process incoming json message

        Called when a client receives a message over websocket

        Args:
            message (str): JSON message string
        """
        if message == "PING" and self.ws_ready_to_send:
            self.send_message("PONG")
            return

        try:
            msg = Message.from_json(message, self.proxy.definitions)

            if msg.header.msg_type == cd.MT_DISCONNECT:
                self.proxy.disconnect()
                logger.info("Received disconnect, disconnected proxy from MM.")
            elif msg.header.msg_type == cd.MT_SUBSCRIBE:
                msg.data = cast(cd.MDF_SUBSCRIBE, msg.data)
                self.proxy.subscribe([msg.data.msg_type])
                logger.info(
                    f"Received SUBSCRIBE: {self.proxy.get_msg_cls(msg.data.msg_type).type_name}"
                )
            elif msg.header.msg_type == cd.MT_UNSUBSCRIBE:
                msg.data = cast(cd.MDF_UNSUBSCRIBE, msg.data)
                self.proxy.unsubscribe([msg.data.msg_type])
                logger.info(
                    f"Received UNSUBSCRIBE: {self.proxy.get_msg_cls(msg.data.msg_type).type_name}"
                )
            elif msg.header.msg_type == cd.MT_PAUSE_SUBSCRIPTION:
                msg.data = cast(cd.MDF_PAUSE_SUBSCRIPTION, msg.data)
                self.proxy.pause_subscription([msg.data.msg_type])
                logger.info(
                    f"Received PAUSE_SUBSCRIPTION: {self.proxy.get_msg_cls(msg.data.msg_type).type_name}"
                )
            elif msg.header.msg_type == cd.MT_RESUME_SUBSCRIPTION:
                msg.data = cast(cd.MDF_RESUME_SUBSCRIPTION, msg.data)
                self.proxy.resume_subscription([msg.data.msg_type])
                logger.info(
                    f"Received RESUME_SUBSCRIPTION: {self.proxy.get_msg_cls(msg.data.msg_type).type_name}"
                )
            elif msg.header.msg_type == cd.MT_CONNECT:
                self.handle_connect(msg)
            elif msg.header.msg_type == cd.MT_CONNECT_V2:
                self.handle_connect_v2(msg)
            else:
                self.proxy.forward_message(msg.header, msg.data or None)
                logger.debug(
                    f"Forwarded message type {self.proxy.get_msg_cls(msg.header.msg_type).type_name} from ws"
                )
        except (RTMAMessageError, ClientError) as e:
            if self.ws_ready_to_send:
                error_json = json.dumps(
                    {"rtma_msg_error": str(e)}, separators=(",", ":")
                )
                self.send_message(error_json)
            logger.error(e, stack_info=False)
            return

    def read_ws_message(self) -> str | None:
        """Read websocket message

        Returns:
            str | None: Websocket message string
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
        for fname, ftype, *_ in data.msg_header._fields_:
            setattr(data.msg_header, fname, getattr(header, fname))

        if (
            data.msg_header.msg_type == cd.MT_FAILED_MESSAGE
        ):  # avoid unlikely infinite recursion
            return
        if self.proxy.connected:
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
        definitions: MessageDefinitions | None = None,
    ):
        """WebMessageManager class

        Args:
            host (str, optional): IP for WebMessageManager to listen for connections. Defaults to "" (any local IP).
            port (int, optional): Port for WebMessageManager to bind to. Defaults to 0.
            mm_ip (str, optional): Address for RTMA MessageManager. Defaults to "127.0.0.1:7111".
            loglevel (int, optional): Loging level. Defaults to logging.WARNING.
            key (optional): Path to SSL key. Defaults to None.
            cert (optional): Path to SSL cert. Defaults to None.
            definitions (MessageDefinitions | None, optional): MessageDefinitions object. Defaults to None.
        """
        self.definitions = definitions

        logger.setLevel(loglevel)
        TCPServer.__init__(self, (host, port), RTMAWebSocketHandler)
        self.host = host
        self.port = self.socket.getsockname()[1]

        if self.host not in ("", "0.0.0.0"):
            logger.info(f"WebMessageManager listening on {self.host}:{self.port}")
        else:
            hosts = socket.gethostbyname_ex(socket.gethostname())[-1]
            if "127.0.0.1" not in hosts:
                hosts.append("127.0.0.1")
            logger.info(
                f"WebMessageManager listening on all interfaces, port {self.port}"
            )
            logger.info(f"IP addresses: {hosts}")

        self.key = key
        self.cert = cert

        self.clients: list[dict] = []
        self.id_counter = 0
        self.thread = None

        self._deny_clients = False

        self.set_fn_new_client(ws_client_connect)
        self.set_fn_client_left(ws_client_disconnect)

        self.mm_ip = mm_ip


def ws_client_connect(client: dict[str, Any], server: WebMessageManager):
    """Websocket client connect

    Called for every client connecting (after handshake)

    Args:
        client (dict[str, Any]): Client dictionary
        server: WebMessageManager Server object
    """
    try:
        logger.info(f"Client connected -> id: {client['id']}")
    except:
        pass


def ws_client_disconnect(client: dict[str, Any], server: WebMessageManager):
    """Websocket client disconnect

    Called for every client disconnecting

    Args:
        client (dict[str, Any]): Client dictionary
        server: WebMessageManager Server object
    """
    try:
        logger.info(f"Client disconnected -> id: {client['id']}")
    except:
        pass


def configure_logging(root: logging.Logger | None = None) -> None:
    """Send log records to the console through rich.

    Called by :func:`main` rather than at import, so importing this module
    leaves an application's logging alone. Any existing handlers, such as
    the one ``websocket_server`` adds with ``logging.basicConfig()`` when it
    is imported, are removed and closed.

    Args:
        root: The logger to configure, for tests. Defaults to the root logger.
    """
    if root is None:
        root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    root.addHandler(RichHandler())


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse the command line.

    Args:
        argv: The arguments, without the program name. Defaults to
            ``sys.argv[1:]``.

    Returns:
        The options.
    """
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
        "-a",
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
        required=True,
        help="Path to python message definitions file. Required argument.",
    )

    if argv is None:
        argv = sys.argv[1:]
    if len(argv) == 0:
        parser.print_help(sys.stderr)
        sys.exit(1)
    return parser.parse_args(argv)


def run(args: argparse.Namespace) -> None:
    """Load the definitions and serve websocket clients until stopped.

    Args:
        args: Options from :func:`parse_args`.

    Raises:
        MessageDefinitionsLoadError: The definitions file can't be loaded.
    """
    defs = load_message_definitions(args.defs_file)

    websocket_server = WebMessageManager(
        host=args.host,
        port=args.port,
        loglevel=logging.INFO,
        mm_ip=args.mm_ip,
        definitions=defs,
    )

    websocket_server.run_forever()


def main(argv: Sequence[str] | None = None) -> None:
    """Main function for starting web_manager

    Args:
        argv: The arguments, without the program name. Defaults to
            ``sys.argv[1:]``.
    """
    args = parse_args(argv)
    configure_logging()
    run(args)


if __name__ == "__main__":
    main()
