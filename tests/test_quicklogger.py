"""Tests for ``pyrtma.data_logger.formatters.quicklogger``."""

from __future__ import annotations

import ctypes
from pathlib import Path

import pytest

from pyrtma.data_logger.formatters.quicklogger import QLFormatter
from pyrtma.header import MessageHeader
from pyrtma.utils.log_reader import LogReader

from .ql_files import starts, v1_file
from .test_msg_defs import test_defs as td

MESSAGE_HEADER_SIZE: int = ctypes.sizeof(MessageHeader)


def spill_path(folder: Path) -> Path:
    """Where the formatter keeps ``rec.bin``'s data while it records."""
    return folder / ("rec.bin" + QLFormatter.spill_suffix)


def record(path: Path, batches: list[list]) -> None:
    """Write batches through the formatter, finalizing with the last one."""
    with open(path, "xb") as fd:
        formatter = QLFormatter(fd)
        for batch in batches[:-1]:
            formatter.write(batch)
        formatter.finalize(batches[-1])


def test_single_batch_matches_the_v1_layout(tmp_path: Path) -> None:
    messages = starts(3)

    record(tmp_path / "rec.bin", [messages])

    assert (tmp_path / "rec.bin").read_bytes() == v1_file(messages)


def test_several_batches_match_the_v1_layout(tmp_path: Path) -> None:
    messages = starts(7)

    record(tmp_path / "rec.bin", [messages[:2], messages[2:5], messages[5:]])

    assert (tmp_path / "rec.bin").read_bytes() == v1_file(messages)


def test_recording_round_trips_through_log_reader(tmp_path: Path) -> None:
    messages = starts(5)
    record(tmp_path / "rec.bin", [messages[:3], messages[3:]])

    log = LogReader(td.get_message_definitions()).load([tmp_path / "rec.bin"])

    assert [m.data.id for m in log.iter_by_mt(td.MT_TEST_START)] == [0, 1, 2, 3, 4]


class TestSizeLimit:
    def test_write_stops_before_the_limit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # Room for the file header and exactly three messages.
        per_message = MESSAGE_HEADER_SIZE + 4 + 4
        monkeypatch.setattr(QLFormatter, "max_bytes", 24 + 3 * per_message)
        messages = starts(5)

        with open(tmp_path / "rec.bin", "xb") as fd:
            formatter = QLFormatter(fd)
            assert formatter.write(messages) == 3
            assert formatter.write(messages[3:]) == 0
            formatter.finalize([])

        data = (tmp_path / "rec.bin").read_bytes()
        assert data == v1_file(messages[:3])
        assert len(data) <= QLFormatter.max_bytes

    def test_first_message_is_written_even_past_the_limit(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(QLFormatter, "max_bytes", 1)
        messages = starts(2)

        with open(tmp_path / "rec.bin", "xb") as fd:
            formatter = QLFormatter(fd)
            assert formatter.write(messages) == 1
            formatter.finalize([])

        assert (tmp_path / "rec.bin").read_bytes() == v1_file(messages[:1])

    def test_finalize_writes_every_message_it_is_given(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(QLFormatter, "max_bytes", 1)
        messages = starts(3)

        record(tmp_path / "rec.bin", [messages])

        assert (tmp_path / "rec.bin").read_bytes() == v1_file(messages)

    def test_default_limit_is_500_mb(self) -> None:
        assert QLFormatter.max_bytes == 500_000_000


class TestSpill:
    def test_small_recording_never_creates_a_spill_file(self, tmp_path: Path) -> None:
        with open(tmp_path / "rec.bin", "xb") as fd:
            formatter = QLFormatter(fd)
            formatter.write(starts(3))
            assert not spill_path(tmp_path).exists()
            formatter.finalize([])

        assert sorted(p.name for p in tmp_path.iterdir()) == ["rec.bin"]

    def test_data_past_the_threshold_spills_beside_the_recording(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(QLFormatter, "spill_threshold", 10)
        messages = starts(8)

        with open(tmp_path / "rec.bin", "xb") as fd:
            formatter = QLFormatter(fd)
            formatter.write(messages[:2])
            assert not spill_path(tmp_path).exists()
            formatter.write(messages[2:5])
            assert spill_path(tmp_path).exists()
            formatter.write(messages[5:])
            formatter.finalize([])

        assert (tmp_path / "rec.bin").read_bytes() == v1_file(messages)
        assert not spill_path(tmp_path).exists()

    def test_discard_removes_the_spill_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(QLFormatter, "spill_threshold", 10)

        with open(tmp_path / "rec.bin", "xb") as fd:
            formatter = QLFormatter(fd)
            formatter.write(starts(5))
            assert spill_path(tmp_path).exists()
            formatter.discard()

        assert not spill_path(tmp_path).exists()

    def test_stale_spill_file_from_a_crash_is_replaced(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(QLFormatter, "spill_threshold", 10)
        spill_path(tmp_path).write_bytes(b"left by a crashed logger" * 10)
        messages = starts(5)

        record(tmp_path / "rec.bin", [messages[:4], messages[4:]])

        assert (tmp_path / "rec.bin").read_bytes() == v1_file(messages)

    def test_offsets_take_four_bytes_each(self, tmp_path: Path) -> None:
        with open(tmp_path / "rec.bin", "xb") as fd:
            formatter = QLFormatter(fd)
            formatter.write(starts(3))

            assert formatter.offsets.itemsize == 4
            assert list(formatter.offsets) == [0, 4, 8]
            formatter.finalize([])
