"""Helpers shared by the pytest fixtures and the existing ``unittest`` suites.

The fixtures in ``tests/conftest.py`` wrap these. They live in their own module
because ``unittest`` test cases can't request pytest fixtures, and importing
from ``conftest.py`` directly is fragile.
"""

from __future__ import annotations

import logging
import socket
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Callable

from pyrtma.client import Client
from pyrtma.manager import MessageManager
from pyrtma.message import Message
from pyrtma.message_data import MessageData

LOOPBACK: str = "127.0.0.1"
DEFAULT_TIMEOUT: float = 5.0


class HarnessError(Exception):
    """A test harness found a problem outside the test body."""


def free_port(host: str = LOOPBACK) -> int:
    """Find a TCP port that is free at the moment of the call.

    The port is released before returning, so another process could take it.
    Prefer binding to port 0 directly where the code under test allows it.

    Args:
        host: The address to bind on.

    Returns:
        A port number that could be bound on ``host``.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return sock.getsockname()[1]


def bound_port(manager: MessageManager) -> int:
    """Return the port a manager's listening socket is bound to.

    A manager constructed with ``port=0`` binds an unused port chosen by the
    operating system; this reads it back.

    Args:
        manager: A constructed message manager.

    Returns:
        The port number the manager listens on.
    """
    return manager.listen_socket.getsockname()[1]


def wait_for(
    condition: Callable[[], bool],
    timeout: float = DEFAULT_TIMEOUT,
    interval: float = 0.01,
    *,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> bool:
    """Poll a condition until it holds or a deadline passes.

    Args:
        condition: Called repeatedly; polling stops when it returns True.
        timeout: Seconds to wait before giving up.
        interval: Seconds to sleep between polls.
        clock: Monotonic clock, injectable for tests.
        sleep: Sleep function, injectable for tests.

    Returns:
        True if the condition held before the deadline, otherwise False.
    """
    deadline = clock() + timeout
    while True:
        if condition():
            return True
        if clock() >= deadline:
            return False
        sleep(interval)


def deliver(
    sender: Client,
    receiver: Client,
    msg: MessageData,
    timeout: float = DEFAULT_TIMEOUT,
    interval: float = 0.05,
    *,
    match: Callable[[Message], bool] | None = None,
) -> Message | None:
    """Send a message repeatedly until the receiver gets one of its type.

    A subscription takes effect when the manager processes it, and the manager
    doesn't order messages from different clients, so a single send right
    after subscribing can race the subscription. Resending until the message
    arrives avoids a fixed sleep.

    The receiver may be left with duplicates, and a duplicate can arrive well
    after this returns: the manager may forward it after messages from other
    clients. A later call for the same type should pass ``match``, so that it
    doesn't mistake a stale copy for its own message.

    Args:
        sender: The client that sends ``msg``.
        receiver: A client subscribed to the type of ``msg``.
        msg: The message to send.
        timeout: Seconds to keep trying.
        interval: Seconds to wait for the message after each send.
        match: Also required of a message of the same type, such as a check of
            a field value. Messages that fail it are skipped.

    Returns:
        The first message of the same type, and accepted by ``match`` if given,
        that the receiver read, or None if none arrived before the deadline.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        sender.send_message(msg)
        received = receiver.read_message(timeout=interval)
        while received is not None:
            if received.type_id == msg.type_id and (match is None or match(received)):
                return received
            received = receiver.read_message(timeout=0)
    return None


@dataclass(frozen=True)
class ThreadException:
    """An exception that escaped a thread.

    Attributes:
        thread_name: The name of the thread, or "" if it was unavailable.
        exc_type: The type of the exception.
        exc_value: The exception itself, or None if it was unavailable.
        formatted: The formatted traceback, captured when it was raised.
    """

    thread_name: str
    exc_type: type[BaseException]
    exc_value: BaseException | None
    formatted: str


