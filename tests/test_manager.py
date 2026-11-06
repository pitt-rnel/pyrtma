"""Tests for ``pyrtma.manager``: header checks, removal, routing, and ``msg_count``.

Tests that need real routing use the ``manager`` fixture over loopback. Tests
that need conditions real sockets can't produce on demand, such as two peers
resetting at the same moment, drive the manager's methods directly with
``FakeConnection`` stand-ins, which raise the same errors real sockets do.
"""

from __future__ import annotations

import ctypes
import errno
import logging
import os
import socket
import sys
import time
from contextlib import contextmanager
from collections.abc import Callable, Iterable, Iterator
from typing import Any, cast

import pytest

from pyrtma import core_defs as cd
from pyrtma.client import Client
from pyrtma.header import MessageHeader
from pyrtma.core_defs import ALL_MESSAGE_TYPES
from pyrtma.exceptions import ConnectionLost
from pyrtma.manager import DEFAULT_STALL_TIMEOUT, MessageManager, Module, _parse_args
from pyrtma.message import Message

from .helpers import (
    DEFAULT_TIMEOUT,
    LOOPBACK,
    ManagerHarness,
    deliver,
    manager_options,
    read_until,
    wait_for,
)
from .test_msg_defs import test_defs as td

pytestmark = pytest.mark.integration

# The src_mod_id that raw connections put in their headers, so their messages
# can be told apart from the clients' own.
RAW_SRC_MOD_ID = 123

# A user message type: the manager forwards it without checking its size.
USER_MSG_TYPE = 5000


class FakeConnection:
    """Stands in for a client socket in non-blocking mode.

    Sending: a healthy connection records each ``send()`` call's bytes in
    ``sent``. ``accept`` limits how many more bytes it takes, so a send can be
    partial; a connection that is full, or not ``writable``, raises
    ``BlockingIOError`` as a non-blocking socket does. A failing one raises
    ``ConnectionResetError``, as a socket does after the peer resets.

    Receiving: ``feed()`` queues chunks. ``recv_into`` returns at most the bytes
    asked for from the first chunk and keeps the rest, as the kernel's buffer
    does. An empty chunk reads as the peer closing, and with nothing queued it
    raises ``BlockingIOError``.

    Any connection raises ``OSError(EBADF)`` once it's closed, as a real one
    does. There is no ``sendall``: the manager must not block on a client.
    """

    def __init__(
        self, *, fail: bool = False, writable: bool = True, accept: int | None = None
    ) -> None:
        self.fail = fail
        self.writable = writable
        self.accept = accept
        self.sent: list[bytes] = []
        self.incoming: list[bytes] = []
        self.close_count = 0

    def _check_open(self) -> None:
        if self.close_count:
            raise OSError(errno.EBADF, "Bad file descriptor")

    def send(self, data: Any) -> int:
        self._check_open()
        if self.fail:
            raise ConnectionResetError(errno.ECONNRESET, "Connection reset by peer")
        room = len(data) if self.accept is None else min(len(data), self.accept)
        if not self.writable or room == 0:
            raise BlockingIOError(errno.EAGAIN, "Resource temporarily unavailable")
        self.sent.append(bytes(data[:room]))
        if self.accept is not None:
            self.accept -= room
        return room

    def feed(self, *chunks: bytes) -> None:
        self.incoming.extend(chunks)

    def recv_into(self, buffer: Any, nbytes: int = 0) -> int:
        self._check_open()
        if not self.incoming:
            raise BlockingIOError(errno.EAGAIN, "Resource temporarily unavailable")
        chunk = self.incoming[0]
        if not chunk:
            return 0  # the peer closed; later reads see that too
        count = min(nbytes or len(buffer), len(chunk))
        buffer[:count] = chunk[:count]
        if count < len(chunk):
            self.incoming[0] = chunk[count:]
        else:
            self.incoming.pop(0)
        return count

    def close(self) -> None:
        self.close_count += 1


def fake_conn(module: Module) -> FakeConnection:
    """Return a fake module's connection with its fake type.

    Args:
        module: A module made by ``add_fake_module``.

    Returns:
        Its connection.
    """
    assert isinstance(module.conn, FakeConnection)
    return module.conn


def sent_messages(module: Module) -> list[tuple[MessageHeader, bytes]]:
    """Split what a fake module was sent into headers and payloads.

    Args:
        module: A module made by ``add_fake_module``.

    Returns:
        One ``(header, payload)`` pair per message, in the order sent.
    """
    header_cls = module.header_cls
    raw = b"".join(fake_conn(module).sent)
    size = ctypes.sizeof(header_cls)
    messages: list[tuple[MessageHeader, bytes]] = []
    pos = 0
    while pos < len(raw):
        header = header_cls.from_buffer_copy(raw[pos : pos + size])
        pos += size
        messages.append((header, raw[pos : pos + header.num_data_bytes]))
        pos += header.num_data_bytes
    return messages


def goodbye_ids(module: Module) -> list[int]:
    """Return the module IDs of the ``GOODBYE`` messages a fake module was sent.

    Args:
        module: A module made by ``add_fake_module``.

    Returns:
        One module ID per ``GOODBYE``, in the order sent.
    """
    return [
        cd.MDF_GOODBYE.from_buffer_copy(payload).mod_id
        for header, payload in sent_messages(module)
        if header.msg_type == cd.MT_GOODBYE
    ]


@pytest.fixture
def bare_manager(request: pytest.FixtureRequest) -> Iterator[MessageManager]:
    """A manager that is constructed but never run, for driving its methods.

    Options come from the test's ``manager_options`` marker, as for ``manager``.

    Args:
        request: The requesting test's fixture request.

    Yields:
        The manager. Its listening socket is closed at teardown.
    """
    options: dict[str, Any] = {"log_level": logging.ERROR}
    options.update(manager_options(request))
    manager = MessageManager(ip_address=LOOPBACK, port=0, **options)
    try:
        yield manager
    finally:
        manager.listen_socket.close()


def add_fake_module(
    manager: MessageManager,
    mod_id: int,
    *,
    subs: Iterable[int] = (),
    fail: bool = False,
    writable: bool = True,
    accept: int | None = None,
    is_logger: bool = False,
    connected: bool = True,
) -> Module:
    """Register a connected module on a fake connection, as ``run()`` would.

    Args:
        manager: The manager to add the module to.
        mod_id: The module's ID.
        subs: Message types it subscribes to.
        fail: Whether sends to it raise ``ConnectionResetError``.
        writable: Whether its connection takes any bytes at all.
        accept: How many bytes its connection takes before it is full, or None
            for no limit.
        is_logger: Whether it registered as a logger.
        connected: Whether it has connected, or is only an accepted socket.

    Returns:
        The new module.
    """
    # The manager only calls send(), recv_into() and close() on a client's
    # connection, so the fake can stand in.
    conn = cast(
        socket.socket, FakeConnection(fail=fail, writable=writable, accept=accept)
    )
    module = Module(
        conn,
        (LOOPBACK, 20000 + mod_id),
        manager.header_cls,
        name=f"fake{mod_id}",
        mod_id=mod_id,
        connected=connected,
        is_logger=is_logger,
    )
    manager.modules[conn] = module
    manager.sockets.append(conn)
    for msg_type in subs:
        manager.subscriptions[msg_type].add(module)
        module.subs.add(msg_type)
    if is_logger:
        manager.logger_modules.add(module)
    return module


def make_header(
    manager: MessageManager, msg_type: int, *, dest_mod_id: int = 0, msg_count: int = 0
) -> MessageHeader:
    """Build the header of a message from another module.

    Args:
        manager: The manager, for its header class.
        msg_type: The message type.
        dest_mod_id: The destination module, or 0 to broadcast.
        msg_count: The sender's message count.

    Returns:
        The header, with no data bytes.
    """
    header = manager.header_cls()
    header.msg_type = msg_type
    header.src_mod_id = RAW_SRC_MOD_ID
    header.dest_mod_id = dest_mod_id
    header.msg_count = msg_count
    return header


