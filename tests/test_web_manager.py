"""Tests for ``pyrtma.web_manager``: the command line, logging setup, the
websocket handler driven without a websocket, and the server with real
websocket clients."""

from __future__ import annotations

import ctypes
import inspect
import json
import logging
import os
import shutil
import socket
import ssl
import subprocess
import sys
import threading
import types
from collections.abc import Callable
from pathlib import Path
from typing import Any, Iterator, cast

import pytest
from websockets.exceptions import ConnectionClosed, ConnectionClosedOK, InvalidMessage
from websockets.sync.client import ClientConnection
from websockets.sync.client import connect as ws_connect
from websockets.sync.connection import Connection

import pyrtma.core_defs as cd
import pyrtma.web_manager as wm
from pyrtma.client import Client
from pyrtma.definitions import MessageDefinitions
from pyrtma.header import MessageHeader
from pyrtma.message import Message
from pyrtma.message_data import MessageData

from .helpers import (
    DEFAULT_TIMEOUT,
    LOOPBACK,
    ManagerHarness,
    RecordingHandler,
    deliver,
    free_port,
    read_until,
)
from .test_msg_defs import test_defs as td

DEFS_FILE = Path(td.__file__)


class StubHandler(wm.RTMAWebSocketHandler):
    """An ``RTMAWebSocketHandler`` with no websocket behind it.

    It takes the proxy it's given, rather than making one, and starts no
    reader thread, so the tests read for the proxy themselves. Messages for
    the websocket are collected in ``sent``.
    """

    def __init__(self, proxy: Client) -> None:
        self.connection = None
        self.mm_ip = LOOPBACK
        self.proxy = proxy
        self.rtma_connected = False
        self.proxy_lock = threading.RLock()
        self._stop_reading = threading.Event()
        self._reader = None
        self.sent: list[str] = []

    @property
    def ws_ready_to_send(self) -> bool:
        return True

    def send_message(self, message: Any) -> None:
        self.sent.append(message)

    def start_reader(self) -> None:
        pass


def raw_message(msg_type: int, payload: MessageData) -> bytes:
    """Build the bytes of a whole message as the manager would send it.

    Args:
        msg_type: The message type.
        payload: The message data.

    Returns:
        The header bytes followed by the payload.
    """
    header = MessageHeader()
    header.msg_type = msg_type
    header.num_data_bytes = ctypes.sizeof(payload)
    return bytes(header) + bytes(payload)


def test_import_keeps_root_handlers() -> None:
    script = (
        "import logging, sys\n"
        "handler = logging.StreamHandler(sys.stdout)\n"
        "logging.getLogger().addHandler(handler)\n"
        "import pyrtma.web_manager\n"
        "print(logging.getLogger().handlers == [handler])\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )

    assert result.stdout.strip() == "True"


def test_configure_logging_replaces_root_handlers() -> None:
    empty = logging.Logger("empty-root")
    configured = logging.Logger("configured-root")
    old = logging.StreamHandler()
    configured.addHandler(old)

    wm.configure_logging(empty)
    wm.configure_logging(configured)

    for root in (empty, configured):
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0], wm.RichHandler)


def test_default_manager_address_uses_the_core_host_and_port() -> None:
    args = wm.parse_args(["-d", "defs.py"])

    assert args.mm_ip == f"{cd.DEFAULT_HOST}:{cd.DEFAULT_PORT}"
    assert (
        inspect.signature(wm.WebMessageManager).parameters["mm_ip"].default
        == args.mm_ip
    )


