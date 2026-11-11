"""Tests for ``pyrtma.data_logger.data_logger``: a real logger and manager.

The logger runs in a thread against the ``manager`` fixture, with a
``FakeClock`` for its datasets' write schedules. A ``controller`` client
sends requests and reads the logger's replies, as the CLI or a lab module
would.
"""

from __future__ import annotations

import errno
import json
import logging
import sys
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, ClassVar

import pytest

from pyrtma import core_defs as cd
from pyrtma.client import Client
from pyrtma.data_logger import data_formatter
from pyrtma.data_logger import data_logger as data_logger_module
from pyrtma.data_logger.__main__ import main
from pyrtma.data_logger.data_formatter import DataFormatter
from pyrtma.data_logger.data_logger import DataLogger
from pyrtma.data_logger.dataset import Dataset
from pyrtma.data_logger.dataset_writer import DatasetWriter
from pyrtma.exceptions import MessageManagerNotFound
from pyrtma.utils.raw_reader import RawFile
from pyrtma.message import Message
from pyrtma.message_base import MessageMeta
from pyrtma.message_data import MessageData
from pyrtma.validators import Int32

from .helpers import DEFAULT_TIMEOUT, FakeClock, ManagerHarness, read_until, wait_for
from .test_msg_defs import test_defs as td

pytestmark = pytest.mark.integration

# A type the test definitions don't define.
UNKNOWN_TYPE: int = 7777

# The types a dataset reports about itself.
DATASET_EVENTS: tuple[int, ...] = (
    cd.MT_DATA_LOGGER_ERROR,
    cd.MT_DATASET_STARTED,
    cd.MT_DATASET_STOPPED,
    cd.MT_DATASET_SAVED,
    cd.MT_DATASET_REMOVED,
)


class StaleTestStart(MessageData, metaclass=MessageMeta):
    """``TEST_START`` as an out-of-date definition has it: 8 bytes, not 4."""

    type_id: ClassVar[int] = td.MT_TEST_START
    type_name: ClassVar[str] = "TEST_START"
    type_hash: ClassVar[int] = 0
    type_size: ClassVar[int] = 8
    type_source: ClassVar[str] = "test_data_logger"
    type_def: ClassVar[str] = ""

    id: Int32 = Int32()
    extra: Int32 = Int32()


class UnknownMessage(MessageData, metaclass=MessageMeta):
    """A type that the logger's definitions don't have."""

    type_id: ClassVar[int] = UNKNOWN_TYPE
    type_name: ClassVar[str] = "UNKNOWN"
    type_hash: ClassVar[int] = 0
    type_size: ClassVar[int] = 4
    type_source: ClassVar[str] = "test_data_logger"
    type_def: ClassVar[str] = ""

    value: Int32 = Int32()


class FullDiskFormatter(DataFormatter):
    """A formatter whose writes fail as on a full disk."""

    name: ClassVar[str] = "full_disk"
    mode: ClassVar[str] = "wt"
    ext: ClassVar[str] = ".txt"

    def write(self, wbuf: list[Message]) -> None:
        raise OSError(errno.ENOSPC, "No space left on device")


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def data_logger(manager: ManagerHarness, clock: FakeClock) -> Iterator[DataLogger]:
    """A data logger running in a thread, stopped at teardown.

    If ``run()`` raises, the ``thread_exceptions`` fixture fails the test.

    Yields:
        The logger.
    """
    logger = DataLogger(
        manager.address,
        logging.INFO,
        definitions=td.get_message_definitions(),
        clock=clock,
    )
    thread = threading.Thread(target=logger.run, name="data-logger", daemon=True)
    thread.start()
    yield logger
    logger.stop()
    thread.join(DEFAULT_TIMEOUT)
    assert not thread.is_alive(), "the data logger didn't stop"


def wait_for_logger(client: Client) -> None:
    """Wait until the logger answers ``client``.

    The reply shows that the logger's subscriptions and ``client``'s are in
    place, since each client's messages reach the manager in order.
    """

    def answered() -> bool:
        client.send_signal(cd.MT_DATA_LOGGER_CONFIG_REQUEST)
        reply = read_until(client, is_type(cd.MT_DATA_LOGGER_CONFIG), timeout=0.2)
        return reply is not None

    assert wait_for(answered, interval=0), "the data logger never answered"


@pytest.fixture
def controller(
    client_factory: Callable[..., Client], data_logger: DataLogger
) -> Client:
    client = client_factory(name="controller")
    client.subscribe(Dataset.DATALOGGER_TYPES)
    wait_for_logger(client)
    return client


