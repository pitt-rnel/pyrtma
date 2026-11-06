"""Tests for ``pyrtma.data_logger.dataset_writer``.

The writer's thread is real, but its formatter is a stand-in whose writes can
be held at a gate or made to fail, and its clock is a ``FakeClock`` the test
advances, so write periods and subdivisions need no waiting.
"""

from __future__ import annotations

import errno
import logging
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, ClassVar

import pytest

from pyrtma import core_defs as cd
from pyrtma.client_logging import TRUNCATED_MARKER
from pyrtma.data_logger import data_formatter, dataset_writer
from pyrtma.data_logger.data_formatter import DataFormatter
from pyrtma.data_logger.dataset_writer import DatasetWriter
from pyrtma.data_logger.exceptions import (
    DatasetError,
    DatasetExistsError,
    DatasetInProgress,
)
from pyrtma.header import MessageHeader
from pyrtma.message import Message

from .helpers import DEFAULT_TIMEOUT, FakeClock, wait_for

# A little more than one write period, to make a write due.
PAST_WRITE = DatasetWriter.WRITE_PERIOD + 1


class StubFormatter(DataFormatter):
    """A text formatter that writes one line per message.

    The ``stub_formatter`` fixture makes a subclass per test, so these class
    attributes are fresh in each one.
    """

    name: ClassVar[str] = "stub"
    mode: ClassVar[str] = "wt"
    ext: ClassVar[str] = ".txt"
    gate: ClassVar[threading.Event]
    write_started: ClassVar[threading.Event]
    fail_on_write: ClassVar[Exception | None] = None
    fail_on_init: ClassVar[Exception | None] = None

    def __init__(self, fd: Any) -> None:
        if (exc := type(self).fail_on_init) is not None:
            raise exc
        super().__init__(fd)

    def format_header(self) -> str:
        return "header\n"

    def format_footer(self) -> str:
        return "footer\n"

    def format_message(self, msg: Message) -> str:
        return f"{msg.data.name}\n"

    def write(self, wbuf: list[Message]) -> None:
        type(self).write_started.set()
        if not type(self).gate.wait(DEFAULT_TIMEOUT):
            raise TimeoutError("the test never opened the gate")
        if (exc := type(self).fail_on_write) is not None:
            raise exc
        super().write(wbuf)
        # So the test can read what was written while the file is open.
        self.fd.flush()


@pytest.fixture
def stub_formatter(monkeypatch: pytest.MonkeyPatch) -> Iterator[type[StubFormatter]]:
    """Register a fresh ``StubFormatter`` subclass as the ``stub`` formatter.

    Yields:
        The subclass, with its gate open.
    """
    cls = type(
        "Stub",
        (StubFormatter,),
        {"gate": threading.Event(), "write_started": threading.Event()},
    )
    cls.gate.set()
    monkeypatch.setitem(data_formatter._formatter_map, "stub", cls)
    yield cls
    cls.gate.set()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def make_writer(
    tmp_path: Path, stub_formatter: type[StubFormatter], clock: FakeClock
) -> Iterator[Callable[..., DatasetWriter]]:
    """Make writers that save to ``tmp_path`` with the stub formatter.

    Keyword arguments override the defaults; ``default_clock=True`` leaves
    out the fake clock. At teardown every writer is stopped and its thread
    joined.

    Yields:
        The factory.
    """
    writers: list[DatasetWriter] = []

    def make(*, default_clock: bool = False, **kwargs: Any) -> DatasetWriter:
        args: dict[str, Any] = dict(
            name="ds",
            save_path=str(tmp_path),
            filename="rec",
            formatter="stub",
            subdivide_interval=0,
            msg_types=[cd.ALL_MESSAGE_TYPES],
        )
        if not default_clock:
            args["clock"] = clock
        args.update(kwargs)
        writer = DatasetWriter(**args)
        writers.append(writer)
        return writer

    yield make

    stub_formatter.gate.set()
    for writer in writers:
        writer.stop()
        # Ends a thread that a writer started without ever recording.
        writer.stop_flag.set()
        if writer.write_thread.ident is not None:
            writer.write_thread.join(DEFAULT_TIMEOUT)


def message(text: str) -> Message:
    """Make a message whose stub-formatted line is ``text``."""
    data = cd.MDF_DATASET_ADDED()
    data.name = text
    header = MessageHeader()
    header.msg_type = data.type_id
    return Message(header, data)


def write_now(writer: DatasetWriter, clock: FakeClock) -> None:
    """Make a write due and stage it."""
    clock.advance(PAST_WRITE)
    writer.update(None)


def wait_written(writer: DatasetWriter) -> None:
    """Wait for the staged write to finish."""
    assert wait_for(writer.write_finished.is_set), "the write didn't finish"


def wait_dead(writer: DatasetWriter) -> None:
    """Wait for the write thread to end."""
    assert wait_for(lambda: writer.dead), "the write thread didn't end"


def lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


