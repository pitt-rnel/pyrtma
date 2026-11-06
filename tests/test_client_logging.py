"""Tests for ``pyrtma.client_logging``: per-client loggers, RTMA log messages,
and the console formatter."""

from __future__ import annotations

import gc
import logging
import time
import weakref
from collections.abc import Callable
from pathlib import Path

import pytest

import pyrtma.core_defs as cd
from pyrtma.client import Client
from pyrtma.client_logging import RichLogFormatter, RTMALogger, RTMALogHandler
from pyrtma.message import Message

from .helpers import DEFAULT_TIMEOUT, ManagerHarness, wait_for
from .test_msg_defs import test_defs as td


def quiet_client(name: str = "") -> Client:
    """Create an unconnected client whose log lines don't reach the console.

    Args:
        name: The client's name.

    Returns:
        The client.
    """
    client = Client(name=name, definitions=td.get_message_definitions())
    client.logger.enable_console = False
    return client


def handler_count() -> int:
    """Count the handlers on every logger that ``logging`` knows about.

    Returns:
        The total, including the root logger's.
    """
    loggers = [logging.getLogger()] + [
        item
        for item in logging.Logger.manager.loggerDict.values()
        if isinstance(item, logging.Logger)
    ]
    return sum(len(item.handlers) for item in loggers)


def make_record(
    msg: object = "message",
    *,
    pathname: str = "module.py",
    func: str = "function",
    log_name: str = "test",
    args: tuple[object, ...] | None = None,
) -> logging.LogRecord:
    """Build a log record as a logger with an ``RtmaLogFilter`` would.

    Args:
        msg: The record's message or format string.
        pathname: The source path.
        func: The function name.
        log_name: The name the filter would attach.
        args: Arguments for ``msg``.

    Returns:
        The record.
    """
    record = logging.LogRecord(
        "test", logging.INFO, pathname, 12, msg, args, None, func=func
    )
    record.log_name = log_name
    return record


def deliver_log(sender: Client, receiver: Client, text: str) -> Message | None:
    """Log ``text`` from ``sender`` until ``receiver`` reads it as RTMA_LOG_INFO.

    Subscriptions race messages from other clients, so the line is logged
    again after each wait, as ``helpers.deliver()`` does for messages.

    Args:
        sender: The connected client that logs.
        receiver: A connected client subscribed to ``MT_RTMA_LOG_INFO``.
        text: The text to log.

    Returns:
        The first RTMA_LOG_INFO from the sender, or None before the deadline.
    """
    deadline = time.monotonic() + DEFAULT_TIMEOUT
    while time.monotonic() < deadline:
        sender.info(text)
        received = receiver.read_message(timeout=0.05)
        while received is not None:
            # The data class comes from the receiver's definitions, not from
            # core_defs, so it is matched by type ID rather than isinstance.
            if (
                received.type_id == cd.MT_RTMA_LOG_INFO
                and getattr(received.data, "name", None) == sender.logger.log_name
            ):
                return received
            received = receiver.read_message(timeout=0)
    return None


class TestLoggerLifecycle:
    def test_live_clients_have_distinct_loggers(self) -> None:
        first = quiet_client("first")
        second = quiet_client("second")

        assert first.logger.logger is not second.logger.logger
        assert first.logger.logger.name != second.logger.logger.name

    def test_new_client_logger_has_only_its_own_handlers(self) -> None:
        for _ in range(20):
            client = Client(definitions=td.get_message_definitions())

            own = {client.logger.rtma_handler, client.logger.console_handler}

            assert set(client.logger.logger.handlers) == own
            del client
            gc.collect()

    def test_discarded_clients_release_their_handlers(self) -> None:
        gc.collect()
        before = handler_count()

        for _ in range(50):
            Client(name="discarded", definitions=td.get_message_definitions())
        gc.collect()

        assert handler_count() == before

    def test_logger_does_not_keep_client_alive(self) -> None:
        client = quiet_client()
        ref = weakref.ref(client)

        del client
        gc.collect()

        assert ref() is None

    def test_close_removes_handlers_and_is_idempotent(self) -> None:
        client = Client(definitions=td.get_message_definitions())
        logger = client.logger

        logger.close()
        logger.close()

        assert logger.logger.handlers == []
        assert not logger.enable_rtma
        assert not logger.enable_console

    def test_console_can_be_enabled_again(self) -> None:
        client = quiet_client()

        client.logger.enable_console = True

        assert client.logger.console_handler is not None
        assert client.logger.console_handler in client.logger.logger.handlers