def is_type(msg_type: int, name: str | None = None) -> Callable[[Message], bool]:
    """Match a message by type, and by dataset name if given."""

    def check(msg: Message) -> bool:
        return msg.type_id == msg_type and (name is None or dataset_of(msg) == name)

    return check


def dataset_of(msg: Message) -> str:
    """The dataset a data logger message is about."""
    if msg.type_id == cd.MT_DATA_LOGGER_ERROR:
        return msg.data.dataset_name
    return getattr(msg.data, "name", "")


def wait_reply(client: Client, msg_type: int, name: str | None = None) -> list[Message]:
    """Read until a message of a type, for a dataset if given, arrives.

    Returns:
        Every message read, ending with that one.
    """
    seen = read_until(client, is_type(msg_type, name))
    assert seen is not None, f"no message of type {msg_type} for {name!r}"
    return seen


def events(messages: list[Message], name: str) -> list[int]:
    """The types of the dataset events about one dataset, in order."""
    return [
        m.type_id
        for m in messages
        if m.type_id in DATASET_EVENTS and dataset_of(m) == name
    ]


def add_request(
    name: str,
    save_path: Path,
    *,
    filename: str = "rec",
    formatter: str = "json",
    msg_types: tuple[int, ...] = (cd.ALL_MESSAGE_TYPES,),
    max_size_mb: int = cd.DATASET_MAX_SIZE_MB,
) -> cd.MDF_DATASET_ADD:
    msg = cd.MDF_DATASET_ADD()
    msg.dataset.max_size_mb = max_size_mb
    msg.dataset.name = name
    msg.dataset.save_path = str(save_path)
    msg.dataset.filename = filename
    msg.dataset.formatter = formatter
    msg.dataset.msg_types[: len(msg_types)] = msg_types
    return msg


def named(msg_cls: type[Any], name: str) -> Any:
    msg = msg_cls()
    msg.name = name
    return msg


def add_and_start(controller: Client, *datasets: cd.MDF_DATASET_ADD) -> None:
    """Add datasets, then start them all, waiting for each reply."""
    for request in datasets:
        controller.send_message(request)
        wait_reply(controller, cd.MT_DATASET_ADDED, request.dataset.name)
    controller.send_message(named(cd.MDF_DATASET_START, "*"))
    for request in datasets:
        wait_reply(controller, cd.MT_DATASET_STARTED, request.dataset.name)


def recorded_types(path: Path) -> list[int]:
    """The message types in a json recording."""
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return [row["header"]["msg_type"] for row in rows]


def stop_and_wait_saved(controller: Client, name: str) -> list[Message]:
    controller.send_message(named(cd.MDF_DATASET_STOP, name))
    return wait_reply(controller, cd.MT_DATASET_SAVED, name)


