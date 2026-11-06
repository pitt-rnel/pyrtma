"""Tests for ``pyrtma.client``: signatures, receiving, and lost connections."""

from __future__ import annotations

import gc
import itertools
import select
import socket
import sys
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

import pytest

from pyrtma import core_defs as cd
from pyrtma.client import Client, client_context
from pyrtma.exceptions import (
    ConnectionLost,
    InvalidMessageDefinition,
    UnknownMessageType,
)
from pyrtma.header import MessageHeader

from .helpers import (
    DEFAULT_TIMEOUT,
    HEADER_SIZE,
    ManagerHarness,
    ScriptedManager,
    bytes_waiting,
    frame,
    wait_for,
)
from .test_msg_defs import test_defs as td

# How much later than its timeout a read may return before a test fails. Wide,
# because CI machines can be slow; the bugs these tests catch block for far
# longer.
SLACK: float = 1.0

# A message type the test definitions don't define.
UNKNOWN_TYPE: int = 7777

# The largest payload the client accepts; the message manager's limit.
MAX_DATA_BYTES: int = 1024**2


@pytest.mark.parametrize(
    ("factory", "args"),
    [
        (Client, (0, 0, "name")),
        (client_context, (0, "127.0.0.1:7111", None, 0, False)),
    ],
    ids=["Client", "client_context"],
)
def test_options_after_host_id_are_keyword_only(
    factory: Any, args: tuple[Any, ...]
) -> None:
    with pytest.raises(TypeError):
        factory(*args)


@pytest.mark.parametrize("factory", [Client, client_context])
def test_timecode_argument_is_rejected(factory: Any) -> None:
    with pytest.raises(TypeError, match="timecode"):
        factory(timecode=True)


@pytest.mark.parametrize("module_id", [-1, cd.DYN_MOD_ID_START])
def test_failed_constructor_leaves_no_unraisable_exception(
    monkeypatch: pytest.MonkeyPatch, module_id: int
) -> None:
    unraisable: list[Any] = []
    monkeypatch.setattr(sys, "unraisablehook", unraisable.append)

    with pytest.raises(ValueError):
        Client(module_id=module_id)
    gc.collect()

    assert unraisable == []


def start_message(test_id: int) -> bytes:
    """Build a ``TEST_START`` message as the manager sends it.

    Args:
        test_id: The value of its ``id`` field.

    Returns:
        The message's bytes.
    """
    data = td.MDF_TEST_START()
    data.id = test_id
    return frame(td.MT_TEST_START, bytes(data))


def unknown_message() -> bytes:
    """Build a message of a type the test definitions don't define.

    Returns:
        The message's bytes, with a 4-byte payload.
    """
    return frame(UNKNOWN_TYPE, b"\x00" * 4)


@pytest.fixture
def scripted_client(scripted_manager: ScriptedManager) -> Iterator[Client]:
    """A client connected to the ``scripted_manager`` stand-in.

    It uses the compiled test definitions and doesn't print its log.

    Args:
        scripted_manager: The stand-in to connect to.

    Yields:
        The connected client, disconnected at teardown.
    """
    client = Client(name="scripted", definitions=td.get_message_definitions())
    client.logger.enable_console = False
    scripted_manager.connect(client)
    try:
        yield client
    finally:
        client.disconnect()


@contextmanager
def watchdog(stand_in: ScriptedManager, seconds: float = 3.0) -> Iterator[None]:
    """Reset the stand-in's connection if the body is still running after a while.

    A read that blocks on a partial message would otherwise hang the test
    until pytest's timeout. With this, it fails within a few seconds, with
    ``ConnectionLost``.

    Args:
        stand_in: The stand-in whose connection to reset.
        seconds: How long the body may run.

    Yields:
        Nothing; the body runs under the watchdog.
    """
    timer = threading.Timer(seconds, stand_in.reset)
    timer.start()
    try:
        yield
    finally:
        timer.cancel()
        timer.join()