def test_defs_option_is_required(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        wm.parse_args(["-m", "127.0.0.1:7111"])

    assert raised.value.code == 2
    assert "--defs" in capsys.readouterr().err


def test_proxy_records_are_printed_once(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    root = RecordingHandler()
    monkeypatch.setattr(logging.getLogger(), "handlers", [root])
    server = types.SimpleNamespace(
        mm_ip=LOOPBACK, definitions=cd.get_message_definitions()
    )

    handler = wm.RTMAWebSocketHandler(None, server)
    handler.proxy.warning("proxy-hello")

    assert [r.getMessage() for r in root.records] == ["proxy-hello"]
    assert "proxy-hello" not in "".join(capsys.readouterr())


def test_definitions_are_loaded_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    defs_file = tmp_path / "rig_defs.py"
    shutil.copy(DEFS_FILE, defs_file)
    loads: list[str] = []
    load = wm.load_message_definitions

    def counting_load(path: Any) -> MessageDefinitions:
        loads.append(str(path))
        return load(path)

    servers: list[wm.WebMessageManager] = []

    def no_serve(self: wm.WebMessageManager, *args: Any, **kwargs: Any) -> None:
        servers.append(self)
        self.shutdown()

    monkeypatch.setattr(wm, "load_message_definitions", counting_load)
    monkeypatch.setattr(wm.WebMessageManager, "run_forever", no_serve)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.delitem(sys.modules, "rig_defs", raising=False)
    monkeypatch.setattr(wm.logger, "level", wm.logger.level)

    wm.run(wm.parse_args(["-d", str(defs_file), "-a", "127.0.0.1", "-p", "0"]))

    assert loads == [str(defs_file)]
    assert "rig_defs" not in sys.modules
    assert str(tmp_path) not in sys.path
    assert servers[0].definitions is not None
    assert servers[0].definitions.message_id_from_name("TEST_START") is not None


def test_failed_message_carries_the_whole_header() -> None:
    sent: list[Any] = []
    proxy = types.SimpleNamespace(
        module_id=12345, connected=True, send_message=sent.append
    )
    handler = StubHandler(cast(Client, proxy))
    header = MessageHeader()
    header.msg_type = td.MT_TEST_START
    header.msg_count = 7
    header.send_time = 12.5
    header.src_host_id = 3
    header.src_mod_id = 101
    header.num_data_bytes = 4
    header.remaining_bytes = 9
    header.is_dynamic = 1
    header.version = 0x89ABCDEF

    handler.send_failed_message(header, 1.5)

    (failed,) = sent
    assert bytes(failed.msg_header) == bytes(header)
    assert (failed.dest_mod_id, failed.time_of_failure) == (12345, 1.5)


@pytest.mark.integration
class TestProxyRead:
    def test_unsubscribed_message_does_not_block(self) -> None:
        # The real manager follows every message a client didn't subscribe
        # to with an ACK soon after, so a hand-rolled peer stands in for it:
        # one unsubscribed message, then nothing.
        with socket.create_server((LOOPBACK, 0)) as listener:
            proxy = Client(name="proxy", definitions=td.get_message_definitions())
            proxy.logger.enable_console = False
            proxy._socket_connect(f"{LOOPBACK}:{listener.getsockname()[1]}")
            peer, _ = listener.accept()
            try:
                peer.sendall(raw_message(td.MT_TEST_START, td.MDF_TEST_START()))
                handler = StubHandler(proxy)
                reader = threading.Thread(
                    target=handler.read_proxy_message, daemon=True
                )

                reader.start()
                reader.join(DEFAULT_TIMEOUT)

                assert not reader.is_alive()
                assert handler.sent == []
            finally:
                peer.close()
                proxy.disconnect()

    def test_partial_message_does_not_block(self) -> None:
        # The proxy's socket is readable once part of a message arrives; the
        # read must return without waiting for the rest.
        with socket.create_server((LOOPBACK, 0)) as listener:
            proxy = Client(name="proxy", definitions=td.get_message_definitions())
            proxy.logger.enable_console = False
            proxy._socket_connect(f"{LOOPBACK}:{listener.getsockname()[1]}")
            peer, _ = listener.accept()
            try:
                wire = raw_message(td.MT_TEST_START, td.MDF_TEST_START())
                peer.sendall(wire[: len(wire) // 2])
                handler = StubHandler(proxy)
                reader = threading.Thread(
                    target=handler.read_proxy_message, daemon=True
                )

                reader.start()
                reader.join(DEFAULT_TIMEOUT)

                assert not reader.is_alive()
                assert handler.sent == []
            finally:
                peer.close()
                proxy.disconnect()


def connect_message(*, src_mod_id: int = 0, logger_status: int = 0) -> Message:
    """Build a CONNECT as a web client sends it, after JSON decoding.

    Args:
        src_mod_id: The module ID in its header; CONNECT asks for an ID there.
        logger_status: 1 to connect as a logger.

    Returns:
        The message.
    """
    header = MessageHeader()
    header.msg_type = cd.MT_CONNECT
    header.src_mod_id = src_mod_id
    data = cd.MDF_CONNECT()
    data.logger_status = logger_status
    return Message(header, data)


def connect_v2_message(name: str, *, mod_id: int = 0) -> Message:
    """Build a CONNECT_V2 as a web client would send it, after JSON decoding.

    Args:
        name: The module name.
        mod_id: The requested module ID, or 0 for a dynamic one.

    Returns:
        The message.
    """
    header = MessageHeader()
    header.msg_type = cd.MT_CONNECT_V2
    data = cd.MDF_CONNECT_V2()
    data.name = name
    data.mod_id = mod_id
    return Message(header, data)


def sent_types(handler: StubHandler) -> list[int]:
    """Return the message types a handler passed to its websocket.

    Args:
        handler: The handler.

    Returns:
        One message type per JSON message, in order.
    """
    return [json.loads(text)["header"]["msg_type"] for text in handler.sent]


@pytest.mark.integration
class TestConnect:
    @pytest.fixture
    def handler(self, manager: ManagerHarness) -> Iterator[StubHandler]:
        """A stub handler whose proxy has a socket to the manager, as
        ``handle()`` sets up before the web client's first message."""
        proxy = Client(definitions=td.get_message_definitions())
        proxy.logger.enable_console = False
        proxy._socket_connect(manager.address)
        try:
            yield StubHandler(proxy)
        finally:
            proxy.disconnect()

    @pytest.fixture
    def hello_observer(
        self, client_factory: Callable[..., Client]
    ) -> Callable[[Callable[[Any], bool]], list[Message] | None]:
        """A client subscribed to HELLO, with the subscription confirmed.

        Returns:
            A function that reads HELLO messages until one passes a check on
            its data.
        """
        observer = client_factory(name="observer")
        observer.subscribe([cd.MT_HELLO, td.MT_TEST_START])
        sender = client_factory(name="sender")
        assert deliver(sender, observer, td.MDF_TEST_START()) is not None

        def wait_for_hello(check: Callable[[Any], bool]) -> list[Message] | None:
            return read_until(
                observer, lambda m: m.type_id == cd.MT_HELLO and check(m.data)
            )

        return wait_for_hello

    def test_handle_connect_returns_ack(self, handler: StubHandler) -> None:
        handler.handle_connect(connect_message())

        assert sent_types(handler) == [cd.MT_ACKNOWLEDGE]
        ack = json.loads(handler.sent[0])
        assert ack["header"]["dest_mod_id"] == handler.proxy.module_id
        assert handler.proxy.module_id >= cd.DYN_MOD_ID_START

    def test_handle_connect_v2_returns_ack_and_sets_name(
        self, handler: StubHandler, hello_observer: Any
    ) -> None:
        handler.handle_connect_v2(connect_v2_message("web-page"))

        assert sent_types(handler) == [cd.MT_ACKNOWLEDGE]
        mod_id = handler.proxy.module_id
        assert hello_observer(lambda d: d.mod_id == mod_id and d.name == "web-page")

    def test_connect_json_from_web_client(self, handler: StubHandler) -> None:
        text = connect_message().to_json(minify=True)

        handler.process_json_message(text)

        assert sent_types(handler) == [cd.MT_ACKNOWLEDGE]

    @pytest.mark.parametrize(
        "make",
        [
            lambda: connect_message(src_mod_id=50),
            lambda: connect_v2_message("static", mod_id=50),
        ],
        ids=["CONNECT", "CONNECT_V2"],
    )
    def test_requested_static_id_gets_dynamic_id(
        self, handler: StubHandler, make: Callable[[], Message]
    ) -> None:
        msg = make()

        handler.process_json_message(msg.to_json(minify=True))

        assert sent_types(handler) == [cd.MT_ACKNOWLEDGE]
        assert handler.proxy.module_id >= cd.DYN_MOD_ID_START

    def test_connect_v2_after_connect_updates_name(
        self, handler: StubHandler, hello_observer: Any
    ) -> None:
        handler.handle_connect(connect_message())
        mod_id = handler.proxy.module_id

        handler.handle_connect_v2(connect_v2_message("late-page"))

        assert sent_types(handler) == [cd.MT_ACKNOWLEDGE]
        assert handler.proxy.module_id == mod_id
        assert handler.proxy.name == "late-page"
        assert hello_observer(lambda d: d.mod_id == mod_id and d.name == "late-page")

    def test_module_ready_sends_the_web_managers_pid(
        self, handler: StubHandler, hello_observer: Any
    ) -> None:
        handler.handle_connect_v2(connect_v2_message("page"))
        mod_id = handler.proxy.module_id
        assert hello_observer(lambda d: d.mod_id == mod_id)
        header = MessageHeader()
        header.msg_type = cd.MT_MODULE_READY
        data = cd.MDF_MODULE_READY()
        data.pid = os.getpid() + 1

        handler.process_json_message(Message(header, data).to_json(minify=True))

        hellos = hello_observer(lambda d: d.mod_id == mod_id)
        assert hellos is not None
        assert hellos[-1].data.pid == os.getpid()
        assert [text for text in handler.sent if "rtma_msg_error" in text] == []

    @pytest.mark.parametrize(
        "msg_type", [cd.ALL_MESSAGE_TYPES, 7777], ids=["all types", "undefined"]
    )
    @pytest.mark.parametrize("command", ["subscribe", "unsubscribe", "pause"])
    def test_subscription_commands_report_no_error(
        self, handler: StubHandler, msg_type: int, command: str
    ) -> None:
        handler.handle_connect_v2(connect_v2_message("page"))
        handler.sent.clear()
        ctrl = {
            "subscribe": (cd.MT_SUBSCRIBE, cd.MDF_SUBSCRIBE),
            "unsubscribe": (cd.MT_UNSUBSCRIBE, cd.MDF_UNSUBSCRIBE),
            "pause": (cd.MT_PAUSE_SUBSCRIPTION, cd.MDF_PAUSE_SUBSCRIPTION),
        }
        header = MessageHeader()
        header.msg_type, data_cls = ctrl[command]
        data = data_cls()
        data.msg_type = msg_type

        handler.process_json_message(Message(header, data).to_json(minify=True))

        assert [text for text in handler.sent if "rtma_msg_error" in text] == []
        expected = {msg_type} if command == "subscribe" else set()
        assert handler.proxy.subscribed_types == expected

    @pytest.mark.parametrize("msg_type", [-1, cd.MAX_MESSAGE_TYPES + 1])
    def test_invalid_subscription_type_gets_an_error_reply(
        self, handler: StubHandler, msg_type: int
    ) -> None:
        handler.handle_connect_v2(connect_v2_message("page"))
        handler.sent.clear()
        header = MessageHeader()
        header.msg_type = cd.MT_SUBSCRIBE
        data = cd.MDF_SUBSCRIBE()
        data.msg_type = msg_type

        handler.process_json_message(Message(header, data).to_json(minify=True))

        errors = [json.loads(text)["rtma_msg_error"] for text in handler.sent]
        assert len(errors) == 1 and "Invalid message type" in errors[0]
        assert handler.proxy.subscribed_types == set()

    def test_connect_after_connect_v2_is_ignored(self, handler: StubHandler) -> None:
        handler.handle_connect_v2(connect_v2_message("page"))
        mod_id = handler.proxy.module_id

        handler.handle_connect(connect_message())

        assert sent_types(handler) == [cd.MT_ACKNOWLEDGE]
        assert handler.proxy.module_id == mod_id
        assert handler.proxy.name == "page"


def message_json(msg_type: int, data: MessageData | None = None) -> str:
    """Build a message's JSON as a web client sends it.

    Args:
        msg_type: The message type.
        data: The message data, or None for a signal.

    Returns:
        The JSON text.
    """
    header = MessageHeader()
    header.msg_type = msg_type
    return Message(header, data or cd.MDF_EXIT()).to_json(minify=True)


def closed_with(ws: Connection) -> ConnectionClosed:
    """Read until the server closes the websocket, and return how it closed.

    Args:
        ws: The web client's websocket.

    Returns:
        The exception that ended the read.
    """
    with pytest.raises(ConnectionClosed) as raised:
        while True:
            ws.recv(timeout=DEFAULT_TIMEOUT)
    return raised.value


@pytest.mark.integration
class TestServer:
    """The web manager with real websocket clients, from the websockets
    library, and the ``manager`` fixture behind it."""

    @pytest.fixture
    def web_manager(self, manager: ManagerHarness) -> Iterator[wm.WebMessageManager]:
        server = wm.WebMessageManager(
            host=LOOPBACK,
            port=0,
            mm_ip=manager.address,
            definitions=td.get_message_definitions(),
        )
        thread = threading.Thread(target=server.run_forever, daemon=True)
        thread.start()
        try:
            yield server
        finally:
            server.shutdown()
            thread.join(DEFAULT_TIMEOUT)
            assert not thread.is_alive()

    @staticmethod
    def connect(server: wm.WebMessageManager, name: str = "page") -> ClientConnection:
        """Connect a web client with CONNECT_V2, and read its ACK.

        Args:
            server: The web manager.
            name: The module name.

        Returns:
            The web client's websocket.
        """
        ws = ws_connect(f"ws://{LOOPBACK}:{server.port}", open_timeout=DEFAULT_TIMEOUT)
        ws.send(connect_v2_message(name).to_json(minify=True))
        ack = json.loads(ws.recv(timeout=DEFAULT_TIMEOUT))
        assert ack["header"]["msg_type"] == cd.MT_ACKNOWLEDGE
        return ws

    def test_messages_pass_both_ways(
        self,
        web_manager: wm.WebMessageManager,
        client_factory: Callable[..., Client],
    ) -> None:
        peer = client_factory(name="peer")
        peer.subscribe([td.MT_TEST_END])
        with self.connect(web_manager) as ws:
            subscribe = cd.MDF_SUBSCRIBE()
            subscribe.msg_type = td.MT_TEST_START
            ws.send(message_json(cd.MT_SUBSCRIBE, subscribe))
            # The subscription is in place once the manager has passed on a
            # message sent after it.
            ws.send(message_json(td.MT_TEST_END, td.MDF_TEST_END()))
            assert read_until(peer, lambda m: m.type_id == td.MT_TEST_END)

            start = td.MDF_TEST_START()
            start.id = 42
            peer.send_message(start)
            # The manager's ACK of the SUBSCRIBE comes first.
            received = json.loads(ws.recv(timeout=DEFAULT_TIMEOUT))
            while received["header"]["msg_type"] == cd.MT_ACKNOWLEDGE:
                received = json.loads(ws.recv(timeout=DEFAULT_TIMEOUT))

        assert received["header"]["msg_type"] == td.MT_TEST_START
        assert received["header"]["src_mod_id"] == peer.module_id
        assert received["data"] == {"id": 42}

    def test_messages_sent_together_pass_at_once(
        self,
        web_manager: wm.WebMessageManager,
        client_factory: Callable[..., Client],
    ) -> None:
        # Messages that reach the web manager together must not wait for
        # further input, such as rtma-js's next keepalive, 750 ms later.
        peer = client_factory(name="peer")
        peer.subscribe([td.MT_TEST_START])
        with self.connect(web_manager) as ws:
            for n in range(5):
                start = td.MDF_TEST_START()
                start.id = n
                ws.send(message_json(td.MT_TEST_START, start))

            seen = read_until(
                peer,
                lambda m: m.type_id == td.MT_TEST_START and m.data.id == 4,
                timeout=0.5,
            )

        assert seen is not None
        assert [m.data.id for m in seen if m.type_id == td.MT_TEST_START] == [
            0,
            1,
            2,
            3,
            4,
        ]

    def test_ping_gets_pong(self, web_manager: wm.WebMessageManager) -> None:
        with self.connect(web_manager) as ws:
            ws.send("PING")

            assert ws.recv(timeout=DEFAULT_TIMEOUT) == "PONG"

    def test_disconnect_closes_the_websocket_cleanly(
        self, web_manager: wm.WebMessageManager
    ) -> None:
        with self.connect(web_manager) as ws:
            ws.send(message_json(cd.MT_DISCONNECT))

            closed = closed_with(ws)

        assert isinstance(closed, ConnectionClosedOK)
        assert closed.rcvd is not None and closed.rcvd.code == 1000

    def test_closing_the_websocket_disconnects_the_proxy(
        self,
        web_manager: wm.WebMessageManager,
        client_factory: Callable[..., Client],
    ) -> None:
        observer = client_factory(name="observer")
        observer.subscribe([cd.MT_HELLO, cd.MT_GOODBYE])
        ws = self.connect(web_manager, "leaving")
        hello = read_until(
            observer,
            lambda m: m.type_id == cd.MT_HELLO and m.data.name == "leaving",
        )
        assert hello is not None

        ws.close()

        mod_id = hello[-1].data.mod_id
        assert read_until(
            observer,
            lambda m: m.type_id == cd.MT_GOODBYE and m.data.mod_id == mod_id,
        )

    def test_unreachable_manager_gets_an_error_and_a_close(self) -> None:
        # Nothing listens on a port that was just free.
        server = wm.WebMessageManager(
            host=LOOPBACK,
            port=0,
            mm_ip=f"{LOOPBACK}:{free_port()}",
            definitions=td.get_message_definitions(),
        )
        thread = threading.Thread(target=server.run_forever, daemon=True)
        thread.start()
        try:
            with ws_connect(f"ws://{LOOPBACK}:{server.port}") as ws:
                error = json.loads(ws.recv(timeout=DEFAULT_TIMEOUT))
                closed = closed_with(ws)
        finally:
            server.shutdown()
            thread.join(DEFAULT_TIMEOUT)

        assert "No message manager" in error["rtma_msg_error"]
        assert isinstance(closed, ConnectionClosedOK)
        assert closed.rcvd is not None and closed.rcvd.code == 1000

    def test_losing_the_manager_closes_the_websocket(self) -> None:
        harness = ManagerHarness()
        harness.start()
        server = wm.WebMessageManager(
            host=LOOPBACK,
            port=0,
            mm_ip=harness.address,
            definitions=td.get_message_definitions(),
        )
        thread = threading.Thread(target=server.run_forever, daemon=True)
        thread.start()
        try:
            with self.connect(server) as ws:
                harness.stop()
                closed = closed_with(ws)
        finally:
            server.shutdown()
            thread.join(DEFAULT_TIMEOUT)
            harness.stop()

        assert isinstance(closed, ConnectionClosedOK)

    def test_text_over_1_mib_is_read(self, web_manager: wm.WebMessageManager) -> None:
        # A message of MAX_DATA_BYTES is longer than that as JSON, and the
        # websockets library refuses 1 MiB or more by default.
        with self.connect(web_manager) as ws:
            ws.send("x" * (2 * 2**20))
            error = json.loads(ws.recv(timeout=DEFAULT_TIMEOUT))
            ws.send("PING")
            pong = ws.recv(timeout=DEFAULT_TIMEOUT)

        assert "rtma_msg_error" in error
        assert pong == "PONG"

    @pytest.mark.parametrize("text", ["not json", "{}", "[1]"])
    def test_text_that_isnt_a_message_gets_an_error(
        self, web_manager: wm.WebMessageManager, text: str
    ) -> None:
        with self.connect(web_manager) as ws:
            ws.send(text)
            error = json.loads(ws.recv(timeout=DEFAULT_TIMEOUT))
            ws.send("PING")
            pong = ws.recv(timeout=DEFAULT_TIMEOUT)

        assert error["rtma_msg_error"].startswith("Not a message")
        assert pong == "PONG"

    def test_binary_message_is_ignored(self, web_manager: wm.WebMessageManager) -> None:
        with self.connect(web_manager) as ws:
            ws.send(b"\x00\x01")
            ws.send("PING")

            assert ws.recv(timeout=DEFAULT_TIMEOUT) == "PONG"

    def test_shutdown_closes_the_websockets(self, manager: ManagerHarness) -> None:
        server = wm.WebMessageManager(
            host=LOOPBACK,
            port=0,
            mm_ip=manager.address,
            definitions=td.get_message_definitions(),
        )
        thread = threading.Thread(target=server.run_forever, daemon=True)
        thread.start()
        with self.connect(server) as ws:
            server.shutdown()
            closed = closed_with(ws)
        thread.join(DEFAULT_TIMEOUT)

        assert not thread.is_alive()
        assert closed.rcvd is not None and closed.rcvd.code == 1001


#: openssl's configuration for the test certificate. openssl is given a file
#: of the test's own, since some builds look for theirs where none is
#: installed: conda's on Windows, for one, looks in
#: C:\Program Files\Common Files\ssl.
CERT_CONFIG = """\
[req]
distinguished_name = req_dn
x509_extensions = v3
prompt = no

[req_dn]
CN = localhost

[v3]
basicConstraints = critical, CA:TRUE
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid:always, issuer
subjectAltName = DNS:localhost, IP:127.0.0.1
"""


@pytest.fixture(scope="module")
def tls_files(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """A throwaway self-signed certificate for 127.0.0.1 and localhost.

    It is made with OpenSSL for each run, so that no private key is kept in
    the repository; tests that need it are skipped without OpenSSL, with
    openssl's error when it fails.

    Returns:
        The certificate's path and its private key's path.
    """
    openssl = shutil.which("openssl")
    if openssl is None:
        pytest.skip("openssl is not on PATH")
    folder = tmp_path_factory.mktemp("tls")
    config, cert, key = folder / "openssl.cnf", folder / "cert.pem", folder / "key.pem"
    config.write_text(CERT_CONFIG)
    made = subprocess.run(
        [openssl, "req", "-x509", "-config", str(config), "-newkey", "ec"]
        + ["-pkeyopt", "ec_paramgen_curve:prime256v1", "-nodes", "-days", "1"]
        + ["-keyout", str(key), "-out", str(cert)],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if made.returncode != 0:
        pytest.skip(f"openssl couldn't make a test certificate: {made.stderr}")
    return cert, key


def test_cert_and_key_options() -> None:
    args = wm.parse_args(["-d", "defs.py", "--cert", "c.pem", "--key", "k.pem"])

    assert (args.cert, args.key) == ("c.pem", "k.pem")
    assert wm.parse_args(["-d", "defs.py"]).cert is None


def test_key_option_needs_cert(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        wm.parse_args(["-d", "defs.py", "--key", "k.pem"])

    assert raised.value.code == 2
    assert "--key needs --cert" in capsys.readouterr().err


def test_key_without_cert_raises() -> None:
    with pytest.raises(ValueError, match="needs a certificate"):
        wm.WebMessageManager(host=LOOPBACK, key="k.pem")


def test_missing_cert_raises(tmp_path: Path) -> None:
    missing = tmp_path / "missing.pem"

    with pytest.raises(ValueError, match="Can't load the TLS certificate"):
        wm.WebMessageManager(host=LOOPBACK, cert=str(missing))


@pytest.mark.integration
class TestTLS:
    """The web manager serving wss://, with the certificate from
    ``tls_files`` and the ``manager`` fixture behind it."""

    @staticmethod
    def start(
        manager: ManagerHarness, cert: Path, key: Path | None
    ) -> tuple[wm.WebMessageManager, threading.Thread]:
        server = wm.WebMessageManager(
            host=LOOPBACK,
            port=0,
            mm_ip=manager.address,
            cert=str(cert),
            key=None if key is None else str(key),
            definitions=td.get_message_definitions(),
        )
        thread = threading.Thread(target=server.run_forever, daemon=True)
        thread.start()
        return server, thread

    @staticmethod
    def trusting(cert: Path) -> ssl.SSLContext:
        """A client context that trusts the test certificate alone."""
        return ssl.create_default_context(cafile=str(cert))

    def test_wss_client_connects_and_messages_pass(
        self,
        manager: ManagerHarness,
        tls_files: tuple[Path, Path],
        client_factory: Callable[..., Client],
    ) -> None:
        cert, key = tls_files
        server, thread = self.start(manager, cert, key)
        peer = client_factory(name="peer")
        peer.subscribe([td.MT_TEST_START])
        try:
            assert server.secure
            with ws_connect(
                f"wss://{LOOPBACK}:{server.port}",
                ssl=self.trusting(cert),
                open_timeout=DEFAULT_TIMEOUT,
            ) as ws:
                ws.send(connect_v2_message("secure").to_json(minify=True))
                ack = json.loads(ws.recv(timeout=DEFAULT_TIMEOUT))
                # Sent together, so they may share a TLS record.
                for n in range(5):
                    start = td.MDF_TEST_START()
                    start.id = n
                    ws.send(message_json(td.MT_TEST_START, start))
                seen = read_until(
                    peer,
                    lambda m: m.type_id == td.MT_TEST_START and m.data.id == 4,
                    timeout=0.5,
                )
                ws.send("PING")
                pong = ws.recv(timeout=DEFAULT_TIMEOUT)
        finally:
            server.shutdown()
            thread.join(DEFAULT_TIMEOUT)

        assert ack["header"]["msg_type"] == cd.MT_ACKNOWLEDGE
        assert seen is not None
        assert [m.data.id for m in seen if m.type_id == td.MT_TEST_START] == [
            0,
            1,
            2,
            3,
            4,
        ]
        assert pong == "PONG"

    def test_plain_client_is_refused(
        self, manager: ManagerHarness, tls_files: tuple[Path, Path]
    ) -> None:
        # A ws:// client is never served without TLS, and the server goes
        # on serving wss:// clients.
        cert, key = tls_files
        server, thread = self.start(manager, cert, key)
        try:
            with pytest.raises(InvalidMessage):
                ws_connect(
                    f"ws://{LOOPBACK}:{server.port}", open_timeout=DEFAULT_TIMEOUT
                ).close()
            with ws_connect(
                f"wss://{LOOPBACK}:{server.port}",
                ssl=self.trusting(cert),
                open_timeout=DEFAULT_TIMEOUT,
            ) as ws:
                ws.send("PING")
                pong = ws.recv(timeout=DEFAULT_TIMEOUT)
        finally:
            server.shutdown()
            thread.join(DEFAULT_TIMEOUT)

        assert pong == "PONG"

    def test_key_in_the_cert_file(
        self,
        manager: ManagerHarness,
        tls_files: tuple[Path, Path],
        tmp_path: Path,
    ) -> None:
        cert, key = tls_files
        combined = tmp_path / "combined.pem"
        combined.write_text(key.read_text() + cert.read_text())
        server, thread = self.start(manager, combined, None)
        try:
            with ws_connect(
                f"wss://{LOOPBACK}:{server.port}",
                ssl=self.trusting(cert),
                open_timeout=DEFAULT_TIMEOUT,
            ) as ws:
                ws.send("PING")
                pong = ws.recv(timeout=DEFAULT_TIMEOUT)
        finally:
            server.shutdown()
            thread.join(DEFAULT_TIMEOUT)

        assert pong == "PONG"

    def test_key_that_doesnt_match_raises(
        self, tls_files: tuple[Path, Path], tmp_path: Path
    ) -> None:
        cert, _ = tls_files
        not_a_key = tmp_path / "not_a_key.pem"
        not_a_key.write_text("not a key\n")

        with pytest.raises(ValueError, match="Can't load the TLS certificate"):
            wm.WebMessageManager(host=LOOPBACK, cert=str(cert), key=str(not_a_key))