def watcher(
    client_factory: Callable[..., Client], *types: int
) -> tuple[Client, Client]:
    """Connect a sender and an observer that has subscribed to ``types``.

    The observer subscribes to ``GOODBYE`` and the given types, then to
    ``TEST_START``, each in its own call. The manager handles one client's
    messages in order, so once a ``TEST_START`` from the sender arrives, the
    earlier subscriptions are in place too.

    Args:
        client_factory: The ``client_factory`` fixture.
        types: Message types the observer should also receive.

    Returns:
        The sender and the observer.
    """
    sender = client_factory()
    observer = client_factory()
    observer.subscribe([cd.MT_GOODBYE, *types])
    observer.subscribe([td.MT_TEST_START])
    assert deliver(sender, observer, td.MDF_TEST_START()) is not None
    return sender, observer


def raw_header(msg_type: int, num_data_bytes: int) -> bytes:
    """Build the bytes of a header as a raw client would send it.

    Args:
        msg_type: The message type.
        num_data_bytes: The data size the header announces.

    Returns:
        The header bytes.
    """
    header = MessageHeader()
    header.msg_type = msg_type
    header.src_mod_id = RAW_SRC_MOD_ID
    header.num_data_bytes = num_data_bytes
    return bytes(header)


def raw_message(msg_type: int, payload: bytes = b"") -> bytes:
    """Build the bytes of a whole message as a raw client would send it.

    Args:
        msg_type: The message type.
        payload: The message data.

    Returns:
        The header bytes followed by the payload.
    """
    return raw_header(msg_type, len(payload)) + payload


def recv_message(sock: socket.socket) -> tuple[MessageHeader, bytes]:
    """Read one whole message from a raw connection.

    Args:
        sock: A raw connection with a read timeout.

    Returns:
        The message's header and payload.
    """

    def recv_exact(count: int) -> bytes:
        data = b""
        while len(data) < count:
            chunk = sock.recv(count - len(data))
            assert chunk, "the manager closed the connection"
            data += chunk
        return data

    header = MessageHeader.from_buffer_copy(recv_exact(ctypes.sizeof(MessageHeader)))
    return header, recv_exact(header.num_data_bytes)


def connect_raw(sock: socket.socket, name: str = "raw") -> int:
    """Connect a raw connection as a module, as ``Client.connect`` does.

    Args:
        sock: A raw connection with a read timeout.
        name: The module name to send.

    Returns:
        The module ID the manager assigned.
    """
    data = cd.MDF_CONNECT_V2()
    data.name = name
    sock.sendall(raw_message(cd.MT_CONNECT_V2, bytes(data)))
    header, _ = recv_message(sock)
    assert header.msg_type == cd.MT_ACKNOWLEDGE
    return header.dest_mod_id


def subscribe_raw(sock: socket.socket, msg_type: int) -> None:
    """Subscribe a connected raw connection to a message type.

    Args:
        sock: A raw connection that has connected, with a read timeout.
        msg_type: The type to subscribe to.
    """
    data = cd.MDF_SUBSCRIBE()
    data.msg_type = msg_type
    sock.sendall(raw_message(cd.MT_SUBSCRIBE, bytes(data)))
    header, _ = recv_message(sock)
    assert header.msg_type == cd.MT_ACKNOWLEDGE


def read_once(
    manager: MessageManager, module: Module
) -> tuple[MessageHeader, bytes] | None:
    """Give a module one read turn, as ``run()`` does when its socket is readable.

    Args:
        manager: A manager that isn't running.
        module: The module whose connection to read.

    Returns:
        A copy of the header and payload of the message the turn completed, or
        None if it didn't complete one.
    """
    header = manager.read_message(module.conn)
    if header is None:
        return None
    return (
        MessageHeader.from_buffer_copy(bytes(header)),
        bytes(manager.data_view[: header.num_data_bytes]),
    )


def read_until_done(
    manager: MessageManager, module: Module
) -> list[tuple[MessageHeader, bytes] | None]:
    """Give a fake module read turns until its queued bytes are used up.

    Turns also stop when the module is dropped. A queued close is never used
    up, so a manager that doesn't drop the module fails the turn limit.

    Args:
        manager: A manager that isn't running.
        module: A module made by ``add_fake_module``, with bytes fed to it.

    Returns:
        The result of each turn, as ``read_once`` returns it.
    """
    results: list[tuple[MessageHeader, bytes] | None] = []
    while fake_conn(module).incoming and is_routed(manager, module):
        assert len(results) < 10_000, "the queued bytes were never used up"
        results.append(read_once(manager, module))
    return results


def is_routed(manager: MessageManager, module: Module) -> bool:
    """Report whether a module is still registered with a manager.

    Args:
        manager: The manager.
        module: The module.

    Returns:
        True until the module is removed.
    """
    return manager.modules.get(module.conn) is module


def read_until_marker(sender: Client, observer: Client) -> list[Message]:
    """Read everything the observer is sent up to a fresh marker message.

    Messages the manager forwarded before the marker was sent arrive before
    it, so this collects them all.

    Args:
        sender: A connected client.
        observer: A client already subscribed to ``TEST_START``.

    Returns:
        The messages read, ending with the marker.
    """
    marker = td.MDF_TEST_START()
    marker.id = 8
    sender.send_message(marker)
    seen = read_until(
        observer, lambda m: m.type_id == td.MT_TEST_START and m.data.id == 8
    )
    assert seen is not None
    return seen


def hello_ids(module: Module) -> list[int]:
    """Return the module IDs of the HELLO messages a fake module was sent.

    Args:
        module: A module made by ``add_fake_module``.

    Returns:
        One module ID per HELLO, in the order sent.
    """
    return [
        cd.MDF_HELLO.from_buffer_copy(payload).mod_id
        for header, payload in sent_messages(module)
        if header.msg_type == cd.MT_HELLO
    ]


def assert_closed_by_manager(sock: socket.socket) -> None:
    """Assert that the manager closed a raw connection.

    A socket closed with unread data in it is reset rather than closed
    cleanly, so a reset counts as closed too.

    Args:
        sock: The raw connection, which has a read timeout.
    """
    try:
        assert sock.recv(1) == b""
    except ConnectionResetError:
        pass


def assert_still_routes(sender: Client, observer: Client) -> None:
    """Assert that the manager still forwards messages between two clients.

    The message carries an ID that ``watcher()`` doesn't use, and only a copy
    with that ID counts: a stale copy of the watcher's own ``TEST_START`` can
    arrive after the dropped client's ``GOODBYE``.

    Args:
        sender: A connected client.
        observer: A client subscribed to ``TEST_START``.
    """
    msg = td.MDF_TEST_START()
    msg.id = 7
    received = deliver(sender, observer, msg, match=lambda m: m.data.id == msg.id)
    assert received is not None
    assert received.data.id == 7


class TestConstructor:
    def test_options_after_port_are_keyword_only(self) -> None:
        args: tuple[Any, ...] = (LOOPBACK, 0, logging.ERROR)

        with pytest.raises(TypeError):
            MessageManager(*args)

    def test_timecode_argument_is_rejected(self) -> None:
        kwargs: dict[str, Any] = {"timecode": True}

        with pytest.raises(TypeError, match="timecode"):
            MessageManager(ip_address=LOOPBACK, port=0, **kwargs)

    def test_default_timeouts(self, bare_manager: MessageManager) -> None:
        assert bare_manager.stall_timeout == DEFAULT_STALL_TIMEOUT == 5.0
        assert bare_manager.logger_timeout is None

    @pytest.mark.parametrize("option", ["stall_timeout", "logger_timeout"])
    @pytest.mark.parametrize("value", [0, -1.0])
    def test_timeouts_must_be_positive(self, option: str, value: float) -> None:
        kwargs: dict[str, Any] = {option: value}

        with pytest.raises(ValueError, match=option):
            MessageManager(ip_address=LOOPBACK, port=0, **kwargs)


