"""Tests for ``pyrtma.web_manager``: the command line, logging setup, and the
websocket handler, driven without a real websocket."""

from __future__ import annotations

import ctypes
import json
import logging
import shutil
import socket
import subprocess
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any, Iterator

import pytest

import pyrtma.core_defs as cd
import pyrtma.web_manager as wm
from pyrtma.client import Client
from pyrtma.definitions import MessageDefinitions
from pyrtma.header import MessageHeader
from pyrtma.message import Message
from pyrtma.message_data import MessageData

from .helpers import DEFAULT_TIMEOUT, LOOPBACK, ManagerHarness, deliver, read_until
from .test_msg_defs import test_defs as td

DEFS_FILE = Path(td.__file__)


class StubHandler(wm.RTMAWebSocketHandler):
    """An ``RTMAWebSocketHandler`` with no websocket behind it.

    ``socketserver`` handlers do all their work in ``__init__``, so this one
    skips the base constructors and sets only what the RTMA side uses.
    Messages for the websocket are collected in ``sent``.
    """

    def __init__(self, proxy: Client) -> None:
        self.proxy = proxy
        self.keep_alive = True
        self.sent: list[str] = []

    @property
    def ws_ready_to_send(self) -> bool:
        return True

    def send_message(self, message: Any) -> None:
        self.sent.append(message)


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


def test_defs_option_is_required(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        wm.parse_args(["-m", "127.0.0.1:7111"])

    assert raised.value.code == 2
    assert "--defs" in capsys.readouterr().err


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
        self.server_close()

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

    def test_connect_after_connect_v2_is_ignored(self, handler: StubHandler) -> None:
        handler.handle_connect_v2(connect_v2_message("page"))
        mod_id = handler.proxy.module_id

        handler.handle_connect(connect_message())

        assert sent_types(handler) == [cd.MT_ACKNOWLEDGE]
        assert handler.proxy.module_id == mod_id
        assert handler.proxy.name == "page"