class TestWriterFailure:
    def test_write_error_stops_recording_and_reports_it(
        self,
        make_writer: Callable[..., DatasetWriter],
        stub_formatter: type[StubFormatter],
        clock: FakeClock,
    ) -> None:
        stub_formatter.fail_on_write = OSError(errno.ENOSPC, "No space left on device")
        writer = make_writer()
        writer.start()
        writer.update(message("a"))

        write_now(writer, clock)
        wait_dead(writer)
        writer.update(message("b"))

        assert writer.failed
        assert not writer.recording
        assert writer.error_event.is_set()
        assert writer.error.dataset_name == "ds"
        assert writer.error.exc_type == "OSError"
        assert "No space left on device" in writer.error.msg
        assert "rec.txt" in writer.error.msg
        assert writer.rbuf == []

    def test_dataset_error_in_writer_stops_recording(
        self,
        make_writer: Callable[..., DatasetWriter],
        clock: FakeClock,
        tmp_path: Path,
    ) -> None:
        (tmp_path / "rec_0001.txt").write_text("in the way", encoding="utf-8")
        writer = make_writer(subdivide_interval=DatasetWriter.MIN_INTERVAL)
        writer.start()
        writer.update(message("a"))

        clock.advance(DatasetWriter.MIN_INTERVAL + 1)
        writer.update(None)
        wait_dead(writer)

        assert not writer.recording
        assert writer.failed
        assert writer.error.exc_type == "DatasetExistsError"
        assert writer.error.dataset_name == "ds"
        assert "rec_0001.txt" in writer.error.msg
        assert writer.saved_files == [tmp_path / "rec.txt"]
        assert writer.file_saved.is_set()
        assert lines(tmp_path / "rec.txt") == ["header", "a", "footer"]
        assert lines(tmp_path / "rec_0001.txt") == ["in the way"]

    def test_error_text_fits_its_fields(
        self,
        make_writer: Callable[..., DatasetWriter],
        stub_formatter: type[StubFormatter],
        clock: FakeClock,
    ) -> None:
        # Like a localized Windows message: not ASCII, and long.
        stub_formatter.fail_on_write = OSError(
            errno.ENOSPC, "Espace insuffisant sur le périphérique. " * 20
        )
        writer = make_writer(name="d" * (cd.DATASET_NAME_LEN - 1))
        writer.start()

        write_now(writer, clock)
        wait_dead(writer)

        error = writer.error
        assert error.dataset_name == "d" * (cd.DATASET_NAME_LEN - 1)
        assert error.msg.isascii()
        assert "p?riph?rique" in error.msg
        assert error.msg.endswith(TRUNCATED_MARKER)
        assert len(error.msg) == 511


class TestSlowWrites:
    def test_slow_write_keeps_buffering(
        self,
        make_writer: Callable[..., DatasetWriter],
        stub_formatter: type[StubFormatter],
        clock: FakeClock,
        tmp_path: Path,
    ) -> None:
        stub_formatter.gate.clear()
        writer = make_writer()
        writer.start()
        writer.update(message("a"))
        write_now(writer, clock)
        assert wait_for(stub_formatter.write_started.is_set)

        writer.update(message("b"))
        write_now(writer, clock)
        writer.update(message("c"))
        stub_formatter.gate.set()
        wait_written(writer)
        writer.update(None)
        wait_written(writer)
        writer.stop()
        wait_dead(writer)

        assert not writer.error_event.is_set()
        assert lines(tmp_path / "rec.txt") == ["header", "a", "b", "c", "footer"]

    def test_falling_behind_warns_once_and_reports_catching_up(
        self,
        make_writer: Callable[..., DatasetWriter],
        stub_formatter: type[StubFormatter],
        clock: FakeClock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.INFO)
        stub_formatter.gate.clear()
        writer = make_writer()
        writer.start()
        write_now(writer, clock)
        assert wait_for(stub_formatter.write_started.is_set)

        for _ in range(3):
            write_now(writer, clock)
        stub_formatter.gate.set()
        wait_written(writer)
        writer.update(None)

        records = [r for r in caplog.records if r.name == writer.logger.logger.name]
        warnings = [r for r in records if r.levelno == logging.WARNING]
        caught_up = [r for r in records if "caught up" in r.getMessage()]
        assert len(warnings) == 1
        assert "behind" in warnings[0].getMessage()
        assert len(caught_up) == 1

    def test_subdivide_waits_for_busy_writer(
        self,
        make_writer: Callable[..., DatasetWriter],
        stub_formatter: type[StubFormatter],
        clock: FakeClock,
        tmp_path: Path,
    ) -> None:
        stub_formatter.gate.clear()
        writer = make_writer(subdivide_interval=DatasetWriter.MIN_INTERVAL)
        writer.start()
        writer.update(message("a"))
        write_now(writer, clock)
        assert wait_for(stub_formatter.write_started.is_set)

        # The subdivision falls due while the writer is still busy with "a".
        writer.update(message("b"))
        write_now(writer, clock)
        stub_formatter.gate.set()
        wait_written(writer)
        writer.update(None)
        wait_written(writer)
        writer.update(message("c"))
        writer.stop()
        wait_dead(writer)

        assert not writer.error_event.is_set()
        assert lines(tmp_path / "rec.txt") == ["header", "a", "b", "footer"]
        assert lines(tmp_path / "rec_0001.txt") == ["header", "c", "footer"]

    def test_stop_while_behind_writes_everything(
        self,
        make_writer: Callable[..., DatasetWriter],
        stub_formatter: type[StubFormatter],
        clock: FakeClock,
        tmp_path: Path,
    ) -> None:
        stub_formatter.gate.clear()
        writer = make_writer()
        writer.start()
        writer.update(message("a"))
        write_now(writer, clock)
        assert wait_for(stub_formatter.write_started.is_set)
        writer.update(message("b"))
        write_now(writer, clock)

        writer.stop()
        stub_formatter.gate.set()
        wait_dead(writer)

        assert lines(tmp_path / "rec.txt") == ["header", "a", "b", "footer"]
        assert writer.saved_files == [tmp_path / "rec.txt"]