class TestHeaderValidation:
    @pytest.mark.parametrize("data_size", [-1, 1024**2 + 1])
    def test_invalid_data_size_drops_only_that_client(
        self,
        manager: ManagerHarness,
        client_factory: Callable[..., Client],
        raw_connection: socket.socket,
        caplog: pytest.LogCaptureFixture,
        data_size: int,
    ) -> None:
        sender, observer = watcher(client_factory)

        raw_connection.sendall(raw_header(td.MT_TEST_END, data_size))

        assert_closed_by_manager(raw_connection)
        assert_still_routes(sender, observer)
        assert wait_for(
            lambda: any(
                r.levelno >= logging.ERROR
                and "num_data_bytes" in r.getMessage()
                and str(data_size) in r.getMessage()
                for r in caplog.records
            )
        )

    @pytest.mark.parametrize(
        ("msg_type", "data_size"),
        [
            (cd.MT_SUBSCRIBE, 0),
            (cd.MT_CONNECT_V2, 4),
            (cd.MT_DATASET_START, 31),
        ],
        ids=["SUBSCRIBE", "CONNECT_V2", "DATASET_START"],
    )
    def test_core_message_with_wrong_size_drops_client(
        self,
        manager: ManagerHarness,
        client_factory: Callable[..., Client],
        raw_connection: socket.socket,
        caplog: pytest.LogCaptureFixture,
        msg_type: int,
        data_size: int,
    ) -> None:
        sender, observer = watcher(client_factory, msg_type)

        raw_connection.sendall(raw_header(msg_type, data_size))
        raw_connection.sendall(bytes(data_size))

        assert_closed_by_manager(raw_connection)
        seen = read_until_marker(sender, observer)
        forwarded = [
            m
            for m in seen
            if m.type_id == msg_type and m.header.src_mod_id == RAW_SRC_MOD_ID
        ]
        assert forwarded == []
        assert wait_for(
            lambda: any(
                r.levelno >= logging.ERROR and f"MT={msg_type}" in r.getMessage()
                for r in caplog.records
            )
        )
        assert_still_routes(sender, observer)

    def test_core_message_with_right_size_is_forwarded(
        self,
        manager: ManagerHarness,
        client_factory: Callable[..., Client],
        raw_connection: socket.socket,
    ) -> None:
        sender, observer = watcher(client_factory, cd.MT_DATASET_START)
        size = cd.MDF_DATASET_START.type_size
        connect_raw(raw_connection)

        # Two in a row: the second arriving shows the first didn't drop the
        # raw client.
        for _ in range(2):
            raw_connection.sendall(raw_header(cd.MT_DATASET_START, size))
            raw_connection.sendall(bytes(size))

        for _ in range(2):
            seen = read_until(
                observer,
                lambda m: m.type_id == cd.MT_DATASET_START
                and m.header.src_mod_id == RAW_SRC_MOD_ID,
            )
            assert seen is not None


class TestRemoval:
    def test_simultaneous_subscriber_resets_remove_each_once(
        self, bare_manager: MessageManager
    ) -> None:
        src = add_fake_module(bare_manager, 101)
        dying = [
            add_fake_module(
                bare_manager, mod_id, subs=[cd.ALL_MESSAGE_TYPES], fail=True
            )
            for mod_id in (102, 103)
        ]
        observer = add_fake_module(
            bare_manager, 104, subs=[td.MT_TEST_START, cd.MT_GOODBYE]
        )

        bare_manager.forward_message(
            src, make_header(bare_manager, td.MT_TEST_START), b""
        )

        for module in dying:
            assert module.conn not in bare_manager.modules
            assert fake_conn(module).close_count == 1
        assert sorted(goodbye_ids(observer)) == [102, 103]
        delivered = sent_messages(observer)
        assert td.MT_TEST_START in [h.msg_type for h, _ in delivered]

    def test_simultaneous_logger_resets_remove_each_once(
        self, bare_manager: MessageManager
    ) -> None:
        src = add_fake_module(bare_manager, 101)
        dying = [
            add_fake_module(bare_manager, mod_id, fail=True, is_logger=True)
            for mod_id in (102, 103)
        ]
        observer = add_fake_module(bare_manager, 104, subs=[cd.MT_GOODBYE])

        bare_manager.send_ack(src)

        for module in dying:
            assert module.conn not in bare_manager.modules
            assert module not in bare_manager.logger_modules
            assert fake_conn(module).close_count == 1
        assert sorted(goodbye_ids(observer)) == [102, 103]

    def test_remove_module_twice_is_harmless(
        self, bare_manager: MessageManager
    ) -> None:
        module = add_fake_module(bare_manager, 101, subs=[td.MT_TEST_START])
        observer = add_fake_module(bare_manager, 102, subs=[cd.MT_GOODBYE])

        bare_manager.remove_module(module)
        bare_manager.remove_module(module)

        assert module.conn not in bare_manager.modules
        assert module.conn not in bare_manager.sockets
        assert module not in bare_manager.subscriptions[td.MT_TEST_START]
        assert fake_conn(module).close_count == 1
        assert goodbye_ids(observer) == [101]

    def test_disconnected_client_leaves_sockets_list(
        self, manager: ManagerHarness, client_factory: Callable[..., Client]
    ) -> None:
        client = client_factory()
        assert wait_for(lambda: len(manager.manager.sockets) == 2)

        client.disconnect()

        assert wait_for(lambda: len(manager.manager.sockets) == 1)
        assert manager.manager.sockets == [manager.manager.listen_socket]


class TestRouting:
    def test_non_destination_module_is_not_counted_as_drop(
        self, bare_manager: MessageManager
    ) -> None:
        src = add_fake_module(bare_manager, 101)
        dest = add_fake_module(bare_manager, 102, subs=[td.MT_TEST_START])
        bystander = add_fake_module(
            bare_manager, 103, subs=[td.MT_TEST_START], writable=False
        )
        observer = add_fake_module(bare_manager, 104, subs=[cd.MT_FAILED_MESSAGE])

        bare_manager.forward_message(
            src, make_header(bare_manager, td.MT_TEST_START, dest_mod_id=102), b""
        )

        assert bystander.drops == 0
        assert sent_messages(observer) == []
        assert len(sent_messages(dest)) == 1

    def test_unwritable_destination_is_counted_as_drop(
        self, bare_manager: MessageManager
    ) -> None:
        src = add_fake_module(bare_manager, 101)
        dest = add_fake_module(
            bare_manager, 102, subs=[td.MT_TEST_START], writable=False
        )
        observer = add_fake_module(bare_manager, 104, subs=[cd.MT_FAILED_MESSAGE])

        bare_manager.forward_message(
            src, make_header(bare_manager, td.MT_TEST_START, dest_mod_id=102), b""
        )

        assert dest.drops == 1
        failed = sent_messages(observer)
        assert [h.msg_type for h, _ in failed] == [cd.MT_FAILED_MESSAGE]
        assert cd.MDF_FAILED_MESSAGE.from_buffer_copy(failed[0][1]).dest_mod_id == 102