class TestLogMessageFields:
    @staticmethod
    def handler() -> tuple[Client, RTMALogHandler]:
        client = quiet_client()
        return client, RTMALogHandler(weakref.ref(client))

    def test_non_ascii_text_is_replaced(self) -> None:
        client, handler = self.handler()
        record = make_record(
            "5 kΩ at 20 µV",
            pathname="C:/Users/Jürgen/rig.py",
            func="mesure_é",
            log_name="Modül",
        )

        msg = handler.gen_log_msg(record)

        assert msg.message == "5 k? at 20 ?V"
        assert msg.pathname == "C:/Users/J?rgen/rig.py"
        assert msg.funcname == "mesure_?"
        assert msg.name == "Mod?l"

    def test_long_message_is_truncated_with_marker(self) -> None:
        client, handler = self.handler()
        record = make_record("é" * 2000)

        msg = handler.gen_log_msg(record)

        assert len(msg.message) == cd.MAX_LOG_LENGTH - 1
        assert msg.message.endswith("[TRUNCATED]")
        assert msg.message.startswith("???")

    def test_long_fields_are_truncated(self) -> None:
        client, handler = self.handler()
        path = "/data/" + "d" * 600 + "/rig.py"
        record = make_record(pathname=path, func="f" * 300, log_name="n" * 200)

        msg = handler.gen_log_msg(record)

        assert len(msg.pathname) == 511
        assert msg.pathname.startswith("...")
        assert msg.pathname.endswith("/rig.py")
        assert msg.funcname == "f" * 255
        assert msg.name == "n" * 127


@pytest.mark.integration
class TestRtmaSending:
    def test_non_ascii_message_is_sent_and_rtma_stays_enabled(
        self, client_factory: Callable[..., Client]
    ) -> None:
        receiver = client_factory(name="receiver")
        receiver.subscribe([cd.MT_RTMA_LOG_INFO])
        sender = client_factory(name="sender")
        sender.logger.enable_console = False

        received = deliver_log(sender, receiver, "5 kΩ")

        assert received is not None
        assert getattr(received.data, "message") == "5 k?"
        assert sender.logger.enable_rtma

    def test_rtma_logging_resumes_after_reconnect(
        self, manager: ManagerHarness, client_factory: Callable[..., Client]
    ) -> None:
        receiver = client_factory(name="receiver")
        receiver.subscribe([cd.MT_RTMA_LOG_INFO])
        sender = quiet_client("sender")
        first = ManagerHarness()
        first.start()
        sender.connect(first.address)
        first.stop()

        def logged_until_lost() -> bool:
            sender.info("probe")
            return not sender.connected or not sender.logger.enable_rtma

        lost = wait_for(logged_until_lost)

        assert lost
        assert sender.logger.enable_rtma
        sender.connect(manager.address)
        try:
            assert deliver_log(sender, receiver, "back again") is not None
        finally:
            sender.disconnect()

    def test_disabled_rtma_logging_stays_disabled_after_reconnect(
        self, manager: ManagerHarness, client_factory: Callable[..., Client]
    ) -> None:
        sender = client_factory(name="sender")
        sender.logger.enable_rtma = False

        sender.connect(manager.address)

        assert not sender.logger.enable_rtma
        assert sender.logger.rtma_handler is None


class TestRichLogFormatter:
    @staticmethod
    def formatter() -> RichLogFormatter:
        return RichLogFormatter("{message}", style="{")

    def test_record_is_left_unchanged(self) -> None:
        record = make_record("a [b] c")

        self.formatter().format(record)

        assert record.msg == "a [b] c"

    def test_markup_in_message_and_arguments_is_escaped(self) -> None:
        record = make_record("%s and [b]", args=("[red]x[/]",))

        text = self.formatter().format(record)

        assert text == "\\[red]x\\[/] and \\[b]"

    def test_message_that_is_not_a_string_is_formatted(self) -> None:
        record = make_record(42)

        assert self.formatter().format(record) == "42"

    def test_file_handler_after_console_sees_original_text(
        self, tmp_path: Path
    ) -> None:
        client = Client(name="filer", definitions=td.get_message_definitions())
        client.logger.log_filename = tmp_path / "client.log"
        client.logger.enable_file = True

        client.info("a [b] c")
        handler = client.logger.file_handler
        assert handler is not None
        handler.flush()
        client.logger.enable_file = False

        text = (tmp_path / "client.log").read_text(encoding="utf-8")
        assert "a [b] c" in text
        assert "\\[" not in text
