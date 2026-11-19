"""Websocket server that connects web clients, such as rtma-js, to a message manager.

Each web client gets a proxy: a pyrtma :py:class:`~pyrtma.client.Client`
connected to the message manager on its behalf. The web client sends and
receives messages as JSON text, ``{"header": {...}, "data": {...}}``, and the
text messages ``PING`` and ``PONG`` are a keepalive.

The websocket side is the ``websockets`` library's threading server: each web
client is served in a thread of its own, which reads the websocket, and a
second thread for the web client forwards messages from the message manager.
"""

import argparse
import json
import logging
import os
import select
import socket
import ssl
import sys
import threading
import time

import pyrtma.core_defs as cd
from rich.logging import RichHandler
from websockets.exceptions import ConnectionClosed
from websockets.protocol import State
from websockets.sync.server import Server, ServerConnection, serve

from pyrtma import (
    Client,
    Message,
    ClientError,
    MessageDefinitions,
    load_message_definitions,
)
from pyrtma.exceptions import RTMAMessageError
from pyrtma.header import MessageHeader

from collections.abc import Sequence
from typing import Any, cast

logger = logging.getLogger(__name__)

#: The longest message a web client may send, as JSON text, in bytes. A
#: message's data can be up to ``MAX_DATA_BYTES``, and its JSON is longer:
#: an ``int8`` of -128, one byte, takes five characters with its comma.
MAX_JSON_BYTES = 8 * cd.MAX_DATA_BYTES

#: Seconds to wait for the web client's CLOSE after sending ours.
CLOSE_TIMEOUT = 1.0