class TestMsgCount:
    def test_forwarded_message_keeps_sender_msg_count(
        self, client_factory: Callable[..., Client]
    ) -> None:
        sender, observer = watcher(client_factory, td.MT_TEST_END)
        expected = [sender.msg_count, sender.msg_count + 1]

        sender.send_message(td.MDF_TEST_END())
        sender.send_message(td.MDF_TEST_END())

        counts: list[int] = []
        for _ in expected:
            seen = read_until(observer, lambda m: m.type_id == td.MT_TEST_END)
            assert seen is not None
            counts.append(seen[-1].header.msg_count)
        assert counts == expected

    def test_manager_messages_have_zero_msg_count(
        self, bare_manager: MessageManager
    ) -> None:
        module = add_fake_module(
            bare_manager, 101, subs=[cd.MT_HELLO, cd.MT_FAILED_MESSAGE]
        )
        module.msg_count = 5
        unwritable = add_fake_module(
            bare_manager, 102, subs=[td.MT_TEST_START], writable=False
        )

        bare_manager.send_ack(module)
        bare_manager.send_hello(unwritable)
        bare_manager.forward_message(
            module, make_header(bare_manager, td.MT_TEST_START, msg_count=9), b""
        )

        received = sent_messages(module)
        assert [h.msg_type for h, _ in received] == [
            cd.MT_ACKNOWLEDGE,
            cd.MT_HELLO,
            cd.MT_FAILED_MESSAGE,
        ]
        assert [h.msg_count for h, _ in received] == [0, 0, 0]
        assert module.msg_count == 5 + 3

    def test_failed_message_reports_sender_msg_count(
        self, bare_manager: MessageManager
    ) -> None:
        src = add_fake_module(bare_manager, 101)
        first = add_fake_module(bare_manager, 102)
        first.msg_count = 40
        unwritable = add_fake_module(bare_manager, 103, writable=False)
        observer = add_fake_module(bare_manager, 104, subs=[cd.MT_FAILED_MESSAGE])
        # A list rather than a set, so the writable module is sent to first and
        # would leave its own count in a shared header before the drop.
        bare_manager.subscriptions[td.MT_TEST_START] = [first, unwritable]  # type: ignore[assignment]
        first.subs.add(td.MT_TEST_START)
        unwritable.subs.add(td.MT_TEST_START)

        bare_manager.forward_message(
            src, make_header(bare_manager, td.MT_TEST_START, msg_count=7), b""
        )

        (header, payload), *_ = sent_messages(observer)
        failed = cd.MDF_FAILED_MESSAGE.from_buffer_copy(payload)
        assert failed.dest_mod_id == 103
        assert failed.msg_header.msg_count == 7
        first_received = sent_messages(first)
        assert [h.msg_count for h, _ in first_received] == [7]
        assert first.msg_count == 41


