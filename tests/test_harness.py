"""Tests for the shared fixtures in ``tests/conftest.py`` and ``tests/helpers.py``."""

import socket
import threading
from collections.abc import Callable

import pytest

from pyrtma.client import Client

from .helpers import (
    HarnessError,
    ManagerHarness,
    ThreadExceptionCollector,
    deliver,
    wait_for,
)
from .test_msg_defs import test_defs as td


def test_free_port_can_be_bound(free_port: int) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", free_port))

        assert sock.getsockname()[1] == free_port


@pytest.mark.integration
def test_manager_routes_between_clients(client_factory: Callable[..., Client]) -> None:
    publisher = client_factory()
    subscriber = client_factory()
    subscriber.subscribe([td.MT_TEST_START])
    msg = td.MDF_TEST_START()
    msg.id = 42

    received = deliver(publisher, subscriber, msg)

    assert received is not None
    assert received.data == msg


@pytest.mark.integration
def test_raw_connection_reaches_manager(
    manager: ManagerHarness, raw_connection: socket.socket
) -> None:
    assert raw_connection.getpeername()[1] == manager.port


def test_collector_catches_thread_exception(
    thread_exceptions: ThreadExceptionCollector,
) -> None:
    def fail() -> None:
        raise RuntimeError("boom")

    thread = threading.Thread(target=fail, name="failing-thread")
    thread.start()
    thread.join()

    caught = thread_exceptions.take()
    names = [(c.thread_name, c.exc_type) for c in caught]
    assert names == [("failing-thread", RuntimeError)]
    assert "boom" in caught[0].formatted


@pytest.mark.integration
def test_manager_harness_reports_dead_thread() -> None:
    harness = ManagerHarness()
    harness.start()
    # An invalid select() timeout makes the next loop iteration raise TypeError.
    harness.manager.read_timeout = "invalid"  # type: ignore[assignment]
    wait_for(lambda: not harness.running)

    with pytest.raises(HarnessError, match="TypeError"):
        harness.stop()
