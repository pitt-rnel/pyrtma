import pyrtma
import logging
import select
import errno
import struct
import argparse
import importlib
import pathlib
import sys

from pyrtma.client import Client
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

from typing import Optional, List, Callable, Any, Dict


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

        print("New Client:")
        print(
            f"ws:{self.request.getsockname()[0]}:{self.request.getsockname()[1]} -> {self.request.getpeername()[0]}:{self.request.getpeername()[1]}"
        )

        print(
            f"rtma:{self.proxy.sock.getsockname()[0]}:{self.proxy.sock.getsockname()[1]} -> {self.proxy.sock.getpeername()[0]}:{self.proxy.sock.getpeername()[1]}"
        )
        print()

        # Message Loop
        while self.keep_alive and self.proxy.connected:
            rd, _, _ = select.select([self.rfile, self.proxy.sock], [], [], 0.100)

            if self.rfile in rd:
                self.read_ws_message()

            if self.proxy.sock in rd:
                try:
                    msg = self.proxy.read_message(timeout=None)
                except RTMAMessageError as e:
                    logger.error(e, stack_info=False)
                    break

                if msg is not None:
                    # Pass message thru websocket as json
                    _, wd, _ = select.select([], [self.rfile], [], 0)
                    if self.rfile in wd:
                        self.send_message(msg.to_json())
                    else:
                        print("X")

    def pong_received(self, msg: str):
        """Log that pong was received

        Args:
            msg (str): Ignored
        """
        logger.info("Websocket PONG received.")

    def process_json_message(self, message: str):
        """Process incoming json message

        Called when a client receives a message over websocket

        Args:
            message (str): JSON message string
        """
        try:
            msg = pyrtma.Message.from_json(message)
        except RTMAMessageError as e:
            logger.error(e, stack_info=False)
            return

        self.proxy.forward_message(msg.header, msg.data or None)

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
    print(f"Client connected -> id:{client['id']}")


def ws_client_disconnect(client: Dict[str, Any], server: WebMessageManager):
    """Websocket client disconnect

        Called for every client disconnecting
    Args:
        client (Dict[str, Any]): Client dictionary
        server: WebMessageManager Server object
    """
    print(f"Client disconnected -> id:{client['id']}")


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
        loglevel=logging.DEBUG,
        mm_ip=args.mm_ip,
    )

    base = pathlib.Path(args.defs_file).absolute().parent
    fname = pathlib.Path(args.defs_file).stem

    sys.path.insert(0, (str(base.absolute())))
    importlib.import_module(fname)

    websocket_server.run_forever()


if __name__ == "__main__":
    main()
