"""Shared pytest fixtures for the pyrtma test suite.

The helpers behind these fixtures are in ``tests/helpers.py``, so the
``unittest`` suites can use them too.
"""

from __future__ import annotations

import socket
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from pyrtma.client import Client

from .helpers import (
    DEFAULT_TIMEOUT,
    LOOPBACK,
    ManagerHarness,
    ScriptedManager,
    ThreadExceptionCollector,
    free_port as find_free_port,
    manager_options,
)
from .test_msg_defs import test_defs as td


@pytest.fixture(autouse=True)
def thread_exceptions() -> Iterator[ThreadExceptionCollector]:
    """Fail the test if an exception escapes any thread while it runs.

    Autouse fixtures are set up before the others, so the collector is in
    place for the whole test, including the teardown of other fixtures, such
    as the manager thread being joined. A test that expects a thread to fail
    requests this fixture and takes the exception with ``take()``.

    Yields:
        The collector for the current test.
    """
    collector = ThreadExceptionCollector()
    collector.install()
    try:
        yield collector
    finally:
        collector.uninstall()
    caught = collector.take()
    if caught:
        details = "\n".join(
            f"Thread {item.thread_name!r}:\n{item.formatted}" for item in caught
        )
        pytest.fail(f"An exception escaped a thread:\n{details}", pytrace=False)


@pytest.fixture
def free_port() -> int:
    """A loopback TCP port that was free when the fixture ran.

    Returns:
        The port number.
    """
    return find_free_port()


@pytest.fixture
def manager(request: pytest.FixtureRequest) -> Iterator[ManagerHarness]:
    """A message manager running on loopback for the duration of the test.

    Teardown fails the test if the manager thread raised or didn't stop.
    ``MessageManager`` options come from the test's ``manager_options``
    marker, if it has one.

    Args:
        request: The requesting test's fixture request.

    Yields:
        The running harness; connect clients to its ``address``.
    """
    harness = ManagerHarness(**manager_options(request))
    harness.start()
    try:
        yield harness
    finally:
        harness.stop()


@pytest.fixture
def client_factory(manager: ManagerHarness) -> Iterator[Callable[..., Client]]:
    """Create clients connected to the ``manager`` fixture.

    The factory takes ``Client`` keyword arguments, plus ``logger_status`` for
    ``connect()``. Clients use the compiled test definitions unless told
    otherwise. All clients are disconnected at teardown.

    Yields:
        The factory.
    """
    clients: list[Client] = []

    def make(*, logger_status: bool = False, **kwargs: Any) -> Client:
        kwargs.setdefault("definitions", td.get_message_definitions())
        client = Client(**kwargs)
        clients.append(client)
        client.connect(manager.address, logger_status=logger_status)
        return client

    yield make
    for client in clients:
        client.disconnect()


@pytest.fixture
def raw_connection(manager: ManagerHarness) -> Iterator[socket.socket]:
    """A plain TCP socket connected to the ``manager`` fixture.

    Use it to send malformed or partial bytes. Reads time out instead of
    blocking forever. The socket is closed at teardown.

    Yields:
        The connected socket.
    """
    sock = socket.create_connection((LOOPBACK, manager.port), timeout=DEFAULT_TIMEOUT)
    try:
        yield sock
    finally:
        sock.close()


@pytest.fixture
def scripted_manager() -> Iterator[ScriptedManager]:
    """A stand-in manager that the test scripts; see ``helpers.ScriptedManager``.

    Yields:
        The stand-in, listening, with no client connected yet.
    """
    stand_in = ScriptedManager()
    try:
        yield stand_in
    finally:
        stand_in.stop()