class RTMAWebSocketHandler:
    """Relays messages between one web client's websocket and its proxy.

    :py:meth:`handle` runs in the websocket's thread and passes the web
    client's messages to the proxy. Once the proxy has connected, a reader
    thread passes messages from the message manager to the web client.
    """

    #: Seconds the reader waits for each message from the message manager:
    #: the longest it takes to see that it should stop.
    read_timeout: float = 0.1

    def __init__(self, connection: ServerConnection | None, server: Any) -> None:
        """Set up the proxy for a web client.

        Args:
            connection: The web client's websocket, or None in tests.
            server: The :py:class:`WebMessageManager`, for its ``mm_ip`` and
                ``definitions``.
        """
        self.connection = connection
        self.mm_ip: str = server.mm_ip
        self.proxy = Client(definitions=server.definitions)
        # The proxy's records propagate to the root logger, which main() gives
        # a console handler, so its own console handler would print each of
        # them a second time.
        self.proxy.logger.enable_console = False

        #: Whether the proxy has connected to the message manager for the web
        #: client. Set by the web client's first CONNECT or CONNECT_V2.
        self.rtma_connected = False

        #: Held for everything sent to the message manager. Both threads
        #: send, the reader only FAILED_MESSAGE, and a Client can't send for
        #: two threads at once. Reentrant, since a send made with it held can
        #: lead to FAILED_MESSAGE.
        self.proxy_lock = threading.RLock()

        self._stop_reading = threading.Event()
        self._reader: threading.Thread | None = None

    @property
    def ws_ready_to_send(self) -> bool:
        """Whether a message can be sent to the web client without waiting.

        A web client that can't keep up misses messages, each reported to
        the message manager with FAILED_MESSAGE, rather than holding up the
        messages for it.
        """
        if self.connection is None or self.connection.state is not State.OPEN:
            return False
        _, writable, _ = select.select([], [self.connection.socket], [], 0)
        return bool(writable)

    def send_message(self, message: str) -> None:
        """Send text to the web client.

        A websocket that has closed meanwhile is left alone: its thread is
        ending.

        Args:
            message: The text.
        """
        if self.connection is None:
            return
        try:
            self.connection.send(message)
        except ConnectionClosed:
            pass

    def handle(self) -> None:
        """Serve the web client until its websocket or its proxy closes."""
        assert self.connection is not None
        try:
            self.proxy._socket_connect(self.mm_ip)
        except ClientError as e:
            # Tell the web client why, rather than only closing the websocket.
            self.send_ws_error(e)
            self.connection.close()
            return

        local, remote = self.connection.local_address, self.connection.remote_address
        proxy_local, proxy_remote = (
            self.proxy.sock.getsockname(),
            self.proxy.sock.getpeername(),
        )
        logger.info(
            "New Client:\n"
            f"ws: {local[0]}:{local[1]} -> {remote[0]}:{remote[1]}\n"
            f"rtma: {proxy_local[0]}:{proxy_local[1]} -> {proxy_remote[0]}:{proxy_remote[1]}\n"
        )

        try:
            for message in self.connection:
                if isinstance(message, bytes):
                    logger.warning("Binary frames are not supported.")
                    continue
                self.process_json_message(message)
                # After DISCONNECT, or when the proxy's connection failed.
                if not self.proxy.connected:
                    break
        except ConnectionClosed as e:
            logger.info(f"Websocket closed: {e}")
        finally:
            self.finish()
            # Close with the closing handshake, if the web client hasn't.
            self.connection.close()
            logger.info(f"Client disconnected: {remote[0]}:{remote[1]}")

    def start_reader(self) -> None:
        """Start passing messages from the message manager to the web client."""
        self._stop_reading.clear()
        self._reader = threading.Thread(
            target=self._read_proxy,
            name=f"web_manager reader for module {self.proxy.module_id}",
            daemon=True,
        )
        self._reader.start()

    def stop_reader(self) -> None:
        """Stop the reader, and wait for it to finish its current read."""
        self._stop_reading.set()
        reader = self._reader
        if reader is not None and reader is not threading.current_thread():
            reader.join()

    def _read_proxy(self) -> None:
        """Pass messages from the message manager on until told to stop.

        When the connection to the message manager fails, the websocket is
        closed, which ends :py:meth:`handle` too.
        """
        while not self._stop_reading.is_set() and self.proxy.connected:
            try:
                self.read_proxy_message(self.read_timeout)
            except ClientError as e:
                if self._stop_reading.is_set():
                    return
                logger.warning(f"Lost the connection to the message manager: {e}")
                break
        if not self._stop_reading.is_set() and self.connection is not None:
            self.connection.close()

    def send_ws_error(self, error: Exception) -> None:
        """Send the web client an error, as ``{"rtma_msg_error": ...}``, and log it.

        Args:
            error: The error.
        """
        if self.ws_ready_to_send:
            error_json = json.dumps(
                {"rtma_msg_error": str(error)}, separators=(",", ":")
            )
            self.send_message(error_json)
        logger.error(error, stack_info=False)

    def read_proxy_message(self, timeout: float = 0) -> None:
        """Pass a message from the message manager on to the websocket.

        A message the proxy isn't subscribed to is dropped, and only part of
        a message is kept for the next read, so neither holds the read past
        its timeout.

        Args:
            timeout: Seconds to wait for a message.

        Raises:
            ClientError: The connection to the message manager failed.
        """
        try:
            msg = self.proxy.read_message(timeout=timeout, ack=True)
        except RTMAMessageError as e:
            self.send_ws_error(e)
            return

        if msg is None:
            return
        # Pass message thru websocket as json
        if self.ws_ready_to_send:
            logger.debug(
                f"Forwarding message type {self.proxy.get_msg_cls(msg.header.msg_type).type_name} to ws"
            )
            self.send_message(msg.to_json(minify=True))
        else:
            self.send_failed_message(msg.header, time.perf_counter())
            logger.warning(
                f"Failed to foward message type {self.proxy.get_msg_cls(msg.header.msg_type).type_name} to ws. Mod ID = {self.proxy.module_id}"
            )

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
        self.start_reader()

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
        except RTMAMessageError as e:
            self.send_ws_error(e)
            return
        except (ValueError, KeyError, TypeError) as e:
            # Text that isn't JSON, or JSON that isn't a message.
            self.send_ws_error(
                RTMAMessageError(f"Not a message: {type(e).__name__}: {e}")
            )
            return

        if msg.header.msg_type == cd.MT_DISCONNECT:
            # The reader is stopped first: disconnect() reads the proxy's
            # socket, and the reader may be waiting for proxy_lock.
            self.stop_reader()
            with self.proxy_lock:
                self.proxy.disconnect()
            logger.info("Received disconnect, disconnected proxy from MM.")
            return

        try:
            with self.proxy_lock:
                self.dispatch(msg)
        except (RTMAMessageError, ClientError) as e:
            self.send_ws_error(e)

    def dispatch(self, msg: Message) -> None:
        """Act on a message from the web client, other than DISCONNECT.

        Called with ``proxy_lock`` held.

        Args:
            msg: The message.

        Raises:
            RTMAMessageError: The message can't be sent.
            ClientError: The proxy can't do what the message asks.
        """
        if msg.header.msg_type == cd.MT_SUBSCRIBE:
            msg.data = cast(cd.MDF_SUBSCRIBE, msg.data)
            self.proxy.subscribe([msg.data.msg_type])
            logger.info(f"Received SUBSCRIBE: {self._type_name(msg.data.msg_type)}")
        elif msg.header.msg_type == cd.MT_UNSUBSCRIBE:
            msg.data = cast(cd.MDF_UNSUBSCRIBE, msg.data)
            self.proxy.unsubscribe([msg.data.msg_type])
            logger.info(f"Received UNSUBSCRIBE: {self._type_name(msg.data.msg_type)}")
        elif msg.header.msg_type == cd.MT_PAUSE_SUBSCRIPTION:
            msg.data = cast(cd.MDF_PAUSE_SUBSCRIPTION, msg.data)
            self.proxy.pause_subscription([msg.data.msg_type])
            logger.info(
                f"Received PAUSE_SUBSCRIPTION: {self._type_name(msg.data.msg_type)}"
            )
        elif msg.header.msg_type == cd.MT_RESUME_SUBSCRIPTION:
            msg.data = cast(cd.MDF_RESUME_SUBSCRIPTION, msg.data)
            self.proxy.resume_subscription([msg.data.msg_type])
            logger.info(
                f"Received RESUME_SUBSCRIPTION: {self._type_name(msg.data.msg_type)}"
            )
        elif msg.header.msg_type == cd.MT_CONNECT:
            self.handle_connect(msg)
        elif msg.header.msg_type == cd.MT_CONNECT_V2:
            self.handle_connect_v2(msg)
        elif msg.header.msg_type == cd.MT_MODULE_READY:
            # The message manager gets this process's PID, as it does
            # with the proxy's CONNECT_V2: the proxy holds the web
            # client's connection. The web client's PID is ignored.
            self.proxy.send_module_ready()
            logger.info(
                "Received MODULE_READY, web client PID "
                f"{cast(cd.MDF_MODULE_READY, msg.data).pid}"
            )
        else:
            self.proxy.forward_message(msg.header, msg.data or None)
            logger.debug(
                f"Forwarded message type {self.proxy.get_msg_cls(msg.header.msg_type).type_name} from ws"
            )

    def _type_name(self, msg_type: int) -> str:
        """Name a message type for the log, whether or not it is defined.

        A web client may subscribe to ``ALL_MESSAGE_TYPES``, or to a type
        the proxy has no definition for; looking up its class would raise
        after the subscription had gone through.

        Args:
            msg_type: The type.

        Returns:
            Its name, ``ALL_MESSAGE_TYPES``, or ``MT=`` and the number.
        """
        if msg_type == cd.ALL_MESSAGE_TYPES:
            return "ALL_MESSAGE_TYPES"
        return self.proxy.message_name_from_id(msg_type) or f"MT={msg_type}"

    def send_failed_message(self, header: MessageHeader, time_of_failure: float):
        """Send FAILED_MESSAGE when we cannot forward to websocket"""
        data = cd.MDF_FAILED_MESSAGE()
        data.dest_mod_id = self.proxy.module_id
        data.time_of_failure = time_of_failure

        # The failed message's header, whole: RTMA_MSG_HEADER has the
        # message header's layout.
        data.msg_header = cd.RTMA_MSG_HEADER.from_buffer_copy(header)

        if (
            data.msg_header.msg_type == cd.MT_FAILED_MESSAGE
        ):  # avoid unlikely infinite recursion
            return
        with self.proxy_lock:
            if self.proxy.connected:
                self.proxy.send_message(data)

    def finish(self) -> None:
        """Stop the reader and disconnect the proxy, if it's still connected."""
        self.stop_reader()
        with self.proxy_lock:
            if self.proxy.connected:
                self.proxy.disconnect()
                logger.debug("Disconnected proxy from MM.")