class TestRunLoop:
    def test_unexpected_error_drops_only_that_client(
        self,
        manager: ManagerHarness,
        client_factory: Callable[..., Client],
        caplog: pytest.LogCaptureFixture,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        sender, observer = watcher(client_factory)
        victim = client_factory()

        def fail(src_module: Module, msg: Message) -> None:
            raise RuntimeError("handler failed")

        monkeypatch.setattr(manager.manager, "register_module_ready", fail)

        victim.send_module_ready()

        assert (
            read_until(
                observer,
                lambda m: m.type_id == cd.MT_GOODBYE
                and m.data.mod_id == victim.module_id,
            )
            is not None
        )
        assert manager.running
        assert_still_routes(sender, observer)
        assert wait_for(
            lambda: any(
                r.exc_info is not None and isinstance(r.exc_info[1], RuntimeError)
                for r in caplog.records
            )
        )


class TestReceiveBuffering:
    def test_message_split_at_every_byte_is_reassembled(
        self, bare_manager: MessageManager
    ) -> None:
        module = add_fake_module(bare_manager, 101)
        payload = bytes(range(24))
        data = raw_message(USER_MSG_TYPE, payload)
        fake_conn(module).feed(*(data[i : i + 1] for i in range(len(data))))

        results = read_until_done(bare_manager, module)

        assert results[:-1] == [None] * (len(results) - 1)
        last = results[-1]
        assert last is not None
        header, received = last
        assert header.msg_type == USER_MSG_TYPE
        assert header.num_data_bytes == len(payload)
        assert received == payload
        assert is_routed(bare_manager, module)

    def test_back_to_back_messages_are_split_at_the_boundary(
        self, bare_manager: MessageManager
    ) -> None:
        module = add_fake_module(bare_manager, 101)
        first = raw_message(USER_MSG_TYPE, b"first")
        second = raw_message(USER_MSG_TYPE + 1, b"second message")
        fake_conn(module).feed(first + second)

        one = read_once(bare_manager, module)
        left_after_one = sum(len(c) for c in fake_conn(module).incoming)
        two = read_once(bare_manager, module)

        assert one is not None and two is not None
        assert (one[0].msg_type, one[1]) == (USER_MSG_TYPE, b"first")
        assert left_after_one == len(second)
        assert (two[0].msg_type, two[1]) == (USER_MSG_TYPE + 1, b"second message")

    def test_interleaved_partial_messages_stay_separate(
        self, bare_manager: MessageManager
    ) -> None:
        a = add_fake_module(bare_manager, 101)
        b = add_fake_module(bare_manager, 102)
        msg_a = raw_message(USER_MSG_TYPE, b"A" * 40)
        msg_b = raw_message(USER_MSG_TYPE, b"B" * 40)

        fake_conn(a).feed(msg_a[:30])
        fake_conn(b).feed(msg_b[:30])
        turns = [read_once(bare_manager, a), read_once(bare_manager, b)]
        fake_conn(a).feed(msg_a[30:70])
        turns.append(read_once(bare_manager, a))
        fake_conn(b).feed(msg_b[30:])
        done_b = read_once(bare_manager, b)
        fake_conn(a).feed(msg_a[70:])
        done_a = read_once(bare_manager, a)

        assert turns == [None, None, None]
        assert done_b is not None and done_b[1] == b"B" * 40
        assert done_a is not None and done_a[1] == b"A" * 40

    @pytest.mark.manager_options(log_level=logging.WARNING)
    def test_spurious_readiness_keeps_client(
        self, bare_manager: MessageManager, caplog: pytest.LogCaptureFixture
    ) -> None:
        module = add_fake_module(bare_manager, 101)

        result = read_once(bare_manager, module)

        assert result is None
        assert is_routed(bare_manager, module)
        assert caplog.records == []

    @pytest.mark.parametrize(
        ("sent", "expected"),
        [(0, "closed by the client"), (20, "after 20 of 48 bytes")],
        ids=["at a boundary", "mid-message"],
    )
    @pytest.mark.manager_options(log_level=logging.WARNING)
    def test_closed_connection_drops_client(
        self,
        bare_manager: MessageManager,
        caplog: pytest.LogCaptureFixture,
        sent: int,
        expected: str,
    ) -> None:
        module = add_fake_module(bare_manager, 101)
        observer = add_fake_module(bare_manager, 102, subs=[cd.MT_GOODBYE])
        fake_conn(module).feed(raw_header(USER_MSG_TYPE, 0)[:sent], b"")

        read_until_done(bare_manager, module)

        assert not is_routed(bare_manager, module)
        assert goodbye_ids(observer) == [101]
        assert any(expected in r.getMessage() for r in caplog.records)


HALF_HEADER = raw_header(USER_MSG_TYPE, 0)[:10]
HEADER_WITHOUT_PAYLOAD = raw_header(USER_MSG_TYPE, 16)


class TestStalls:
    @pytest.mark.parametrize(
        "partial",
        [HALF_HEADER, HEADER_WITHOUT_PAYLOAD],
        ids=["half a header", "header without payload"],
    )
    def test_partial_message_does_not_block_other_clients(
        self,
        manager: ManagerHarness,
        client_factory: Callable[..., Client],
        raw_connection: socket.socket,
        partial: bytes,
    ) -> None:
        raw_connection.sendall(partial)

        sender, observer = watcher(client_factory)

        assert_still_routes(sender, observer)

    @pytest.mark.manager_options(stall_timeout=0.3, log_level=logging.WARNING)
    def test_stalled_client_is_dropped_after_stall_timeout(
        self,
        manager: ManagerHarness,
        client_factory: Callable[..., Client],
        raw_connection: socket.socket,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        sender, observer = watcher(client_factory)
        start = time.monotonic()

        raw_connection.sendall(HEADER_WITHOUT_PAYLOAD)
        assert_closed_by_manager(raw_connection)
        elapsed = time.monotonic() - start

        assert elapsed >= 0.3
        assert wait_for(
            lambda: any(
                "Stalled" in r.getMessage() and "48 of 64 bytes" in r.getMessage()
                for r in caplog.records
            )
        )
        assert_still_routes(sender, observer)

    @pytest.mark.manager_options(stall_timeout=2.0)
    def test_stall_sweep_drops_only_past_the_limit(
        self, bare_manager: MessageManager
    ) -> None:
        stalled = add_fake_module(bare_manager, 101)
        idle = add_fake_module(bare_manager, 102)
        observer = add_fake_module(bare_manager, 103, subs=[cd.MT_GOODBYE])
        fake_conn(stalled).feed(HALF_HEADER)
        before = time.monotonic()
        assert read_once(bare_manager, stalled) is None
        after = time.monotonic()

        bare_manager._drop_stalled(before + 1.9)
        kept = is_routed(bare_manager, stalled)
        bare_manager._drop_stalled(after + 2.0)

        assert kept
        assert not is_routed(bare_manager, stalled)
        assert is_routed(bare_manager, idle)
        assert goodbye_ids(observer) == [101]

    @pytest.mark.manager_options(stall_timeout=None)
    def test_no_stall_timeout_keeps_stalled_client(
        self, bare_manager: MessageManager
    ) -> None:
        stalled = add_fake_module(bare_manager, 101)
        fake_conn(stalled).feed(HALF_HEADER)
        assert read_once(bare_manager, stalled) is None

        bare_manager._drop_stalled(time.monotonic() + 1e6)

        assert is_routed(bare_manager, stalled)


def message_with_payload(
    manager: MessageManager, payload: bytes, msg_type: int = USER_MSG_TYPE
) -> tuple[MessageHeader, bytes]:
    """Build a header for a payload, and the bytes a recipient should get.

    Args:
        manager: The manager, for its header class.
        payload: The message data.
        msg_type: The message type.

    Returns:
        The header, and the header bytes followed by the payload.
    """
    header = make_header(manager, msg_type)
    header.num_data_bytes = len(payload)
    return header, bytes(header) + payload


class TestSending:
    def test_message_is_sent_as_one_buffer(self, bare_manager: MessageManager) -> None:
        src = add_fake_module(bare_manager, 101)
        dest = add_fake_module(bare_manager, 102, subs=[USER_MSG_TYPE])
        payload = bytes(range(16))
        header, expected = message_with_payload(bare_manager, payload)

        bare_manager.forward_message(src, header, payload)

        assert fake_conn(dest).sent == [expected]

    def test_partial_send_is_finished_before_anything_else(
        self, bare_manager: MessageManager
    ) -> None:
        src = add_fake_module(bare_manager, 101)
        dest = add_fake_module(bare_manager, 102, subs=[USER_MSG_TYPE], accept=60)
        observer = add_fake_module(bare_manager, 104, subs=[cd.MT_FAILED_MESSAGE])
        first, first_bytes = message_with_payload(bare_manager, b"\x01" * 100)
        second, _ = message_with_payload(bare_manager, b"\x02" * 100)

        bare_manager.forward_message(src, first, b"\x01" * 100)
        pending_after_first = dest.has_pending
        bare_manager.forward_message(src, second, b"\x02" * 100)
        fake_conn(dest).accept = None
        bare_manager._flush_module(dest)

        assert pending_after_first
        assert not dest.has_pending
        assert b"".join(fake_conn(dest).sent) == first_bytes
        assert dest.drops == 1
        failed = sent_messages(observer)
        assert [h.msg_type for h, _ in failed] == [cd.MT_FAILED_MESSAGE]
        assert is_routed(bare_manager, dest)

    def test_remainder_is_finished_before_the_next_message(
        self, bare_manager: MessageManager
    ) -> None:
        src = add_fake_module(bare_manager, 101)
        dest = add_fake_module(bare_manager, 102, subs=[USER_MSG_TYPE], accept=60)
        first, first_bytes = message_with_payload(bare_manager, b"\x01" * 100)
        second, second_bytes = message_with_payload(bare_manager, b"\x02" * 100)

        bare_manager.forward_message(src, first, b"\x01" * 100)
        fake_conn(dest).accept = None
        bare_manager.forward_message(src, second, b"\x02" * 100)

        assert b"".join(fake_conn(dest).sent) == first_bytes + second_bytes
        assert dest.drops == 0
        assert not dest.has_pending

    def test_ack_waits_behind_a_remainder(self, bare_manager: MessageManager) -> None:
        src = add_fake_module(bare_manager, 101)
        dest = add_fake_module(bare_manager, 102, subs=[USER_MSG_TYPE], accept=60)
        first, _ = message_with_payload(bare_manager, b"\x01" * 100)

        bare_manager.forward_message(src, first, b"\x01" * 100)
        bare_manager.send_ack(dest)
        fake_conn(dest).accept = None
        bare_manager._flush_module(dest)

        received = sent_messages(dest)
        assert [h.msg_type for h, _ in received] == [USER_MSG_TYPE, cd.MT_ACKNOWLEDGE]
        assert dest.drops == 0

    def test_send_error_while_flushing_drops_module(
        self, bare_manager: MessageManager
    ) -> None:
        src = add_fake_module(bare_manager, 101)
        dest = add_fake_module(bare_manager, 102, subs=[USER_MSG_TYPE], accept=60)
        observer = add_fake_module(bare_manager, 103, subs=[cd.MT_GOODBYE])
        first, _ = message_with_payload(bare_manager, b"\x01" * 100)
        bare_manager.forward_message(src, first, b"\x01" * 100)

        fake_conn(dest).fail = True
        bare_manager._flush_module(dest)

        assert not is_routed(bare_manager, dest)
        assert fake_conn(dest).close_count == 1
        assert goodbye_ids(observer) == [102]

    def test_slow_consumer_is_not_dropped(
        self, manager: ManagerHarness, client_factory: Callable[..., Client]
    ) -> None:
        sender, observer = watcher(client_factory, cd.MT_FAILED_MESSAGE)
        slow = client_factory()
        slow.subscribe([td.MT_TEST_MSG_8192])
        big = td.MDF_TEST_MSG_8192()

        # Flood the slow consumer, which doesn't read, until the manager
        # reports a message it couldn't deliver to it.
        seen: list[Message] = []

        def failed_for_slow() -> bool:
            sender.send_message(big)
            msg = observer.read_message(timeout=0)
            while msg is not None:
                seen.append(msg)
                if (
                    msg.type_id == cd.MT_FAILED_MESSAGE
                    and msg.data.dest_mod_id == slow.module_id
                ):
                    return True
                msg = observer.read_message(timeout=0)
            return False

        assert wait_for(failed_for_slow, timeout=30, interval=0)
        assert not any(
            m.type_id == cd.MT_GOODBYE and m.data.mod_id == slow.module_id for m in seen
        )
        assert_still_routes(sender, observer)
        # Its stream is intact: it reads every queued message whole, then gets
        # a new one.
        while slow.read_message(timeout=0.5) is not None:
            pass
        marked = td.MDF_TEST_MSG_8192()
        marked.blob[0] = 7
        received = deliver(sender, slow, marked, match=lambda m: m.data.blob[0] == 7)
        assert received is not None


class TestLoggers:
    def test_logger_gets_whole_message_after_waiting(
        self, bare_manager: MessageManager, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        src = add_fake_module(bare_manager, 101)
        logger = add_fake_module(
            bare_manager, 103, subs=[ALL_MESSAGE_TYPES], is_logger=True, accept=10
        )
        waits: list[float | None] = []

        def wait(module: Module, timeout: float | None) -> bool:
            waits.append(timeout)
            fake_conn(module).accept = None
            return True

        monkeypatch.setattr(bare_manager, "_wait_writable", wait)
        header, expected = message_with_payload(bare_manager, b"\x05" * 100)

        bare_manager.forward_message(src, header, b"\x05" * 100)

        assert waits == [None]
        assert b"".join(fake_conn(logger).sent) == expected
        assert is_routed(bare_manager, logger)

    @pytest.mark.manager_options(logger_timeout=0.25)
    def test_logger_timeout_drops_hung_logger(
        self,
        bare_manager: MessageManager,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        src = add_fake_module(bare_manager, 101)
        dest = add_fake_module(bare_manager, 102, subs=[USER_MSG_TYPE])
        logger = add_fake_module(
            bare_manager,
            103,
            subs=[ALL_MESSAGE_TYPES],
            is_logger=True,
            writable=False,
        )
        observer = add_fake_module(
            bare_manager, 104, subs=[cd.MT_GOODBYE, cd.MT_FAILED_MESSAGE]
        )
        waits: list[float | None] = []

        def wait(module: Module, timeout: float | None) -> bool:
            waits.append(timeout)
            return False

        monkeypatch.setattr(bare_manager, "_wait_writable", wait)
        header, _ = message_with_payload(bare_manager, b"\x05" * 100)

        bare_manager.forward_message(src, header, b"\x05" * 100)

        assert len(waits) == 1
        timeout = waits[0]
        assert timeout is not None and 0 < timeout <= 0.25
        assert not is_routed(bare_manager, logger)
        assert fake_conn(logger).close_count == 1
        assert len(sent_messages(dest)) == 1
        reported = sent_messages(observer)
        assert [h.msg_type for h, _ in reported] == [
            cd.MT_FAILED_MESSAGE,
            cd.MT_GOODBYE,
        ]
        assert any("did not accept" in r.getMessage() for r in caplog.records)

    @pytest.mark.manager_options(logger_timeout=0.5)
    def test_hung_logger_is_dropped_after_logger_timeout(
        self, manager: ManagerHarness, client_factory: Callable[..., Client]
    ) -> None:
        sender, observer = watcher(client_factory)
        hung = client_factory(logger_status=True)
        hung.subscribe([ALL_MESSAGE_TYPES])
        big = td.MDF_TEST_MSG_8192()

        def hung_dropped() -> bool:
            sender.send_message(big)
            msg = observer.read_message(timeout=0)
            while msg is not None:
                if msg.type_id == cd.MT_GOODBYE and msg.data.mod_id == hung.module_id:
                    return True
                msg = observer.read_message(timeout=0)
            return False

        assert wait_for(hung_dropped, timeout=30, interval=0)
        assert_still_routes(sender, observer)


class TestAccept:
    def test_accepted_connections_are_non_blocking(
        self, manager: ManagerHarness, client_factory: Callable[..., Client]
    ) -> None:
        client = client_factory()

        def client_conn() -> socket.socket | None:
            for module in list(manager.manager.modules.values()):
                if module.mod_id == client.module_id:
                    return module.conn
            return None

        assert wait_for(lambda: client_conn() is not None)
        conn = client_conn()
        assert conn is not None
        assert conn.getblocking() is False


class TestCommandLine:
    @pytest.mark.parametrize(
        ("argv", "stall_timeout"),
        [
            ([], DEFAULT_STALL_TIMEOUT),
            (["--stall-timeout", "2.5"], 2.5),
            (["--no-stall-timeout"], None),
        ],
        ids=["default", "set", "disabled"],
    )
    def test_stall_timeout_options(
        self, argv: list[str], stall_timeout: float | None
    ) -> None:
        args = _parse_args(argv)

        assert args.stall_timeout == stall_timeout

    @pytest.mark.parametrize(
        ("argv", "logger_timeout"),
        [([], None), (["--logger-timeout", "3"], 3.0)],
        ids=["default", "set"],
    )
    def test_logger_timeout_option(
        self, argv: list[str], logger_timeout: float | None
    ) -> None:
        args = _parse_args(argv)

        assert args.logger_timeout == logger_timeout

    @pytest.mark.parametrize(
        "argv",
        [
            ["--stall-timeout", "2", "--no-stall-timeout"],
            ["--stall-timeout", "0"],
            ["--logger-timeout", "-1"],
            ["--stall-timeout", "soon"],
        ],
        ids=["both stall options", "zero stall", "negative logger", "not a number"],
    )
    def test_invalid_timeout_options_are_rejected(self, argv: list[str]) -> None:
        with pytest.raises(SystemExit):
            _parse_args(argv)


class TestDropLogging:
    @pytest.mark.parametrize("cause", ["closed", "stalled"])
    @pytest.mark.manager_options(log_level=logging.WARNING)
    def test_dropped_client_is_not_sent_its_drop_warning(
        self, bare_manager: MessageManager, cause: str
    ) -> None:
        dropped = add_fake_module(bare_manager, 101, subs=[cd.MT_RTMA_LOG_WARNING])
        observer = add_fake_module(
            bare_manager, 102, subs=[cd.MT_RTMA_LOG_WARNING, cd.MT_GOODBYE]
        )

        if cause == "closed":
            fake_conn(dropped).feed(b"")
            read_once(bare_manager, dropped)
        else:
            fake_conn(dropped).feed(HALF_HEADER)
            read_once(bare_manager, dropped)
            bare_manager._drop_stalled(time.monotonic() + 1e6)

        assert not is_routed(bare_manager, dropped)
        assert sent_messages(dropped) == []
        assert [h.msg_type for h, _ in sent_messages(observer)] == [
            cd.MT_RTMA_LOG_WARNING,
            cd.MT_GOODBYE,
        ]


class TestConnect:
    def test_rejected_module_id_sends_no_goodbye(
        self, client_factory: Callable[..., Client]
    ) -> None:
        observer = client_factory()
        observer.subscribe([cd.MT_GOODBYE])
        first = client_factory(module_id=50)

        with pytest.raises(ConnectionLost):
            client_factory(module_id=50)
        marker = client_factory()
        marker_id = marker.module_id
        marker.disconnect()

        seen = read_until(
            observer,
            lambda m: m.type_id == cd.MT_GOODBYE and m.data.mod_id == marker_id,
        )
        assert seen is not None
        assert not any(m.type_id == cd.MT_GOODBYE and m.data.mod_id == 50 for m in seen)
        assert first.connected

    @pytest.mark.parametrize(
        "requested",
        [50, cd.DYN_MOD_ID_START + 1, cd.DYN_MOD_ID_START],
        ids=["already in use", "out of range", "first dynamic ID"],
    )
    def test_rejected_module_id_is_not_kept(
        self, bare_manager: MessageManager, requested: int
    ) -> None:
        add_fake_module(bare_manager, 50)
        newcomer = add_fake_module(bare_manager, 0, connected=False)
        observer = add_fake_module(bare_manager, 102, subs=[cd.MT_GOODBYE])
        data = cd.MDF_CONNECT_V2()
        data.mod_id = requested

        accepted = bare_manager.connect_module(
            newcomer, Message(make_header(bare_manager, cd.MT_CONNECT_V2), data)
        )

        assert not accepted
        assert newcomer.mod_id == 0
        assert not is_routed(bare_manager, newcomer)
        assert goodbye_ids(observer) == []

    def test_only_connected_modules_get_a_goodbye(
        self, bare_manager: MessageManager
    ) -> None:
        accepted_only = add_fake_module(bare_manager, 0, connected=False)
        connected = add_fake_module(bare_manager, 101)
        observer = add_fake_module(bare_manager, 102, subs=[cd.MT_GOODBYE])

        bare_manager.remove_module(accepted_only)
        bare_manager.remove_module(connected)

        assert not is_routed(bare_manager, accepted_only)
        assert fake_conn(accepted_only).close_count == 1
        assert goodbye_ids(observer) == [101]


class TestIntroductions:
    def test_introductions_list_only_connected_modules(
        self, bare_manager: MessageManager
    ) -> None:
        requester = add_fake_module(bare_manager, 101, subs=[cd.MT_HELLO])
        add_fake_module(bare_manager, 102)
        add_fake_module(bare_manager, 0, connected=False)

        bare_manager.send_introductions(requester)

        assert sorted(hello_ids(requester)) == [101, 102]

    def test_failed_logger_send_during_introductions(
        self, bare_manager: MessageManager
    ) -> None:
        requester = add_fake_module(bare_manager, 101, subs=[cd.MT_HELLO])
        add_fake_module(bare_manager, 102)
        logger = add_fake_module(
            bare_manager, 103, subs=[ALL_MESSAGE_TYPES], is_logger=True, fail=True
        )

        bare_manager.send_introductions(requester)

        assert is_routed(bare_manager, requester)
        assert not is_routed(bare_manager, logger)
        assert sorted(hello_ids(requester)) == [101, 102]

    def test_failed_requester_send_during_introductions(
        self, bare_manager: MessageManager
    ) -> None:
        requester = add_fake_module(bare_manager, 101, subs=[cd.MT_HELLO], fail=True)
        other = add_fake_module(bare_manager, 102)
        observer = add_fake_module(bare_manager, 103, subs=[cd.MT_GOODBYE])

        bare_manager.send_introductions(requester)

        assert not is_routed(bare_manager, requester)
        assert is_routed(bare_manager, other)
        assert goodbye_ids(observer) == [101]


def handle(manager: MessageManager, module: Module, data: bytes) -> None:
    """Feed a fake module bytes and give it one turn, as ``run()`` does.

    Args:
        manager: A manager that isn't running.
        module: A module made by ``add_fake_module``.
        data: The bytes it sends.
    """
    fake_conn(module).feed(data)
    manager._handle_client(module.conn, module)


def subscribe_message(msg_type: int, unsubscribe: bool = False) -> bytes:
    """Build the bytes of a SUBSCRIBE or UNSUBSCRIBE message.

    Args:
        msg_type: The type to subscribe to or unsubscribe from.
        unsubscribe: Build UNSUBSCRIBE instead.

    Returns:
        The message bytes.
    """
    data = cd.MDF_UNSUBSCRIBE() if unsubscribe else cd.MDF_SUBSCRIBE()
    data.msg_type = msg_type
    return raw_message(
        cd.MT_UNSUBSCRIBE if unsubscribe else cd.MT_SUBSCRIBE, bytes(data)
    )


class TestConnectRequired:
    @pytest.mark.parametrize(
        "msg_type", [cd.MT_SUBSCRIBE, USER_MSG_TYPE, cd.MT_MODULE_READY]
    )
    @pytest.mark.manager_options(log_level=logging.WARNING)
    def test_messages_before_connect_drop_the_socket(
        self,
        manager: ManagerHarness,
        client_factory: Callable[..., Client],
        raw_connection: socket.socket,
        caplog: pytest.LogCaptureFixture,
        msg_type: int,
    ) -> None:
        sender, observer = watcher(client_factory, cd.MT_HELLO, USER_MSG_TYPE)
        payload = {
            cd.MT_SUBSCRIBE: bytes(cd.MDF_SUBSCRIBE()),
            USER_MSG_TYPE: b"data",
            cd.MT_MODULE_READY: bytes(cd.MDF_MODULE_READY()),
        }[msg_type]

        raw_connection.sendall(raw_message(msg_type, payload))

        assert_closed_by_manager(raw_connection)
        seen = read_until_marker(sender, observer)
        assert not any(m.header.src_mod_id == RAW_SRC_MOD_ID for m in seen)
        assert not any(m.type_id == cd.MT_HELLO and m.data.mod_id == 0 for m in seen)
        assert wait_for(
            lambda: any("before CONNECT" in r.getMessage() for r in caplog.records)
        )

    def test_hello_is_not_sent_for_a_socket_that_never_connected(
        self, bare_manager: MessageManager
    ) -> None:
        accepted_only = add_fake_module(bare_manager, 0, connected=False)
        observer = add_fake_module(bare_manager, 102, subs=[cd.MT_HELLO])

        bare_manager.send_hello(accepted_only)

        assert sent_messages(observer) == []


class TestForwardingAfterDrop:
    def test_refused_connect_is_not_forwarded(
        self, bare_manager: MessageManager
    ) -> None:
        add_fake_module(bare_manager, 50)
        newcomer = add_fake_module(bare_manager, 0, connected=False)
        observer = add_fake_module(bare_manager, 102, subs=[cd.MT_CONNECT_V2])
        data = cd.MDF_CONNECT_V2()
        data.mod_id = 50

        handle(bare_manager, newcomer, raw_message(cd.MT_CONNECT_V2, bytes(data)))

        assert not is_routed(bare_manager, newcomer)
        assert sent_messages(observer) == []

    def test_disconnect_is_still_forwarded(self, bare_manager: MessageManager) -> None:
        leaving = add_fake_module(bare_manager, 101)
        observer = add_fake_module(bare_manager, 102, subs=[cd.MT_DISCONNECT])

        handle(bare_manager, leaving, raw_message(cd.MT_DISCONNECT))

        assert not is_routed(bare_manager, leaving)
        assert [h.msg_type for h, _ in sent_messages(observer)] == [cd.MT_DISCONNECT]


class TestAcknowledgements:
    def test_logger_gets_one_ack_per_request(
        self, bare_manager: MessageManager
    ) -> None:
        requester = add_fake_module(
            bare_manager, 101, subs=[ALL_MESSAGE_TYPES], is_logger=True
        )
        other = add_fake_module(
            bare_manager, 102, subs=[ALL_MESSAGE_TYPES], is_logger=True
        )

        handle(bare_manager, requester, subscribe_message(td.MT_TEST_START))

        def acks(module: Module) -> list[int]:
            return [
                h.dest_mod_id
                for h, _ in sent_messages(module)
                if h.msg_type == cd.MT_ACKNOWLEDGE
            ]

        assert acks(requester) == [101]
        assert acks(other) == [101]


class TestSubscriptionTable:
    def test_forwarding_adds_no_entries(self, bare_manager: MessageManager) -> None:
        src = add_fake_module(bare_manager, 101)
        before = set(bare_manager.subscriptions)

        for msg_type in range(20000, 20100):
            bare_manager.forward_message(src, make_header(bare_manager, msg_type), b"")

        assert set(bare_manager.subscriptions) == before

    def test_unsubscribed_types_leave_no_entries(
        self, bare_manager: MessageManager
    ) -> None:
        module = add_fake_module(bare_manager, 101)

        handle(bare_manager, module, subscribe_message(20001))
        handle(bare_manager, module, subscribe_message(20001, unsubscribe=True))
        handle(bare_manager, module, subscribe_message(20002))
        subscribed = 20002 in bare_manager.subscriptions
        bare_manager.remove_module(module)

        assert subscribed
        assert 20001 not in bare_manager.subscriptions
        assert 20002 not in bare_manager.subscriptions


class TestStaticIds:
    def test_highest_static_id_is_accepted(self, bare_manager: MessageManager) -> None:
        newcomer = add_fake_module(bare_manager, 0, connected=False)
        data = cd.MDF_CONNECT_V2()
        data.mod_id = cd.DYN_MOD_ID_START - 1

        accepted = bare_manager.connect_module(
            newcomer, Message(make_header(bare_manager, cd.MT_CONNECT_V2), data)
        )

        assert accepted
        assert newcomer.mod_id == cd.DYN_MOD_ID_START - 1


@contextmanager
def descriptors_above(threshold: int) -> Iterator[None]:
    """Hold open enough descriptors that new ones are numbered above a threshold.

    Args:
        threshold: The descriptor number new ones should exceed.

    Yields:
        Nothing; descriptors opened inside are numbered above ``threshold``.
    """
    base = os.open(os.devnull, os.O_RDONLY)
    held = [base]
    try:
        while held[-1] <= threshold:
            held.append(os.dup(base))
        yield
    finally:
        for fd in held:
            os.close(fd)


posix_only = pytest.mark.skipif(
    sys.platform == "win32", reason="the descriptor limit applies to select() on POSIX"
)


class TestSelectLimits:
    def test_limits_follow_the_platform(self, bare_manager: MessageManager) -> None:
        if sys.platform == "win32":
            assert (bare_manager._max_sockets, bare_manager._max_fd) == (512, None)
        else:
            assert (bare_manager._max_sockets, bare_manager._max_fd) == (None, 1024)

    @pytest.mark.manager_options(log_level=logging.WARNING)
    def test_connection_beyond_socket_limit_is_refused(
        self,
        manager: ManagerHarness,
        client_factory: Callable[..., Client],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        sender, observer = watcher(client_factory)
        manager.manager._max_sockets = 3  # the listener and the two clients

        extra = socket.create_connection(
            (LOOPBACK, manager.port), timeout=DEFAULT_TIMEOUT
        )
        try:
            assert_closed_by_manager(extra)
        finally:
            extra.close()

        assert wait_for(
            lambda: any("limit of 3 sockets" in r.getMessage() for r in caplog.records)
        )
        assert_still_routes(sender, observer)

    @posix_only
    @pytest.mark.manager_options(log_level=logging.WARNING)
    def test_connection_with_high_descriptor_is_refused(
        self,
        manager: ManagerHarness,
        client_factory: Callable[..., Client],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        sender, observer = watcher(client_factory)

        with descriptors_above(1100):
            extra = socket.create_connection(
                (LOOPBACK, manager.port), timeout=DEFAULT_TIMEOUT
            )
            try:
                assert_closed_by_manager(extra)
            finally:
                extra.close()

        assert wait_for(
            lambda: any("select()" in r.getMessage() for r in caplog.records)
        )
        assert manager.running
        assert_still_routes(sender, observer)

    @posix_only
    def test_listening_socket_with_high_descriptor_raises(self) -> None:
        with descriptors_above(1100):
            with pytest.raises(RuntimeError, match="select"):
                MessageManager(ip_address=LOOPBACK, port=0, log_level=logging.ERROR)


class TestModuleLimit:
    def test_limit_is_max_modules(self, bare_manager: MessageManager) -> None:
        assert bare_manager._max_modules == cd.MAX_MODULES == 256

    def test_manager_and_unconnected_sockets_do_not_count(
        self, bare_manager: MessageManager
    ) -> None:
        bare_manager._max_modules = 1
        add_fake_module(bare_manager, 0, connected=False)
        newcomer = add_fake_module(bare_manager, 0, connected=False)

        accepted = bare_manager.connect_module(
            newcomer,
            Message(make_header(bare_manager, cd.MT_CONNECT_V2), cd.MDF_CONNECT_V2()),
        )

        assert accepted

    def test_connect_beyond_the_limit_is_refused(
        self,
        manager: ManagerHarness,
        client_factory: Callable[..., Client],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        sender, observer = watcher(client_factory)
        manager.manager._max_modules = 2

        with pytest.raises(ConnectionLost):
            client_factory()

        assert wait_for(
            lambda: any("limit of 2 modules" in r.getMessage() for r in caplog.records)
        )
        assert_still_routes(sender, observer)
        sender.disconnect()
        assert wait_for(
            lambda: sum(m.connected for m in list(manager.manager.modules.values()))
            == 2  # the manager's own entry and the observer
        )
        assert client_factory().connected


def connect_v2_message(
    name: str, *, pid: int = 0, mod_id: int = 0, logger_status: int = 0
) -> bytes:
    """Build the bytes of a CONNECT_V2 message.

    Args:
        name: The module name.
        pid: The process ID.
        mod_id: The requested module ID, or 0 for a dynamic one.
        logger_status: 1 to connect as a logger.

    Returns:
        The message bytes.
    """
    data = cd.MDF_CONNECT_V2()
    data.name = name
    data.pid = pid
    data.mod_id = mod_id
    data.logger_status = logger_status
    return raw_message(cd.MT_CONNECT_V2, bytes(data))


class TestLateConnectV2:
    def test_connect_v2_after_connect_updates_name_and_pid(
        self, bare_manager: MessageManager
    ) -> None:
        module = add_fake_module(bare_manager, 101)
        observer = add_fake_module(bare_manager, 102, subs=[cd.MT_HELLO])

        handle(bare_manager, module, connect_v2_message("late-name", pid=4321))

        assert is_routed(bare_manager, module)
        assert (module.mod_id, module.name, module.pid) == (101, "late-name", 4321)
        hellos = [
            cd.MDF_HELLO.from_buffer_copy(payload)
            for header, payload in sent_messages(observer)
            if header.msg_type == cd.MT_HELLO
        ]
        assert [(h.mod_id, h.name, h.pid) for h in hellos] == [(101, "late-name", 4321)]
        assert [h.msg_type for h, _ in sent_messages(module)] == []

    def test_connect_after_connect_v2_changes_nothing(
        self, bare_manager: MessageManager
    ) -> None:
        module = add_fake_module(bare_manager, 101)
        observer = add_fake_module(bare_manager, 102, subs=[cd.MT_HELLO])
        data = cd.MDF_CONNECT()
        data.logger_status = 1

        handle(bare_manager, module, raw_message(cd.MT_CONNECT, bytes(data)))

        assert is_routed(bare_manager, module)
        assert (module.mod_id, module.name, module.is_logger) == (101, "fake101", False)
        assert hello_ids(observer) == []
        assert sent_messages(module) == []

    def test_late_connect_v2_keeps_id_and_logger_status(
        self, bare_manager: MessageManager, caplog: pytest.LogCaptureFixture
    ) -> None:
        module = add_fake_module(bare_manager, 101)
        bare_manager.logger.set_all_levels(logging.WARNING)
        bare_manager.logger.enable_console = False

        with caplog.at_level(logging.WARNING):
            handle(
                bare_manager,
                module,
                connect_v2_message("late", mod_id=77, logger_status=1),
            )

        assert (module.mod_id, module.is_logger, module.name) == (101, False, "late")
        assert module not in bare_manager.logger_modules
        warnings = [r.getMessage() for r in caplog.records]
        assert any("77" in text for text in warnings)
        assert any("logger" in text.lower() for text in warnings)

    @pytest.mark.integration
    def test_late_connect_v2_is_announced(
        self,
        raw_connection: socket.socket,
        client_factory: Callable[..., Client],
    ) -> None:
        observer = client_factory()
        observer.subscribe([cd.MT_HELLO, td.MT_TEST_START])
        sender = client_factory()
        assert deliver(sender, observer, td.MDF_TEST_START()) is not None
        # Old clients sent CONNECT first, for managers without CONNECT_V2.
        raw_connection.sendall(raw_message(cd.MT_CONNECT, bytes(cd.MDF_CONNECT())))
        header, _ = recv_message(raw_connection)
        assert header.msg_type == cd.MT_ACKNOWLEDGE

        raw_connection.sendall(connect_v2_message("late-name", pid=4321))

        seen = read_until(
            observer,
            lambda m: m.type_id == cd.MT_HELLO
            and m.data.mod_id == RAW_SRC_MOD_ID
            and m.data.name == "late-name",
        )
        assert seen is not None
        assert seen[-1].data.pid == 4321
