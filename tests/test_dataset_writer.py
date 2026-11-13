"""Tests for ``pyrtma.data_logger.dataset_writer``.

The writer's thread is real, but its formatter is a stand-in whose writes can
be held at a gate or made to fail, and its clock is a ``FakeClock`` the test
advances, so write periods and subdivisions need no waiting.
"""

from __future__ import annotations

import errno
import gc
import logging
import os
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, ClassVar

import pytest

from pyrtma import core_defs as cd
from pyrtma.client_logging import TRUNCATED_MARKER
from pyrtma.data_logger import data_formatter, dataset_writer
from pyrtma.data_logger.data_formatter import DataFormatter, FileContext
from pyrtma.data_logger.dataset_writer import DatasetWriter
from pyrtma.data_logger.formatters.quicklogger import QLFormatter
from pyrtma.header import MessageHeader
from pyrtma.utils.log_reader import LogReader
from pyrtma.data_logger.exceptions import (
    DatasetError,
    DatasetExistsError,
    DatasetInProgress,
)
from pyrtma.message import Message

from .helpers import DEFAULT_TIMEOUT, FakeClock, wait_for
from .ql_files import starts
from .test_msg_defs import test_defs as td

# A little more than one write period, to make a write due.
PAST_WRITE = DatasetWriter.WRITE_PERIOD + 1

# Bytes a "\n" takes on disk in a text file, which is two on Windows.
NEWLINE: int = len(os.linesep)
# The stand-in's "header\n" or "footer\n" on disk.
HEADER: int = 6 + NEWLINE
# Room for the header, two one-letter lines and the footer.
TWO_LINES: int = HEADER + 2 * (1 + NEWLINE) + HEADER


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
    discarded: ClassVar[threading.Event]
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

    def write(self, wbuf: list[Message]) -> int:
        type(self).write_started.set()
        if not type(self).gate.wait(DEFAULT_TIMEOUT):
            raise TimeoutError("the test never opened the gate")
        if (exc := type(self).fail_on_write) is not None:
            raise exc
        count = super().write(wbuf)
        # So the test can read what was written while the file is open.
        self.fd.flush()
        return count

    def discard(self) -> None:
        type(self).discarded.set()