def wait_until_arrived(client: Client, nbytes: int) -> None:
    """Wait until ``nbytes`` the stand-in sent are waiting on the client's socket.

    Args:
        client: The receiving client.
        nbytes: How many bytes were sent.
    """
    assert wait_for(lambda: bytes_waiting(client.sock, nbytes))


def readable(client: Client) -> bool:
    """Whether the client's socket has something to read, or an error to report.

    Args:
        client: The client to look at.

    Returns:
        True if a read wouldn't wait.
    """
    ready, _, _ = select.select([client.sock], [], [], 0)
    return bool(ready)


@pytest.mark.integration
class TestReceive:
    def test_unsubscribed_stream_does_not_extend_timeout(
        self, scripted_client: Client, scripted_manager: ScriptedManager
    ) -> None:
        scripted_client.subscribe([td.MT_TEST_START])
        stop = threading.Event()
        ends = time.monotonic() + 3.0

        def trickle() -> None:
            # An ACK every 50 ms for 3 s: each one arrives before a 0.3 s
            # timeout would end, if the timeout started again with each.
            while not stop.wait(0.05) and time.monotonic() < ends:
                scripted_manager.send(frame(cd.MT_ACKNOWLEDGE))

        feeder = threading.Thread(target=trickle, daemon=True)
        feeder.start()
        try:
            start = time.monotonic()
            received = scripted_client.read_message(timeout=0.3)
            elapsed = time.monotonic() - start
        finally:
            stop.set()
            feeder.join(DEFAULT_TIMEOUT)

        assert received is None
        assert elapsed < 0.3 + SLACK

    @pytest.mark.parametrize("timeout", [0, 0.2])
    @pytest.mark.parametrize(
        "split", [HEADER_SIZE // 2, HEADER_SIZE + 2], ids=["in_header", "in_payload"]
    )
    def test_partial_message_does_not_block_past_timeout(
        self,
        scripted_client: Client,
        scripted_manager: ScriptedManager,
        timeout: float,
        split: int,
    ) -> None:
        scripted_client.subscribe([td.MT_TEST_START])
        scripted_manager.send(start_message(1)[:split])
        wait_until_arrived(scripted_client, split)

        with watchdog(scripted_manager):
            start = time.monotonic()
            received = scripted_client.read_message(timeout=timeout)
            elapsed = time.monotonic() - start

        assert received is None
        assert elapsed < timeout + SLACK

    @pytest.mark.parametrize(
        "split", [HEADER_SIZE // 2, HEADER_SIZE + 2], ids=["in_header", "in_payload"]
    )
    def test_partial_message_completes_on_a_later_read(
        self, scripted_client: Client, scripted_manager: ScriptedManager, split: int
    ) -> None:
        scripted_client.subscribe([td.MT_TEST_START])
        wire = start_message(7)
        scripted_manager.send(wire[:split])
        wait_until_arrived(scripted_client, split)
        with watchdog(scripted_manager):
            first = scripted_client.read_message(timeout=0)

        scripted_manager.send(wire[split:])
        second = scripted_client.read_message(timeout=DEFAULT_TIMEOUT)

        assert first is None
        assert second is not None
        assert second.type_id == td.MT_TEST_START
        assert second.data.id == 7

    @pytest.mark.parametrize("timeout", [None, -1])
    def test_blocking_read_waits_for_a_message(
        self,
        scripted_client: Client,
        scripted_manager: ScriptedManager,
        timeout: float | None,
    ) -> None:
        scripted_client.subscribe([td.MT_TEST_START])
        sender = threading.Timer(0.2, scripted_manager.send, args=(start_message(3),))
        sender.start()
        try:
            received = scripted_client.read_message(timeout=timeout)
        finally:
            sender.cancel()
            sender.join()

        assert received is not None
        assert received.data.id == 3

    def test_poll_reads_at_most_one_message(
        self, scripted_client: Client, scripted_manager: ScriptedManager
    ) -> None:
        scripted_client.subscribe([td.MT_TEST_START])
        wire = frame(cd.MT_ACKNOWLEDGE) + start_message(4)
        scripted_manager.send(wire)
        wait_until_arrived(scripted_client, len(wire))

        first = scripted_client.read_message(timeout=0)
        second = scripted_client.read_message(timeout=0)

        assert first is None
        assert second is not None
        assert second.data.id == 4

    def test_unsubscribed_message_of_unknown_type_is_skipped(
        self, scripted_client: Client, scripted_manager: ScriptedManager
    ) -> None:
        scripted_client.subscribe([td.MT_TEST_START])
        scripted_manager.send(unknown_message() + start_message(5))

        received = scripted_client.read_message(timeout=DEFAULT_TIMEOUT)

        assert received is not None
        assert received.data.id == 5

    def test_subscribed_message_of_unknown_type_raises(
        self, scripted_client: Client, scripted_manager: ScriptedManager
    ) -> None:
        scripted_client.subscribe([UNKNOWN_TYPE, td.MT_TEST_START])
        scripted_manager.send(unknown_message() + start_message(6))

        with pytest.raises(UnknownMessageType) as raised:
            scripted_client.read_message(timeout=DEFAULT_TIMEOUT)
        after = scripted_client.read_message(timeout=DEFAULT_TIMEOUT)

        assert raised.value.args[2] == b"\x00" * 4
        assert after is not None
        assert after.data.id == 6

    def test_subscribed_message_of_wrong_size_raises(
        self, scripted_client: Client, scripted_manager: ScriptedManager
    ) -> None:
        scripted_client.subscribe([td.MT_TEST_START])
        scripted_manager.send(frame(td.MT_TEST_START, b"\x00" * 8) + start_message(9))

        with pytest.raises(InvalidMessageDefinition, match="data size"):
            scripted_client.read_message(timeout=DEFAULT_TIMEOUT)
        after = scripted_client.read_message(timeout=DEFAULT_TIMEOUT)

        assert after is not None
        assert after.data.id == 9

    def test_discard_messages_empties_the_queue(
        self, scripted_client: Client, scripted_manager: ScriptedManager
    ) -> None:
        scripted_client.subscribe([td.MT_TEST_START])
        wire = (frame(cd.MT_ACKNOWLEDGE) + start_message(1) + unknown_message()) * 10
        scripted_manager.send(wire)
        wait_until_arrived(scripted_client, len(wire))

        emptied = scripted_client.discard_messages()

        assert emptied is True
        assert not readable(scripted_client)

    def test_discard_messages_reports_messages_left_at_its_timeout(
        self, scripted_client: Client, scripted_manager: ScriptedManager
    ) -> None:
        wire = frame(cd.MT_ACKNOWLEDGE) * 200
        scripted_manager.send(wire)
        wait_until_arrived(scripted_client, len(wire))

        first = scripted_client.discard_messages(timeout=0)
        second = scripted_client.discard_messages()

        assert first is False
        assert second is True
        assert not readable(scripted_client)

    def test_reset_subscriptions_leaves_nothing_queued(
        self, scripted_client: Client, scripted_manager: ScriptedManager
    ) -> None:
        # The stand-in doesn't ACK the unsubscribes, so anything still
        # queued afterwards was there before the reset.
        scripted_client.subscribe([td.MT_TEST_START])
        wire = (frame(cd.MT_ACKNOWLEDGE) + start_message(2)) * 25
        scripted_manager.send(wire)
        wait_until_arrived(scripted_client, len(wire))

        scripted_client.reset_subscriptions()

        assert scripted_client.subscribed_types == set()
        assert not readable(scripted_client)

    @pytest.mark.parametrize("end", ["close", "reset", "close_mid_message"])
    def test_lost_connection_marks_client_disconnected(
        self, scripted_client: Client, scripted_manager: ScriptedManager, end: str
    ) -> None:
        scripted_client.subscribe([td.MT_TEST_START])
        if end == "close_mid_message":
            scripted_manager.send(start_message(1)[: HEADER_SIZE + 2])
        if end == "reset":
            scripted_manager.reset()
        else:
            scripted_manager.close()

        with pytest.raises(ConnectionLost):
            scripted_client.read_message(timeout=DEFAULT_TIMEOUT)

        assert scripted_client.connected is False
        assert scripted_client.sock.fileno() == -1
        assert scripted_client.subscribed_types == set()

    def test_send_after_reset_marks_client_disconnected(
        self, scripted_client: Client, scripted_manager: ScriptedManager
    ) -> None:
        scripted_manager.reset()
        assert wait_for(lambda: readable(scripted_client))

        with pytest.raises(ConnectionLost):
            scripted_client.send_message(td.MDF_TEST_START())

        assert scripted_client.connected is False
        assert scripted_client.sock.fileno() == -1

    @pytest.mark.parametrize("size", [-1, MAX_DATA_BYTES + 1])
    def test_corrupt_header_drops_the_connection(
        self, scripted_client: Client, scripted_manager: ScriptedManager, size: int
    ) -> None:
        scripted_manager.send(frame(td.MT_TEST_START, num_data_bytes=size))

        with watchdog(scripted_manager):
            with pytest.raises(ConnectionLost, match=f"num_data_bytes.*{size}"):
                scripted_client.read_message(timeout=DEFAULT_TIMEOUT)

        assert scripted_client.connected is False

    def test_payload_limit_matches_the_manager(self, manager: ManagerHarness) -> None:
        assert len(manager.manager.data_buffer) == MAX_DATA_BYTES

    def test_reconnect_discards_partial_message(
        self, scripted_client: Client, scripted_manager: ScriptedManager
    ) -> None:
        scripted_client.subscribe([td.MT_TEST_START])
        scripted_manager.send(start_message(1)[: HEADER_SIZE // 2])
        wait_until_arrived(scripted_client, HEADER_SIZE // 2)
        with watchdog(scripted_manager):
            stale = scripted_client.read_message(timeout=0)
        second = ScriptedManager()
        try:
            second.connect(scripted_client)
            scripted_client.subscribe([td.MT_TEST_START])
            second.send(start_message(8))

            received = scripted_client.read_message(timeout=DEFAULT_TIMEOUT)
        finally:
            second.stop()

        assert stale is None
        assert received is not None
        assert received.data.id == 8


@pytest.mark.integration
class TestSend:
    def test_send_waits_for_room_in_the_socket(self) -> None:
        # Small buffers at both ends and 33 MB of messages: sends find the
        # socket full many times, and must wait and carry on, not fail.
        count = 4000
        size = HEADER_SIZE + td.MDF_TEST_MSG_8192.type_size
        stand_in = ScriptedManager(receive_buffer=4096)
        client = Client(name="sender", definitions=td.get_message_definitions())
        client.logger.enable_console = False
        try:
            stand_in.connect(client)
            client.sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
            msg = td.MDF_TEST_MSG_8192()
            msg.blob[0] = 255
            sender = threading.Thread(
                target=lambda: [client.send_message(msg) for _ in range(count)],
                daemon=True,
            )

            sender.start()
            received = stand_in.receive(count * size)
            sender.join(DEFAULT_TIMEOUT)
        finally:
            client.disconnect()
            stand_in.stop()

        assert not sender.is_alive()
        for offset in range(0, len(received), size):
            header = MessageHeader.from_buffer_copy(received, offset)
            assert header.msg_type == td.MT_TEST_MSG_8192
            assert header.num_data_bytes == td.MDF_TEST_MSG_8192.type_size
            assert received[offset + HEADER_SIZE] == 255


# Message types for the subscription tests. The manager forwards types it
# doesn't know, and nothing is sent of these, so they needn't be defined.
A, B, C, D, E = 7001, 7002, 7003, 7004, 7005

_sync_names = itertools.count()


def manager_subscriptions(manager: ManagerHarness, client: Client) -> set[int]:
    """The manager's subscriptions for a client, after it has acted on all it sent.

    The manager handles each client's messages in order, so once it has
    taken a ``CLIENT_SET_NAME`` with a fresh name, every subscription message
    the client sent before it has been handled too.

    Args:
        manager: The running manager.
        client: A client connected to it.

    Returns:
        The message types the manager has the client subscribed to.
    """
    token = f"sync-{next(_sync_names)}"
    msg = cd.MDF_CLIENT_SET_NAME()
    msg.name = token
    client.send_message(msg)
    module = next(
        m
        for m in list(manager.manager.modules.values())
        if m.mod_id == client.module_id
    )
    assert wait_for(lambda: module.name == token)
    return set(module.subs)


@pytest.mark.integration
class TestSubscriptions:
    def test_generator_subscribes_every_type(
        self, manager: ManagerHarness, client_factory: Callable[..., Client]
    ) -> None:
        client = client_factory()

        client.subscribe(mt for mt in [A, B, C])

        assert client.subscribed_types == {A, B, C}
        assert manager_subscriptions(manager, client) == {A, B, C}

    @pytest.mark.parametrize("method", ["unsubscribe", "pause_subscription"])
    def test_generator_removes_every_type(
        self,
        manager: ManagerHarness,
        client_factory: Callable[..., Client],
        method: str,
    ) -> None:
        client = client_factory()
        client.subscribe([A, B, C])

        getattr(client, method)(mt for mt in [A, B])

        assert client.subscribed_types == {C}
        assert manager_subscriptions(manager, client) == {C}

    def test_generator_resumes_every_type(
        self, manager: ManagerHarness, client_factory: Callable[..., Client]
    ) -> None:
        client = client_factory()
        client.subscribe([A, B])
        client.pause_subscription([A, B])

        client.resume_subscription(mt for mt in [A, B])

        assert client.subscribed_types == {A, B}
        assert client.paused_subscribed_types == set()
        assert manager_subscriptions(manager, client) == {A, B}

    def test_subscription_context_keeps_existing_subscriptions(
        self, manager: ManagerHarness, client_factory: Callable[..., Client]
    ) -> None:
        client = client_factory()
        client.subscribe([A, B, C])

        with pytest.warns(UserWarning, match="already subscribed"):
            with client.subscription_context([A, B, C, D]):
                inside = client.subscribed_types

        assert inside == {A, B, C, D}
        assert client.subscribed_types == {A, B, C}
        assert manager_subscriptions(manager, client) == {A, B, C}

    def test_subscription_context_restores_after_exception(
        self, manager: ManagerHarness, client_factory: Callable[..., Client]
    ) -> None:
        client = client_factory()
        client.subscribe([A])

        with pytest.raises(RuntimeError, match="body"):
            with client.subscription_context([B]):
                raise RuntimeError("body")

        assert client.subscribed_types == {A}
        assert manager_subscriptions(manager, client) == {A}

    def test_subscription_context_for_all_types_restores_previous_ones(
        self, manager: ManagerHarness, client_factory: Callable[..., Client]
    ) -> None:
        client = client_factory()
        client.subscribe([A, B])
        client.pause_subscription([B])

        with client.subscription_context([cd.ALL_MESSAGE_TYPES]):
            inside = client.subscribed_types

        assert inside == {cd.ALL_MESSAGE_TYPES}
        assert client.subscribed_types == {A}
        assert client.paused_subscribed_types == {B}
        assert manager_subscriptions(manager, client) == {A}

    def test_paused_subscription_context_restores_after_exception(
        self, manager: ManagerHarness, client_factory: Callable[..., Client]
    ) -> None:
        client = client_factory()
        client.subscribe([A, B])

        with pytest.raises(RuntimeError, match="body"):
            with client.paused_subscription_context([A]):
                raise RuntimeError("body")

        assert client.subscribed_types == {A, B}
        assert client.paused_subscribed_types == set()
        assert manager_subscriptions(manager, client) == {A, B}

    def test_paused_subscription_context_ignores_every_unsubscribed_type(
        self, manager: ManagerHarness, client_factory: Callable[..., Client]
    ) -> None:
        # B and D come first: removing B while iterating skipped D, which was
        # then paused and, on exit, subscribed.
        client = client_factory()
        client.subscribe([A])

        with pytest.warns(UserWarning, match="not subscribed"):
            with client.paused_subscription_context([B, D, A]):
                inside = client.subscribed_types

        assert inside == set()
        assert client.subscribed_types == {A}
        assert client.paused_subscribed_types == set()
        assert manager_subscriptions(manager, client) == {A}

    def test_contexts_leave_changes_the_body_made(
        self, manager: ManagerHarness, client_factory: Callable[..., Client]
    ) -> None:
        client = client_factory()
        client.subscribe([A])

        with client.subscription_context([B]):
            client.unsubscribe([B])
            client.subscribe([E])
        with client.paused_subscription_context([A]):
            client.resume_subscription([A])
            client.unsubscribe([A])

        assert client.subscribed_types == {E}
        assert client.paused_subscribed_types == set()
        assert manager_subscriptions(manager, client) == {E}

    @pytest.mark.parametrize(
        "context", ["subscription_context", "paused_subscription_context"]
    )
    def test_context_exit_after_disconnect_does_not_raise(
        self, client_factory: Callable[..., Client], context: str
    ) -> None:
        client = client_factory()
        client.subscribe([A])

        # The paused context pauses A; the other subscribes to B.
        with getattr(client, context)([A] if context.startswith("paused") else [B]):
            client.disconnect()

        assert client.connected is False

    def test_pause_and_resume_of_all_types_round_trips(
        self, manager: ManagerHarness, client_factory: Callable[..., Client]
    ) -> None:
        client = client_factory()
        client.subscribe([cd.ALL_MESSAGE_TYPES])

        client.pause_subscription([cd.ALL_MESSAGE_TYPES])
        paused = client.paused_subscribed_types
        paused_at_manager = manager_subscriptions(manager, client)
        client.resume_all_subscriptions()

        assert paused == {cd.ALL_MESSAGE_TYPES}
        assert paused_at_manager == set()
        assert client.subscribed_types == {cd.ALL_MESSAGE_TYPES}
        assert manager_subscriptions(manager, client) == {cd.ALL_MESSAGE_TYPES}

    def test_pausing_all_types_pauses_individual_subscriptions(
        self, manager: ManagerHarness, client_factory: Callable[..., Client]
    ) -> None:
        client = client_factory()
        client.subscribe([A, B])

        client.pause_subscription([cd.ALL_MESSAGE_TYPES])
        paused = client.paused_subscribed_types
        paused_at_manager = manager_subscriptions(manager, client)
        client.resume_all_subscriptions()

        assert paused == {A, B}
        assert paused_at_manager == set()
        assert client.subscribed_types == {A, B}
        assert manager_subscriptions(manager, client) == {A, B}

    def test_unsubscribe_from_all_forgets_paused_types(
        self, manager: ManagerHarness, client_factory: Callable[..., Client]
    ) -> None:
        client = client_factory()
        client.subscribe([A, B])
        client.pause_subscription([A])

        client.unsubscribe_from_all()
        client.resume_all_subscriptions()

        assert client.subscribed_types == set()
        assert client.paused_subscribed_types == set()
        assert manager_subscriptions(manager, client) == set()