class TestPauseResume:
    def test_resume_when_not_paused_keeps_elapsed_time(
        self,
        make_writer: Callable[..., DatasetWriter],
        stub_formatter: type[StubFormatter],
        clock: FakeClock,
    ) -> None:
        # The closed gate holds the writer before it acts on the subdivision.
        stub_formatter.gate.clear()
        writer = make_writer(subdivide_interval=DatasetWriter.MIN_INTERVAL)
        writer.start()
        clock.advance(10)

        result = writer.resume()

        assert writer.elapsed_time == pytest.approx(10)
        assert result is False
        clock.advance(DatasetWriter.MIN_INTERVAL - 10 + 1)
        writer.update(None)
        assert writer.subdivide_flag

    def test_pause_before_start_does_nothing(
        self, make_writer: Callable[..., DatasetWriter]
    ) -> None:
        writer = make_writer()

        result = writer.pause()

        assert not writer.paused
        assert result is False
        assert writer.resume() is False

    def test_pause_and_resume_track_elapsed_time(
        self, make_writer: Callable[..., DatasetWriter], clock: FakeClock
    ) -> None:
        writer = make_writer()
        writer.start()
        clock.advance(5)

        writer.pause()
        clock.advance(100)
        assert writer.elapsed_time == pytest.approx(5)
        writer.resume()
        clock.advance(2)

        assert writer.elapsed_time == pytest.approx(7)


class TestStartAndFiles:
    def test_start_twice_raises_dataset_in_progress(
        self, make_writer: Callable[..., DatasetWriter]
    ) -> None:
        writer = make_writer()
        writer.start()

        with pytest.raises(DatasetInProgress):
            writer.start()
        assert writer.recording

    def test_second_writer_for_same_file_is_refused(
        self,
        make_writer: Callable[..., DatasetWriter],
        clock: FakeClock,
        tmp_path: Path,
    ) -> None:
        first = make_writer(name="one")
        second = make_writer(name="two")
        first.start()
        first.update(message("a"))
        write_now(first, clock)
        wait_written(first)

        with pytest.raises(DatasetExistsError):
            second.start()

        assert not second.recording
        assert not second.write_thread.is_alive()
        assert lines(tmp_path / "rec.txt") == ["header", "a"]

    def test_failed_start_leaves_no_thread_and_no_file(
        self,
        make_writer: Callable[..., DatasetWriter],
        stub_formatter: type[StubFormatter],
        tmp_path: Path,
    ) -> None:
        writer = make_writer()
        stub_formatter.fail_on_init = OSError(errno.EACCES, "Access is denied")

        with pytest.raises(DatasetError, match="Access is denied"):
            writer.start()

        assert not writer.recording
        assert not writer.write_thread.is_alive()
        assert not (tmp_path / "rec.txt").exists()

    def test_save_path_that_cannot_be_created_raises_dataset_error(
        self, make_writer: Callable[..., DatasetWriter], tmp_path: Path
    ) -> None:
        blocker = tmp_path / "file"
        blocker.write_text("", encoding="utf-8")

        with pytest.raises(DatasetError):
            make_writer(save_path=str(blocker / "sub"))

    def test_stop_writes_buffered_messages_and_saves(
        self, make_writer: Callable[..., DatasetWriter], tmp_path: Path
    ) -> None:
        writer = make_writer()
        writer.start()
        writer.update(message("a"))
        writer.update(message("b"))

        writer.stop()
        wait_dead(writer)

        assert not writer.error_event.is_set()
        assert lines(tmp_path / "rec.txt") == ["header", "a", "b", "footer"]
        assert writer.saved_files == [tmp_path / "rec.txt"]
        assert writer.file_saved.is_set()

    def test_default_clock_ignores_wall_clock_steps(
        self,
        make_writer: Callable[..., DatasetWriter],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        writer = make_writer(default_clock=True)
        writer.start()
        stepped = time.time() + 3600
        monkeypatch.setattr(dataset_writer.time, "time", lambda: stepped)

        writer.update(None)

        assert not writer.write_to_disk.is_set()
        assert writer.elapsed_time < DatasetWriter.WRITE_PERIOD