def tls_context(cert: str | None, key: str | None) -> ssl.SSLContext | None:
    """Make the TLS context for serving wss://, from a certificate and key.

    The context is the standard library's default for a server, which
    accepts TLS 1.2 or later.

    Args:
        cert: Path to the certificate chain, in PEM format, which may hold
            the private key too, or None for no TLS.
        key: Path to the private key, in PEM format, if it isn't in the
            cert file.

    Raises:
        ValueError: key without cert, or a certificate or key that can't be
            loaded.

    Returns:
        The context, or None when cert is None.
    """
    if cert is None:
        if key is not None:
            raise ValueError("A TLS key needs a certificate (cert) to go with it.")
        return None
    context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    try:
        context.load_cert_chain(cert, key)
    except (OSError, ssl.SSLError) as e:
        where = cert if key is None else f"{cert} and {key}"
        raise ValueError(
            f"Can't load the TLS certificate and key from {where}: {e}"
        ) from e
    return context


class WebMessageManager:
    """Websocket server that gives each web client a proxy to a message manager."""

    def __init__(
        self,
        host="",
        port=0,
        mm_ip: str = f"{cd.DEFAULT_HOST}:{cd.DEFAULT_PORT}",
        loglevel: int = logging.WARNING,
        key=None,
        cert=None,
        definitions: MessageDefinitions | None = None,
    ):
        """WebMessageManager class

        The server listens from here on, and serves web clients from
        :py:meth:`run_forever`.

        Args:
            host (str, optional): IP for WebMessageManager to listen for connections. Defaults to "" (any local IP).
            port (int, optional): Port for WebMessageManager to bind to. Defaults to 0.
            mm_ip (str, optional): Address for RTMA MessageManager. Defaults to ``DEFAULT_HOST`` on ``DEFAULT_PORT``, "localhost:7111".
            loglevel (int, optional): Loging level. Defaults to logging.WARNING.
            key (optional): Path to the TLS private key, in PEM format, if it isn't in the cert file. Needs cert.
            cert (optional): Path to the TLS certificate chain, in PEM format, which may hold the private key too. With it, the server serves wss:// only. Defaults to None, for ws://.
            definitions (MessageDefinitions | None, optional): MessageDefinitions object. Defaults to None.

        Raises:
            ValueError: key without cert, or a certificate or key that can't
                be loaded.
            OSError: The port can't be listened on.
        """
        self.definitions = definitions
        self.mm_ip = mm_ip

        logger.setLevel(loglevel)
        ssl_context = tls_context(cert, key)
        #: Whether web clients connect with wss://, rather than ws://.
        self.secure = ssl_context is not None

        #: The web clients' websockets, to close at shutdown.
        self.connections: set[ServerConnection] = set()
        self._connections_lock = threading.Lock()

        self.server: Server = serve(
            self._serve_client,
            host,
            port,
            # A web client whose TLS handshake fails, such as a ws:// client,
            # is closed. The handshakes must finish within open_timeout, 10 s
            # by default, so a stalled client doesn't hold its thread.
            ssl=ssl_context,
            max_size=MAX_JSON_BYTES,
            # rtma-js messages are small and frequent: compressing each one
            # would cost more time than it saves.
            compression=None,
            close_timeout=CLOSE_TIMEOUT,
        )
        self.host = host
        self.port: int = self.server.socket.getsockname()[1]

        scheme = "wss" if self.secure else "ws"
        if self.host not in ("", "0.0.0.0"):
            logger.info(
                f"WebMessageManager listening on {self.host}:{self.port}, for {scheme}://"
            )
        else:
            hosts = socket.gethostbyname_ex(socket.gethostname())[-1]
            if "127.0.0.1" not in hosts:
                hosts.append("127.0.0.1")
            logger.info(
                f"WebMessageManager listening on all interfaces, port {self.port}, for {scheme}://"
            )
            logger.info(f"IP addresses: {hosts}")

    def _serve_client(self, connection: ServerConnection) -> None:
        """Serve one web client, in the thread the server gives it.

        Args:
            connection: The web client's websocket.
        """
        with self._connections_lock:
            self.connections.add(connection)
        try:
            RTMAWebSocketHandler(connection, self).handle()
        finally:
            with self._connections_lock:
                self.connections.discard(connection)

    def run_forever(self) -> None:
        """Serve web clients until interrupted, then shut down."""
        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            logger.info("Server terminated.")
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        """Stop listening, and close every web client's websocket.

        Each web client's thread then disconnects its proxy. This may be
        called from another thread, to stop :py:meth:`run_forever`.
        """
        self.server.shutdown()
        with self._connections_lock:
            connections = list(self.connections)
        for connection in connections:
            connection.close(1001, "web manager shutting down")