class ThreadExceptionCollector:
    """Collects exceptions that escape threads, through ``threading.excepthook``.

    Install it with :meth:`install` and remove it with :meth:`uninstall`. While
    installed, it replaces the previous hook rather than calling it, so the
    exceptions it collects aren't printed twice.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._caught: list[ThreadException] = []
        self._previous: Callable[[threading.ExceptHookArgs], object] | None = None

    def _hook(self, args: threading.ExceptHookArgs) -> None:
        """Record one exception; called by ``threading`` in the dying thread.

        Args:
            args: The details ``threading`` passes to its hook.
        """
        lines = traceback.format_exception(
            args.exc_type, args.exc_value, args.exc_traceback
        )
        formatted = "".join(lines)
        name = args.thread.name if args.thread is not None else ""
        with self._lock:
            self._caught.append(
                ThreadException(name, args.exc_type, args.exc_value, formatted)
            )

    def install(self) -> None:
        """Start collecting, replacing the current ``threading.excepthook``."""
        self._previous = threading.excepthook
        threading.excepthook = self._hook

    def uninstall(self) -> None:
        """Stop collecting and restore the hook that was installed before."""
        if self._previous is not None:
            threading.excepthook = self._previous
            self._previous = None

    @property
    def caught(self) -> list[ThreadException]:
        """A copy of the exceptions collected and not yet taken."""
        with self._lock:
            return list(self._caught)

    def take(self) -> list[ThreadException]:
        """Return the collected exceptions and forget them.

        Tests that expect a thread to fail take its exception, so the fixture
        doesn't report it at teardown.

        Returns:
            The exceptions collected since the last call.
        """
        with self._lock:
            caught, self._caught = self._caught, []
        return caught


class ManagerHarness:
    """Runs a ``MessageManager`` on loopback in a background thread.

    The manager binds an unused port when it's constructed. :meth:`start` runs
    it, and :meth:`stop` closes it and reports a thread that raised or didn't
    stop. Clients that connect before ``run()`` begins wait in the listen
    backlog, so no handshake is needed to know the manager is ready.

    Attributes:
        manager: The manager under test.
        port: The port it listens on.
        address: The ``host:port`` string clients connect to.
    """

    def __init__(self, *, log_level: int = logging.ERROR) -> None:
        """Construct the manager and bind its port.

        Args:
            log_level: The manager's logging level.
        """
        self.manager = MessageManager(
            ip_address=LOOPBACK,
            port=0,
            log_level=log_level,
            debug=False,
        )
        self.port = bound_port(self.manager)
        self.address = f"{LOOPBACK}:{self.port}"
        self._error: BaseException | None = None
        self._thread = threading.Thread(
            target=self._run, name=f"manager-{self.port}", daemon=True
        )

    def _run(self) -> None:
        """Run the manager, keeping any exception for :meth:`stop` to report."""
        try:
            self.manager.run()
        except BaseException as err:  # reported by stop(), not by excepthook
            self._error = err

    @property
    def running(self) -> bool:
        """Whether the manager thread is alive."""
        return self._thread.is_alive()

    def start(self, timeout: float = DEFAULT_TIMEOUT) -> None:
        """Start the manager thread and wait until ``run()`` has begun.

        Waiting matters only for :meth:`stop`: ``close()`` called before
        ``run()`` sets its running flag would be overwritten, and the loop
        would never end.

        Args:
            timeout: Seconds to wait for ``run()`` to begin.

        Raises:
            HarnessError: The manager didn't start, or its thread died.
        """
        self._thread.start()
        started = wait_for(
            lambda: self.manager._keep_running or not self._thread.is_alive(),
            timeout,
        )
        if not started or not self._thread.is_alive():
            self.stop()
            raise HarnessError("The message manager did not start.")

    def stop(self, timeout: float = DEFAULT_TIMEOUT) -> None:
        """Close the manager, wait for its thread, and report problems.

        Args:
            timeout: Seconds to wait for the thread to finish.

        Raises:
            HarnessError: The manager thread raised, or didn't stop in time.
        """
        if self._thread.ident is None:
            # Never started: run() didn't get the chance to close the socket.
            self.manager.listen_socket.close()
            return
        self.manager.close()
        self._thread.join(timeout)
        if self._thread.is_alive():
            raise HarnessError(f"The message manager didn't stop within {timeout} s.")
        if self._error is not None:
            raise HarnessError(
                f"The message manager thread raised {self._error!r}."
            ) from self._error
