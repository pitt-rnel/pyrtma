"""Tests for ``pyrtma.web_manager``: the command line, logging setup, and the
websocket handler, driven without a real websocket."""

from __future__ import annotations

import ctypes
import logging
import shutil
import socket
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any

import pytest

import pyrtma.web_manager as wm
from pyrtma.client import Client
from pyrtma.definitions import MessageDefinitions
from pyrtma.header import MessageHeader
from pyrtma.message_data import MessageData

from .helpers import DEFAULT_TIMEOUT, LOOPBACK
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