def configure_logging(root: logging.Logger | None = None) -> None:
    """Send log records to the console through rich.

    Called by :func:`main` rather than at import, so importing this module
    leaves an application's logging alone. Any existing handlers are removed
    and closed.

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
        default=f"{cd.DEFAULT_HOST}:{cd.DEFAULT_PORT}",
        dest="mm_ip",
        type=str,
        help=f"IP address of Message Manager. Defaults to {cd.DEFAULT_HOST}:{cd.DEFAULT_PORT}.",
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
        "--cert",
        dest="cert",
        type=str,
        default=None,
        help="Path to a TLS certificate chain, in PEM format, to serve wss:// in place of ws://. It may hold the private key too.",
    )

    parser.add_argument(
        "--key",
        dest="key",
        type=str,
        default=None,
        help="Path to the TLS private key, in PEM format, if it isn't in the --cert file.",
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
    args = parser.parse_args(argv)
    if args.key is not None and args.cert is None:
        parser.error("--key needs --cert")
    return args


def run(args: argparse.Namespace) -> None:
    """Load the definitions and serve websocket clients until stopped.

    Args:
        args: Options from :func:`parse_args`.

    Raises:
        MessageDefinitionsLoadError: The definitions file can't be loaded.
        ValueError: The TLS certificate or key can't be loaded.
    """
    defs = load_message_definitions(args.defs_file)

    websocket_server = WebMessageManager(
        host=args.host,
        port=args.port,
        loglevel=logging.INFO,
        mm_ip=args.mm_ip,
        key=args.key,
        cert=args.cert,
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
