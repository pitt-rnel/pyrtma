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
import socket
from collections.abc import Callable, Iterable, Iterator
from typing import Any, cast

import pytest

from pyrtma import core_defs as cd
from pyrtma.client import Client
from pyrtma.header import MessageHeader, get_header_cls
from pyrtma.manager import MessageManager, Module
from pyrtma.message import Message

from .helpers import DEFAULT_TIMEOUT, LOOPBACK, ManagerHarness, deliver, wait_for
from .test_msg_defs import test_defs as td

pytestmark = pytest.mark.integration

# The src_mod_id that raw connections put in their headers, so their messages
# can be told apart from the clients' own.
RAW_SRC_MOD_ID = 123


class FakeConnection:
    """Stands in for a client socket that the manager writes to.

    A healthy connection records what is sent. A failing one raises
    ``ConnectionResetError``, as a socket does after the peer resets, and any
    connection raises ``OSError(EBADF)`` once it's closed, as a real one does.
    """

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[bytes] = []
        self.close_count = 0

    def sendall(self, data: Any) -> None:
        if self.close_count:
            raise OSError(errno.EBADF, "Bad file descriptor")
        if self.fail:
            raise ConnectionResetError(errno.ECONNRESET, "Connection reset by peer")
        self.sent.append(bytes(data))

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
def bare_manager() -> Iterator[MessageManager]:
    """A manager that is constructed but never run, for driving its methods.

    Yields:
        The manager. Its listening socket is closed at teardown.
    """
    manager = MessageManager(ip_address=LOOPBACK, port=0, log_level=logging.ERROR)
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
    is_logger: bool = False,
) -> Module:
    """Register a connected module on a fake connection, as ``run()`` would.

    Args:
        manager: The manager to add the module to.
        mod_id: The module's ID.
        subs: Message types it subscribes to.
        fail: Whether sends to it raise ``ConnectionResetError``.
        writable: Whether it is in the manager's writable list.
        is_logger: Whether it registered as a logger.

    Returns:
        The new module.
    """
    # The manager only calls sendall() and close(), so the fake can stand in.
    conn = cast(socket.socket, FakeConnection(fail=fail))
    module = Module(
        conn,
        (LOOPBACK, 20000 + mod_id),
        manager.header_cls,
        name=f"fake{mod_id}",
        mod_id=mod_id,
        connected=True,
        is_logger=is_logger,
    )
    manager.modules[conn] = module
    manager.sockets.append(conn)
    for msg_type in subs:
        manager.subscriptions[msg_type].add(module)
        module.subs.add(msg_type)
    if is_logger:
        manager.logger_modules.add(module)
    if writable:
        manager.wlist.append(conn)
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


def raw_header(manager: ManagerHarness, msg_type: int, num_data_bytes: int) -> bytes:
    """Build the bytes of a header as a raw client would send it.

    Args:
        manager: The running harness, for its header type.
        msg_type: The message type.
        num_data_bytes: The data size the header announces.

    Returns:
        The header bytes.
    """
    header = get_header_cls(manager.timecode)()
    header.msg_type = msg_type
    header.src_mod_id = RAW_SRC_MOD_ID
    header.num_data_bytes = num_data_bytes
    return bytes(header)


def is_goodbye_for_port(port: int) -> Callable[[Message], bool]:
    """Match the ``GOODBYE`` the manager sends when a connection is dropped.

    Args:
        port: The dropped connection's local port.

    Returns:
        A predicate for ``read_until``.
    """
    return lambda msg: msg.type_id == cd.MT_GOODBYE and msg.data.port == port


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

    Args:
        sender: A connected client.
        observer: A client subscribed to ``TEST_START``.
    """
    msg = td.MDF_TEST_START()
    msg.id = 7
    received = deliver(sender, observer, msg)
    assert received is not None
    assert received.data.id == 7


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
        raw_port = raw_connection.getsockname()[1]

        raw_connection.sendall(raw_header(manager, td.MT_TEST_END, data_size))

        assert read_until(observer, is_goodbye_for_port(raw_port)) is not None
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
        raw_port = raw_connection.getsockname()[1]

        raw_connection.sendall(raw_header(manager, msg_type, data_size))
        raw_connection.sendall(bytes(data_size))

        seen = read_until(observer, is_goodbye_for_port(raw_port))
        assert seen is not None
        assert_closed_by_manager(raw_connection)
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

        raw_connection.sendall(raw_header(manager, cd.MT_DATASET_START, size))
        raw_connection.sendall(bytes(size))

        seen = read_until(
            observer,
            lambda m: m.type_id == cd.MT_DATASET_START
            and m.header.src_mod_id == RAW_SRC_MOD_ID,
        )
        assert seen is not None
        assert not any(m.type_id == cd.MT_GOODBYE for m in seen)


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