@pytest.fixture
def stub_formatter(monkeypatch: pytest.MonkeyPatch) -> Iterator[type[StubFormatter]]:
    """Register a fresh ``StubFormatter`` subclass as the ``stub`` formatter.

    Yields:
        The subclass, with its gate open.
    """
    cls = type(
        "Stub",
        (StubFormatter,),
        {
            "gate": threading.Event(),
            "write_started": threading.Event(),
            "discarded": threading.Event(),
        },
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


def test_collected_writer_leaves_no_open_socket(
    tmp_path: Path, stub_formatter: type[StubFormatter]
) -> None:
    writer = DatasetWriter(
        name="ds",
        save_path=str(tmp_path),
        filename="rec",
        formatter="stub",
        subdivide_interval=0,
        msg_types=[cd.ALL_MESSAGE_TYPES],
    )
    sock = writer.client.sock

    del writer
    gc.collect()

    assert sock.fileno() == -1


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
        assert stub_formatter.discarded.is_set()

    def test_dataset_error_in_writer_stops_recording(
        self,
        make_writer: Callable[..., DatasetWriter],
        stub_formatter: type[StubFormatter],
        clock: FakeClock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        (tmp_path / "rec_0001.txt").write_text("in the way", encoding="utf-8")
        monkeypatch.setattr(stub_formatter, "max_bytes", TWO_LINES)
        writer = make_writer()
        writer.start()
        for text in "abc":
            writer.update(message(text))

        write_now(writer, clock)
        wait_dead(writer)

        assert not writer.recording
        assert writer.failed
        assert writer.error.exc_type == "DatasetExistsError"
        assert writer.error.dataset_name == "ds"
        assert "rec_0001.txt" in writer.error.msg
        assert writer.saved_files == [tmp_path / "rec.txt"]
        assert writer.file_saved.is_set()
        assert lines(tmp_path / "rec.txt") == ["header", "a", "b", "footer"]
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
        writer = make_writer()
        writer.start()
        clock.advance(10)

        result = writer.resume()

        assert writer.elapsed_time == pytest.approx(10)
        assert result is False
        clock.advance(DatasetWriter.WRITE_PERIOD - 10 + 1)
        writer.update(None)
        assert wait_for(stub_formatter.write_started.is_set)

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


class LegacyFormatter(StubFormatter):
    """A formatter written before ``write()`` returned a count."""

    def write(self, wbuf: list[Message]) -> None:  # type: ignore[override]
        self.fd.writelines(self.format_message(msg) for msg in wbuf)


class TestRollover:
    def test_full_file_continues_in_a_new_one(
        self,
        make_writer: Callable[..., DatasetWriter],
        stub_formatter: type[StubFormatter],
        clock: FakeClock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(stub_formatter, "max_bytes", TWO_LINES)
        writer = make_writer()
        writer.start()
        for text in "abc":
            writer.update(message(text))
        write_now(writer, clock)
        wait_written(writer)
        for text in "de":
            writer.update(message(text))

        writer.stop()
        wait_dead(writer)

        names = ["rec.txt", "rec_0001.txt", "rec_0002.txt"]
        assert writer.saved_files == [tmp_path / n for n in names]
        assert [lines(tmp_path / n)[1:-1] for n in names] == [
            ["a", "b"],
            ["c", "d"],
            ["e"],
        ]
        assert all((tmp_path / n).stat().st_size <= TWO_LINES for n in names)
        assert not writer.error_event.is_set()

    def test_subdivide_interval_is_ignored(
        self,
        make_writer: Callable[..., DatasetWriter],
        clock: FakeClock,
        tmp_path: Path,
    ) -> None:
        with pytest.warns(DeprecationWarning, match="max_size_mb"):
            writer = make_writer(subdivide_interval=30)
        writer.start()
        writer.update(message("a"))

        clock.advance(10 * 60)
        writer.update(message("b"))
        writer.stop()
        wait_dead(writer)

        assert writer.saved_files == [tmp_path / "rec.txt"]
        assert lines(tmp_path / "rec.txt") == ["header", "a", "b", "footer"]

    def test_max_size_mb_sets_the_file_limit(
        self, make_writer: Callable[..., DatasetWriter]
    ) -> None:
        writer = make_writer(max_size_mb=20)
        writer.start()

        assert writer.max_size_mb == 20
        assert writer.formatter.max_bytes == 20_000_000

    def test_formatter_limit_below_max_size_mb_wins(
        self,
        make_writer: Callable[..., DatasetWriter],
        stub_formatter: type[StubFormatter],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(stub_formatter, "max_bytes", 1000)
        writer = make_writer(max_size_mb=20)
        writer.start()

        assert writer.formatter.max_bytes == 1000

    @pytest.mark.parametrize("size", [0, -1, cd.DATASET_MAX_SIZE_MB + 1])
    def test_max_size_mb_outside_its_range_is_refused(
        self, make_writer: Callable[..., DatasetWriter], size: int
    ) -> None:
        with pytest.raises(DatasetError, match="max_size_mb"):
            make_writer(max_size_mb=size)

    def test_default_max_size_is_500_mb(
        self, make_writer: Callable[..., DatasetWriter]
    ) -> None:
        assert make_writer().max_size_mb == cd.DATASET_MAX_SIZE_MB == 500

    def test_rolled_over_quicklogger_files_all_read(
        self,
        make_writer: Callable[..., DatasetWriter],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # The file header and three TEST_STARTs per file.
        per_message = MessageHeader().size + 4 + 4
        monkeypatch.setattr(QLFormatter, "max_bytes", 24 + 3 * per_message)
        writer = make_writer(formatter="quicklogger")
        writer.start()
        for msg in starts(7):
            writer.update(msg)

        writer.stop()
        wait_dead(writer)

        assert len(writer.saved_files) == 3
        assert all(
            p.stat().st_size <= QLFormatter.max_bytes for p in writer.saved_files
        )
        log = LogReader(td.get_message_definitions()).load(writer.saved_files)
        assert [m.data.id for m in log.iter_by_mt(td.MT_TEST_START)] == list(range(7))

    def test_crash_keeps_finished_files_readable(
        self,
        make_writer: Callable[..., DatasetWriter],
        clock: FakeClock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        per_message = MessageHeader().size + 4 + 4
        monkeypatch.setattr(QLFormatter, "max_bytes", 24 + 3 * per_message)
        writer = make_writer(formatter="quicklogger")
        writer.start()
        for msg in starts(5):
            writer.update(msg)
        write_now(writer, clock)
        wait_written(writer)

        # Read as if the logger had died now, with rec_0001.bin unfinished.
        reader = LogReader(td.get_message_definitions())
        finished = reader.load([tmp_path / "rec.bin"])
        unfinished = LogReader(td.get_message_definitions()).load(
            [tmp_path / "rec_0001.bin"], throw=False
        )

        assert [m.data.id for m in finished.iter_by_mt(td.MT_TEST_START)] == [0, 1, 2]
        assert list(unfinished.iter_by_mt(td.MT_TEST_START)) == []

    def test_formatter_without_a_count_is_not_split(
        self,
        make_writer: Callable[..., DatasetWriter],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setitem(data_formatter._formatter_map, "legacy", LegacyFormatter)
        monkeypatch.setattr(LegacyFormatter, "max_bytes", TWO_LINES)
        writer = make_writer(formatter="legacy")
        writer.start()
        for text in "abcde":
            writer.update(message(text))

        writer.stop()
        wait_dead(writer)

        assert writer.saved_files == [tmp_path / "rec.txt"]
        assert lines(tmp_path / "rec.txt")[1:-1] == list("abcde")


class TestFsync:
    @pytest.fixture
    def syncs(self, monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
        """Record ``os.fsync()`` calls on files, and folder syncs, separately."""
        seen: dict[str, list[Any]] = {"files": [], "folders": []}
        monkeypatch.setattr(dataset_writer.os, "fsync", seen["files"].append)
        monkeypatch.setattr(dataset_writer, "_fsync_dir", seen["folders"].append)
        return seen

    def test_files_are_not_synced_by_default(
        self,
        make_writer: Callable[..., DatasetWriter],
        clock: FakeClock,
        syncs: dict[str, list[Any]],
    ) -> None:
        writer = make_writer()
        writer.start()
        writer.update(message("a"))

        write_now(writer, clock)
        wait_written(writer)
        writer.stop()
        wait_dead(writer)

        assert syncs == {"files": [], "folders": []}

    def test_fsync_syncs_after_each_write_and_before_close(
        self,
        make_writer: Callable[..., DatasetWriter],
        clock: FakeClock,
        tmp_path: Path,
        syncs: dict[str, list[Any]],
    ) -> None:
        writer = make_writer(fsync=True)
        writer.start()
        writer.update(message("a"))

        write_now(writer, clock)
        wait_written(writer)
        after_write = len(syncs["files"])
        writer.stop()
        wait_dead(writer)

        assert after_write == 1
        assert len(syncs["files"]) == 2
        assert syncs["folders"] == [tmp_path]
        assert lines(tmp_path / "rec.txt") == ["header", "a", "footer"]

    def test_fsync_syncs_each_full_file_and_its_folder(
        self,
        make_writer: Callable[..., DatasetWriter],
        stub_formatter: type[StubFormatter],
        clock: FakeClock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        syncs: dict[str, list[Any]],
    ) -> None:
        monkeypatch.setattr(stub_formatter, "max_bytes", TWO_LINES)
        writer = make_writer(fsync=True)
        writer.start()
        for text in "abc":
            writer.update(message(text))

        write_now(writer, clock)
        wait_written(writer)

        # rec.txt is synced when it fills, before it is closed; then the write
        # that continued in rec_0001.txt is synced.
        assert len(syncs["files"]) == 2
        assert syncs["folders"] == [tmp_path, tmp_path]


class TestWritePeriod:
    def test_write_period_sets_the_schedule(
        self,
        make_writer: Callable[..., DatasetWriter],
        clock: FakeClock,
        tmp_path: Path,
    ) -> None:
        writer = make_writer(write_period=2.0)
        writer.start()
        writer.update(message("a"))

        clock.advance(1.9)
        writer.update(None)
        early = writer.write_to_disk.is_set() or writer.write_finished.is_set()
        clock.advance(0.2)
        writer.update(None)
        wait_written(writer)

        assert not early
        assert lines(tmp_path / "rec.txt") == ["header", "a"]
        assert writer.next_write == pytest.approx(4.1)

    def test_default_write_period_is_15_s(
        self, make_writer: Callable[..., DatasetWriter]
    ) -> None:
        writer = make_writer()

        assert writer.write_period == DatasetWriter.WRITE_PERIOD == 15.0

    @pytest.mark.parametrize("period", [0, -1, float("inf"), float("nan")])
    def test_write_period_must_be_positive(
        self, make_writer: Callable[..., DatasetWriter], period: float
    ) -> None:
        with pytest.raises(ValueError, match="write period"):
            make_writer(write_period=period)


class ContextFormatter(StubFormatter):
    """A stand-in that asks for a ``FileContext`` and records each one."""

    wants_context: ClassVar[bool] = True
    contexts: ClassVar[list[FileContext]]

    def __init__(self, fd: Any, *, context: FileContext) -> None:
        type(self).contexts.append(context)
        super().__init__(fd)


class TestFormatterContext:
    def test_context_describes_each_file(
        self,
        make_writer: Callable[..., DatasetWriter],
        stub_formatter: type[StubFormatter],
        clock: FakeClock,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        cls = type("Ctx", (ContextFormatter, stub_formatter), {"contexts": []})
        monkeypatch.setattr(cls, "max_bytes", TWO_LINES)
        monkeypatch.setitem(data_formatter._formatter_map, "stub", cls)
        definitions = cd.get_message_definitions()
        writer = make_writer(definitions=definitions)
        writer.start()
        for text in "abc":
            writer.update(message(text))

        write_now(writer, clock)
        wait_written(writer)

        # The first context is the constructor's placeholder, for the same file.
        files = [(c.dataset, c.path, c.part) for c in cls.contexts[1:]]
        assert files == [
            ("ds", tmp_path / "rec.txt", 0),
            ("ds", tmp_path / "rec_0001.txt", 1),
        ]
        assert all(c.definitions is definitions for c in cls.contexts)

    def test_formatters_without_it_get_only_the_file(
        self,
        make_writer: Callable[..., DatasetWriter],
        stub_formatter: type[StubFormatter],
        tmp_path: Path,
    ) -> None:
        writer = make_writer(definitions=cd.get_message_definitions())

        writer.start()

        assert not stub_formatter.wants_context
        assert (tmp_path / "rec.txt").exists()


class StubbornFormatter(DataFormatter):
    """A formatter that never takes a message, even into a new file."""

    name: ClassVar[str] = "stubborn"

    def write(self, wbuf: list[Message]) -> int:
        return 0


def test_formatter_that_takes_nothing_fails_the_dataset(
    make_writer: Callable[..., DatasetWriter],
    clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(data_formatter._formatter_map, "stubborn", StubbornFormatter)
    writer = make_writer(formatter="stubborn")
    writer.start()
    writer.update(message("a"))

    write_now(writer, clock)
    wait_dead(writer)

    assert writer.failed
    assert writer.error.exc_type == "DatasetWriterError"
    assert "took no messages" in writer.error.msg
