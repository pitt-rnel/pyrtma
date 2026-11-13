"""Tests for ``pyrtma.unified_console_log``: connecting, the main loop's
reconnect back-off, and the command line."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable

import pytest

import pyrtma.core_defs as cd
import pyrtma.unified_console_log as ucl
from pyrtma.client import Client
from pyrtma.exceptions import MessageManagerNotFound

from .helpers import DEFAULT_TIMEOUT, ManagerHarness, wait_for


def stopping_sleep(
    delays: list[float], unified: Callable[[], ucl.RTMA_UnifiedLog], calls: int
) -> Callable[[float], None]:
    """Build a sleep stand-in that records delays and stops the loop.

    Args:
        delays: Receives each requested delay.
        unified: Returns the unified log to stop.
        calls: Stop the loop on this call.

    Returns:
        The stand-in, which returns at once.
    """

    def sleep(delay: float) -> None:
        delays.append(delay)
        if len(delays) >= calls:
            unified().stop()

    return sleep


def run_in_thread(unified: ucl.RTMA_UnifiedLog) -> threading.Thread:
    """Run ``unified.start()`` in a daemon thread.

    Args:
        unified: The unified log.

    Returns:
        The started thread.
    """
    thread = threading.Thread(target=unified.start, name="unified-log", daemon=True)
    thread.start()
    return thread


def quiet(unified: ucl.RTMA_UnifiedLog) -> ucl.RTMA_UnifiedLog:
    """Turn off the unified log's own console output.

    Args:
        unified: The unified log.

    Returns:
        The same unified log.
    """
    unified.mod.logger.enable_console = False
    return unified


@pytest.mark.parametrize(
    ("name", "level"),
    [
        ("DEBUG", logging.DEBUG),
        ("INFO", logging.INFO),
        ("WARN", logging.WARNING),
        ("ERROR", logging.ERROR),
        ("CRITICAL", logging.CRITICAL),
    ],
)
def test_log_level_names_resolve(name: str, level: int) -> None:
    args = ucl.parse_args(["-l", name])

    assert args.log_level == level


def test_server_address_comes_from_options() -> None:
    assert ucl.parse_args([]).server == "127.0.0.1:7111"
    assert ucl.parse_args(["-a", "10.0.0.2", "-p", "7200"]).server == "10.0.0.2:7200"


@pytest.mark.integration
class TestConnect:
    def test_init_rtma_connects_to_manager(self, manager: ManagerHarness) -> None:
        unified = quiet(ucl.RTMA_UnifiedLog(server=manager.address))

        unified.init_rtma()

        try:
            assert unified.mod.connected
            assert cd.MT_RTMA_LOG_INFO in unified.mod.subscribed_types
        finally:
            unified.disconnect()

    def test_exit_message_stops_the_loop(
        self, manager: ManagerHarness, client_factory: Callable[..., Client]
    ) -> None:
        unified = quiet(ucl.RTMA_UnifiedLog(server=manager.address))
        thread = run_in_thread(unified)
        assert wait_for(lambda: unified.mod.connected)
        sender = client_factory(name="sender")

        def exit_sent() -> bool:
            sender.send_signal(cd.MT_EXIT)
            thread.join(0.05)
            return not thread.is_alive()

        assert wait_for(exit_sent)
        assert not unified.mod.connected


class TestBackoff:
    @pytest.mark.integration
    def test_retries_back_off_without_manager(self, free_port: int) -> None:
        delays: list[float] = []
        unified = quiet(
            ucl.RTMA_UnifiedLog(
                server=f"127.0.0.1:{free_port}",
                sleep=stopping_sleep(delays, lambda: unified, 6),
            )
        )

        unified.start()

        assert delays == [0.5, 1.0, 2.0, 4.0, 5.0, 5.0]

    def test_delay_resets_after_a_connection(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        delays: list[float] = []
        unified = quiet(
            ucl.RTMA_UnifiedLog(sleep=stopping_sleep(delays, lambda: unified, 3))
        )
        attempts: list[int] = []

        def init_rtma() -> None:
            # Two failures, then a connection that is at once found unusable.
            attempts.append(1)
            if len(attempts) <= 2:
                raise MessageManagerNotFound("no manager")

        monkeypatch.setattr(unified, "init_rtma", init_rtma)

        unified.start()

        assert delays == [0.5, 1.0, 0.5]

    @pytest.mark.integration
    def test_lost_connection_is_retried_with_back_off(self) -> None:
        delays: list[float] = []
        harness = ManagerHarness()
        harness.start()
        unified = quiet(
            ucl.RTMA_UnifiedLog(
                server=harness.address,
                sleep=stopping_sleep(delays, lambda: unified, 2),
            )
        )
        thread = run_in_thread(unified)
        assert wait_for(lambda: unified.mod.connected)

        harness.stop()
        thread.join(DEFAULT_TIMEOUT)

        assert not thread.is_alive()
        assert delays == [0.5, 1.0]

    @pytest.mark.integration
    def test_stop_interrupts_the_default_sleep(
        self, free_port: int, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        unified = quiet(
            ucl.RTMA_UnifiedLog(server=f"127.0.0.1:{free_port}", retry_delay=30.0)
        )
        attempts: list[int] = []
        connect = unified.init_rtma

        def counting_init_rtma() -> None:
            attempts.append(1)
            connect()

        monkeypatch.setattr(unified, "init_rtma", counting_init_rtma)
        thread = run_in_thread(unified)
        assert wait_for(lambda: len(attempts) >= 1)
        started = time.monotonic()

        unified.stop()
        thread.join(DEFAULT_TIMEOUT)

        assert not thread.is_alive()
        assert time.monotonic() - started < DEFAULT_TIMEOUT
        assert len(attempts) == 1