class TestUndecodableMessages:
    @pytest.mark.parametrize(
        ("message", "exc_type", "described"),
        [
            (StaleTestStart(), "InvalidMessageDefinition", "TEST_START"),
            (UnknownMessage(), "UnknownMessageType", str(UNKNOWN_TYPE)),
        ],
        ids=["stale", "unknown"],
    )
    def test_stops_only_datasets_that_record_it(
        self,
        controller: Client,
        tmp_path: Path,
        message: MessageData,
        exc_type: str,
        described: str,
    ) -> None:
        everything = add_request("everything", tmp_path, filename="all")
        ends_only = add_request(
            "ends_only", tmp_path, filename="ends", msg_types=(td.MT_TEST_END,)
        )
        add_and_start(controller, everything, ends_only)

        controller.send_message(message)
        seen = wait_reply(controller, cd.MT_DATASET_REMOVED, "everything")
        controller.send_message(td.MDF_TEST_END())
        stop_and_wait_saved(controller, "ends_only")

        error = next(m for m in seen if is_type(cd.MT_DATA_LOGGER_ERROR)(m))
        assert error.data.exc_type == exc_type
        assert described in error.data.msg
        assert events(seen, "everything") == [
            cd.MT_DATA_LOGGER_ERROR,
            cd.MT_DATASET_STOPPED,
            cd.MT_DATASET_SAVED,
            cd.MT_DATASET_REMOVED,
        ]
        assert (tmp_path / "all.jsonl").exists()
        assert td.MT_TEST_END in recorded_types(tmp_path / "ends.jsonl")

    @pytest.mark.parametrize(
        ("message", "exc_type"),
        [
            (StaleTestStart(), "InvalidMessageDefinition"),
            (UnknownMessage(), "UnknownMessageType"),
        ],
        ids=["stale", "unknown"],
    )
    def test_raw_dataset_records_it_undecoded(
        self,
        controller: Client,
        tmp_path: Path,
        message: MessageData,
        exc_type: str,
    ) -> None:
        raw_set = add_request("raw", tmp_path, filename="raw", formatter="raw")
        json_set = add_request("json", tmp_path, filename="all")
        add_and_start(controller, raw_set, json_set)

        controller.send_message(message)
        controller.send_message(message)
        seen = wait_reply(controller, cd.MT_DATASET_REMOVED, "json")
        controller.send_message(td.MDF_TEST_END())
        seen += stop_and_wait_saved(controller, "raw")

        # Reported once for both messages, and stopped only by the request.
        assert events(seen, "raw") == [
            cd.MT_DATA_LOGGER_ERROR,
            cd.MT_DATASET_STOPPED,
            cd.MT_DATASET_SAVED,
        ]
        error = next(m for m in seen if is_type(cd.MT_DATA_LOGGER_ERROR, "raw")(m))
        assert error.data.exc_type == exc_type
        assert "Recording undecoded" in error.data.msg
        with RawFile(tmp_path / "raw.dat") as f:
            records = list(f.records())
        undecoded = [r for r in records if r.undecoded]
        assert [(r.header.msg_type, r.payload) for r in undecoded] == [
            (message.type_id, bytes(message))
        ] * 2
        assert td.MT_TEST_END in [r.header.msg_type for r in records if not r.undecoded]

    def test_unrecorded_type_is_warned_about_once(
        self,
        controller: Client,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.WARNING)
        add_and_start(
            controller,
            add_request("ends_only", tmp_path, msg_types=(td.MT_TEST_END,)),
        )

        for _ in range(3):
            controller.send_message(StaleTestStart())
        wait_for_logger(controller)

        warnings = [
            r
            for r in caplog.records
            if r.levelno == logging.WARNING and "TEST_START" in r.getMessage()
        ]
        assert len(warnings) == 1
        controller.send_message(named(cd.MDF_DATASET_STATUS_REQUEST, "ends_only"))
        status = wait_reply(controller, cd.MT_DATASET_STATUS, "ends_only")[-1]
        assert status.data.is_recording


