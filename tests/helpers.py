"""Helpers shared by the pytest fixtures and the existing ``unittest`` suites.

The fixtures in ``tests/conftest.py`` wrap these. They live in their own module
because ``unittest`` test cases can't request pytest fixtures, and importing
from ``conftest.py`` directly is fragile.
"""

from __future__ import annotations

import logging
import pathlib
import select
import socket
import struct
import sys
import threading
import time
import textwrap
import traceback
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable

from pyrtma import core_defs as cd
from pyrtma.client import Client
from pyrtma.header import MessageHeader
from pyrtma.manager import MessageManager
from pyrtma.message import Message
from pyrtma.message_data import MessageData
from pyrtma.parser import Parser

if TYPE_CHECKING:
    import pytest

LOOPBACK: str = "127.0.0.1"
DEFAULT_TIMEOUT: float = 5.0


def manager_options(request: pytest.FixtureRequest) -> dict[str, Any]:
    """Return the ``MessageManager`` options a test asks for.

    A test sets them with ``@pytest.mark.manager_options(stall_timeout=0.3)``.

    Args:
        request: The requesting test's fixture request.

    Returns:
        The marker's keyword arguments, or an empty dict without the marker.
    """
    marker = request.node.get_closest_marker("manager_options")
    return dict(marker.kwargs) if marker is not None else {}


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


class FakeClock:
    """A clock that only moves when the test advances it.

    Reading it from several threads is safe; it is only advanced by the test.
    """

    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        """Move the clock forward.

        Args:
            seconds: How far.
        """
        self.now += seconds


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


def read_until(
    client: Client,
    predicate: Callable[[Message], bool],
    timeout: float = DEFAULT_TIMEOUT,
) -> list[Message] | None:
    """Read messages until one matches.

    Args:
        client: The client to read from.
        predicate: Returns True for the message being waited for.
        timeout: Seconds to keep reading.

    Returns:
        Every message read, ending with the matching one, or None if none
        matched before the deadline.
    """
    seen: list[Message] = []

    def matched() -> bool:
        msg = client.read_message(timeout=0.05)
        if msg is None:
            return False
        seen.append(msg)
        return predicate(msg)

    return seen if wait_for(matched, timeout, interval=0) else None


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

    def __init__(self, *, log_level: int = logging.ERROR, **options: Any) -> None:
        """Construct the manager and bind its port.

        Args:
            log_level: The manager's logging level.
            options: Other ``MessageManager`` keyword arguments, such as
                ``stall_timeout``.
        """
        self.manager = MessageManager(
            ip_address=LOOPBACK,
            port=0,
            log_level=log_level,
            debug=False,
            **options,
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


HEADER_SIZE: int = MessageHeader().size


def frame(
    msg_type: int,
    payload: bytes = b"",
    *,
    dest_mod_id: int = 0,
    num_data_bytes: int | None = None,
) -> bytes:
    """Build a message as the manager sends it: the header, then the payload.

    Args:
        msg_type: The header's message type.
        payload: The bytes that follow the header.
        dest_mod_id: The header's destination module.
        num_data_bytes: The payload size announced in the header. Defaults to
            the length of ``payload``; pass another value for a corrupt header.

    Returns:
        The message's bytes.
    """
    header = MessageHeader()
    header.msg_type = msg_type
    header.src_mod_id = cd.MID_MESSAGE_MANAGER
    header.dest_mod_id = dest_mod_id
    header.num_data_bytes = len(payload) if num_data_bytes is None else num_data_bytes
    return bytes(header) + payload


def recv_exactly(sock: socket.socket, nbytes: int) -> bytes:
    """Read exactly ``nbytes`` from a socket.

    Args:
        sock: A socket with a timeout, so that missing bytes fail the read
            rather than hang it.
        nbytes: How many bytes to read.

    Returns:
        The bytes.

    Raises:
        HarnessError: The peer closed the connection before sending them all.
    """
    data = bytearray()
    while len(data) < nbytes:
        chunk = sock.recv(nbytes - len(data))
        if not chunk:
            raise HarnessError(
                f"Connection closed after {len(data)} of {nbytes} bytes."
            )
        data += chunk
    return bytes(data)


def bytes_waiting(sock: socket.socket, nbytes: int) -> bool:
    """Whether at least ``nbytes`` have arrived on a socket, unread.

    Nothing is taken from the socket.

    Args:
        sock: The socket to look at.
        nbytes: How many bytes to look for.

    Returns:
        True if that many bytes could be read now without waiting.
    """
    readable, _, _ = select.select([sock], [], [], 0)
    if not readable:
        return False
    return len(sock.recv(nbytes, socket.MSG_PEEK)) >= nbytes


class ScriptedManager:
    """A stand-in for the message manager that a test scripts byte by byte.

    It listens on loopback and answers one client's connect message with an
    ACK. After that it sends only what the test passes to :meth:`send`, and
    reads nothing more from the client; the few messages a test's client
    sends fit in the socket's buffer. It is for what the real manager can't
    produce on demand: part of a message, a steady stream of messages the
    client didn't subscribe to, a corrupt header, or a reset connection.

    Attributes:
        address: The ``host:port`` string to connect a client to.
    """

    def __init__(
        self,
        *,
        module_id: int = cd.DYN_MOD_ID_START,
        receive_buffer: int | None = None,
    ) -> None:
        """Bind an unused loopback port.

        Args:
            module_id: The ID the ACK assigns to a client that asks for a
                dynamic one.
            receive_buffer: A size for the connection's receive buffer, so
                that a test can fill it; None keeps the system's default.
        """
        self._module_id = module_id
        self._listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if receive_buffer is not None:
            # Set before listening, so the accepted connection inherits it.
            self._listener.setsockopt(
                socket.SOL_SOCKET, socket.SO_RCVBUF, receive_buffer
            )
        self._listener.bind((LOOPBACK, 0))
        self._listener.listen(1)
        self.address = f"{LOOPBACK}:{self._listener.getsockname()[1]}"
        self._conn: socket.socket | None = None
        self._lock = threading.Lock()

    def connect(self, client: Client, timeout: float = DEFAULT_TIMEOUT) -> None:
        """Connect a client to this stand-in, answering its connect with an ACK.

        Args:
            client: The client to connect.
            timeout: Seconds to wait for each step.

        Raises:
            HarnessError: The client didn't connect.
        """
        accepted: list[socket.socket] = []

        def serve() -> None:
            self._listener.settimeout(timeout)
            conn, _ = self._listener.accept()
            conn.settimeout(timeout)
            header = MessageHeader.from_buffer_copy(recv_exactly(conn, HEADER_SIZE))
            recv_exactly(conn, header.num_data_bytes)
            assigned = header.src_mod_id or self._module_id
            conn.sendall(frame(cd.MT_ACKNOWLEDGE, dest_mod_id=assigned))
            accepted.append(conn)

        server = threading.Thread(target=serve, name="scripted-manager", daemon=True)
        server.start()
        client.connect(self.address)
        server.join(timeout)
        if not accepted:
            raise HarnessError("The client didn't connect to the scripted manager.")
        self._conn = accepted[0]

    def _connection(self) -> socket.socket:
        """Return the connection to the client.

        Returns:
            The connected socket.

        Raises:
            HarnessError: No client has connected.
        """
        if self._conn is None:
            raise HarnessError("No client has connected to the scripted manager.")
        return self._conn

    def send(self, data: bytes) -> None:
        """Send bytes to the client. Safe to call from a timer thread.

        Args:
            data: Messages from :func:`frame`, or part of one.
        """
        with self._lock:
            self._connection().sendall(data)

    def receive(self, nbytes: int) -> bytes:
        """Read what the client sent after connecting.

        Args:
            nbytes: How many bytes to read.

        Returns:
            The bytes.

        Raises:
            HarnessError: The client closed the connection first.
        """
        return recv_exactly(self._connection(), nbytes)

    def close(self) -> None:
        """End the connection cleanly, as a manager that exits does.

        Only the sending side is shut down, so the client reads end-of-file.
        Closing the socket would send a reset instead, because the client's
        messages are left unread.
        """
        with self._lock:
            self._connection().shutdown(socket.SHUT_WR)

    def reset(self) -> None:
        """Reset the connection, as a manager that crashes can."""
        with self._lock:
            conn = self._connection()
            # With a linger time of zero, close() sends RST instead of FIN.
            linger = struct.pack("HH" if sys.platform == "win32" else "ii", 1, 0)
            conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, linger)
            conn.close()

    def stop(self) -> None:
        """Close the connection, if there is one, and the listening socket."""
        with self._lock:
            if self._conn is not None:
                self._conn.close()
        self._listener.close()


class RecordingHandler(logging.Handler):
    """A logging handler that keeps the records it is given."""

    def __init__(self) -> None:
        super().__init__(logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        """Keep a record.

        Args:
            record: The record to keep.
        """
        self.records.append(record)

    @property
    def warnings(self) -> list[str]:
        """The messages of the records at WARNING or above.

        Returns:
            The formatted messages, in the order they were logged.
        """
        return [r.getMessage() for r in self.records if r.levelno >= logging.WARNING]


def write_definitions(
    directory: pathlib.Path,
    files: dict[str, str],
    *,
    options: str = "",
    defs_name: str = "test.defs",
) -> pathlib.Path:
    """Write YAML definition files and a compiler index that lists them.

    Args:
        directory: Where to write the files, such as ``tmp_path``.
        files: YAML text for each index entry, by entry name, in index order.
            Each is written to ``<name>.yaml``, dedented.
        options: The body of a ``compiler_options`` section, if any, dedented.
        defs_name: The index file's name.

    Returns:
        The path of the index file.
    """
    index = []
    if options:
        index.append("compiler_options:")
        index.extend(f"  {line}" for line in textwrap.dedent(options).splitlines())
    index.append("index:")
    for name, text in files.items():
        path = directory / f"{name}.yaml"
        path.write_text(textwrap.dedent(text), encoding="utf-8")
        index.append(f"  {name}: {path.name}")
    defs_file = directory / defs_name
    defs_file.write_text("\n".join(index) + "\n", encoding="utf-8")
    return defs_file


def quiet_parser() -> tuple[Parser, RecordingHandler]:
    """A parser whose log goes to a recording handler instead of the console.

    Returns:
        The parser and the handler that records its warnings.
    """
    parser = Parser()
    recorder = RecordingHandler()
    parser.logger.handlers.clear()
    parser.logger.addHandler(recorder)
    parser.logger.setLevel(logging.WARNING)
    return parser, recorder


def parse_definitions(defs_file: pathlib.Path) -> tuple[Parser, RecordingHandler]:
    """Parse a compiler index with a quiet parser.

    Args:
        defs_file: The index file to parse.

    Returns:
        The parser, holding the parsed definitions, and its recorded log.
    """
    parser, recorder = quiet_parser()
    parser.parse(defs_file)
    return parser, recorder