class TestDatasetFailures:
    def test_writer_failure_is_reported_while_others_record(
        self,
        controller: Client,
        clock: FakeClock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setitem(
            data_formatter._formatter_map, "full_disk", FullDiskFormatter
        )
        failing = add_request("failing", tmp_path, filename="f", formatter="full_disk")
        healthy = add_request("healthy", tmp_path, filename="h")
        add_and_start(controller, failing, healthy)

        clock.advance(DatasetWriter.WRITE_PERIOD + 1)
        seen = wait_reply(controller, cd.MT_DATASET_REMOVED, "failing")
        controller.send_message(td.MDF_TEST_END())
        stop_and_wait_saved(controller, "healthy")

        assert events(seen, "failing") == [
            cd.MT_DATA_LOGGER_ERROR,
            cd.MT_DATASET_STOPPED,
            cd.MT_DATASET_REMOVED,
        ]
        error = next(m for m in seen if is_type(cd.MT_DATA_LOGGER_ERROR)(m))
        assert error.data.exc_type == "OSError"
        assert "No space left on device" in error.data.msg
        assert td.MT_TEST_END in recorded_types(tmp_path / "h.jsonl")

    def test_failing_request_handler_is_reported(
        self,
        controller: Client,
        data_logger: DataLogger,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def fail(dest_mod_id: int = 0) -> None:
            raise RuntimeError("config went wrong")

        monkeypatch.setattr(data_logger, "send_config", fail)

        controller.send_signal(cd.MT_DATA_LOGGER_CONFIG_REQUEST)
        error = wait_reply(controller, cd.MT_DATA_LOGGER_ERROR)[-1]
        controller.send_message(add_request("after", tmp_path))
        added = read_until(controller, is_type(cd.MT_DATASET_ADDED, "after"))

        assert error.data.exc_type == "RuntimeError"
        assert "config went wrong" in error.data.msg
        assert added is not None


class TestRequests:
    def test_start_all_twice_is_harmless(
        self, controller: Client, tmp_path: Path
    ) -> None:
        add_and_start(controller, add_request("ds", tmp_path))

        controller.send_message(named(cd.MDF_DATASET_START, "all"))
        # The logger answers requests in order, so every reply to the second
        # start arrives before the config.
        controller.send_signal(cd.MT_DATA_LOGGER_CONFIG_REQUEST)
        seen = wait_reply(controller, cd.MT_DATA_LOGGER_CONFIG)
        controller.send_message(named(cd.MDF_DATASET_STATUS_REQUEST, "ds"))
        status = wait_reply(controller, cd.MT_DATASET_STATUS, "ds")[-1]

        assert events(seen, "ds") == []
        assert status.data.is_recording

    def test_directed_request_is_answered_to_its_sender(
        self,
        controller: Client,
        client_factory: Callable[..., Client],
        tmp_path: Path,
    ) -> None:
        observer = client_factory(name="observer")
        observer.subscribe(Dataset.DATALOGGER_TYPES)
        wait_for_logger(observer)

        controller.send_message(
            add_request("direct", tmp_path / "a"), dest_mod_id=cd.MID_DATA_LOGGER
        )
        wait_reply(controller, cd.MT_DATASET_ADDED, "direct")
        controller.send_message(add_request("broadcast", tmp_path / "b"))
        seen = wait_reply(observer, cd.MT_DATASET_ADDED, "broadcast")

        assert not any(is_type(cd.MT_DATASET_ADDED, "direct")(m) for m in seen)

    def test_request_addressed_to_another_module_is_ignored(
        self,
        controller: Client,
        client_factory: Callable[..., Client],
        tmp_path: Path,
    ) -> None:
        other = client_factory(name="other")

        controller.send_message(
            add_request("not_for_logger", tmp_path), dest_mod_id=other.module_id
        )
        controller.send_signal(cd.MT_DATA_LOGGER_CONFIG_REQUEST)
        config = wait_reply(controller, cd.MT_DATA_LOGGER_CONFIG)[-1]

        assert config.data.num_datasets == 0

    @pytest.mark.parametrize(
        ("requested", "used", "warned"),
        [(20, 20, False), (0, 500, True), (-5, 500, True), (900, 500, True)],
        ids=["in_range", "zero", "negative", "too_large"],
    )
    def test_max_size_mb_from_the_request(
        self,
        controller: Client,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        requested: int,
        used: int,
        warned: bool,
    ) -> None:
        caplog.set_level(logging.WARNING)

        controller.send_message(add_request("ds", tmp_path, max_size_mb=requested))
        wait_reply(controller, cd.MT_DATASET_ADDED, "ds")
        controller.send_signal(cd.MT_DATA_LOGGER_CONFIG_REQUEST)
        config = wait_reply(controller, cd.MT_DATA_LOGGER_CONFIG)[-1]

        assert config.data.datasets[0].max_size_mb == used
        assert ("max_size_mb" in caplog.text) == warned

    def test_full_logger_refuses_before_creating_folders(
        self, controller: Client, tmp_path: Path
    ) -> None:
        for i in range(DataLogger.MAX_DATASETS):
            controller.send_message(add_request(f"d{i}", tmp_path / f"d{i}"))
            wait_reply(controller, cd.MT_DATASET_ADDED, f"d{i}")

        controller.send_message(add_request("extra", tmp_path / "extra"))
        error = wait_reply(controller, cd.MT_DATA_LOGGER_ERROR, "extra")[-1]

        assert error.data.exc_type == "DataLoggerFullError"
        assert not (tmp_path / "extra").exists()

    def test_duplicate_name_refused_before_creating_folders(
        self, controller: Client, tmp_path: Path
    ) -> None:
        controller.send_message(add_request("same", tmp_path / "first"))
        wait_reply(controller, cd.MT_DATASET_ADDED, "same")

        controller.send_message(add_request("same", tmp_path / "second"))
        error = wait_reply(controller, cd.MT_DATA_LOGGER_ERROR, "same")[-1]

        assert error.data.exc_type == "DatasetExistsError"
        assert not (tmp_path / "second").exists()

    def test_duplicate_file_is_refused_when_added(
        self, controller: Client, tmp_path: Path
    ) -> None:
        controller.send_message(add_request("one", tmp_path))
        wait_reply(controller, cd.MT_DATASET_ADDED, "one")

        controller.send_message(add_request("two", tmp_path))
        error = wait_reply(controller, cd.MT_DATA_LOGGER_ERROR, "two")[-1]

        assert error.data.exc_type == "DatasetExistsError"
        assert "one" in error.data.msg


class TestRemoval:
    def test_reset_reports_saved_files(
        self, controller: Client, tmp_path: Path
    ) -> None:
        add_and_start(controller, add_request("ds", tmp_path))

        controller.send_signal(cd.MT_DATA_LOGGER_RESET)
        seen = wait_reply(controller, cd.MT_DATASET_REMOVED, "ds")

        assert events(seen, "ds")[-2:] == [cd.MT_DATASET_SAVED, cd.MT_DATASET_REMOVED]
        assert (tmp_path / "rec.jsonl").exists()

    def test_remove_after_stop_reports_saved_file_once(
        self, controller: Client, tmp_path: Path
    ) -> None:
        add_and_start(controller, add_request("ds", tmp_path))

        controller.send_message(named(cd.MDF_DATASET_STOP, "ds"))
        controller.send_message(named(cd.MDF_DATASET_REMOVE, "ds"))
        seen = wait_reply(controller, cd.MT_DATASET_REMOVED, "ds")
        # Anything sent for the dataset after its removal arrives before this.
        controller.send_signal(cd.MT_DATA_LOGGER_CONFIG_REQUEST)
        seen += wait_reply(controller, cd.MT_DATA_LOGGER_CONFIG)

        assert events(seen, "ds") == [
            cd.MT_DATASET_STOPPED,
            cd.MT_DATASET_SAVED,
            cd.MT_DATASET_REMOVED,
        ]

    def test_exit_reports_stopped_and_saved(
        self, controller: Client, data_logger: DataLogger, tmp_path: Path
    ) -> None:
        add_and_start(controller, add_request("ds", tmp_path))

        data_logger.stop()
        seen = wait_reply(controller, cd.MT_DATASET_SAVED, "ds")

        assert events(seen, "ds") == [cd.MT_DATASET_STOPPED, cd.MT_DATASET_SAVED]
        assert recorded_types(tmp_path / "rec.jsonl")


@pytest.mark.parametrize(("flags", "fsync"), [([], False), (["--fsync"], True)])
def test_main_passes_fsync(
    flags: list[str],
    fsync: bool,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    created: list[dict[str, Any]] = []

    def no_manager(*args: Any, **kwargs: Any) -> DataLogger:
        created.append(kwargs)
        raise MessageManagerNotFound("no manager in this test")

    monkeypatch.setattr(data_logger_module, "DataLogger", no_manager)
    monkeypatch.setattr(sys, "argv", ["data_logger", "-d", td.__file__, *flags])

    with pytest.raises(SystemExit):
        main()

    assert [kwargs["fsync"] for kwargs in created] == [fsync]


@pytest.mark.parametrize(
    ("flags", "period"), [([], 15.0), (["--write-period", "2.5"], 2.5)]
)
def test_main_passes_write_period(
    flags: list[str],
    period: float,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    created: list[dict[str, Any]] = []

    def no_manager(*args: Any, **kwargs: Any) -> DataLogger:
        created.append(kwargs)
        raise MessageManagerNotFound("no manager in this test")

    monkeypatch.setattr(data_logger_module, "DataLogger", no_manager)
    monkeypatch.setattr(sys, "argv", ["data_logger", "-d", td.__file__, *flags])

    with pytest.raises(SystemExit):
        main()

    assert [kwargs["write_period"] for kwargs in created] == [period]


@pytest.mark.parametrize("value", ["0", "-1", "inf", "soon"])
def test_main_refuses_a_bad_write_period(
    value: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = ["data_logger", "-d", td.__file__, "--write-period", value]
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit) as exited:
        main()

    assert exited.value.code == 2
    assert "--write-period" in capsys.readouterr().err


def test_bad_write_period_raises_before_connecting(free_port: int) -> None:
    with pytest.raises(ValueError, match="write period"):
        DataLogger(
            f"127.0.0.1:{free_port}",
            logging.INFO,
            definitions=td.get_message_definitions(),
            write_period=0,
        )


def test_options_reach_the_datasets(
    manager: ManagerHarness,
    client_factory: Callable[..., Client],
    clock: FakeClock,
    tmp_path: Path,
) -> None:
    logger = DataLogger(
        manager.address,
        logging.INFO,
        definitions=td.get_message_definitions(),
        clock=clock,
        fsync=True,
        write_period=2.5,
    )
    thread = threading.Thread(target=logger.run, name="data-logger", daemon=True)
    thread.start()
    try:
        client = client_factory(name="controller")
        client.subscribe(Dataset.DATALOGGER_TYPES)
        wait_for_logger(client)

        add_and_start(client, add_request("ds", tmp_path))

        dataset = logger.datasets["ds"]
        assert (dataset.fsync, dataset.write_period) == (True, 2.5)
    finally:
        logger.stop()
        thread.join(DEFAULT_TIMEOUT)


def test_main_exits_cleanly_without_manager(
    free_port: int,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    argv = ["data_logger", "-m", f"127.0.0.1:{free_port}", "-d", td.__file__]
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit) as exited:
        main()

    assert exited.value.code == 1
    assert "MessageManagerNotFound" in capsys.readouterr().err
