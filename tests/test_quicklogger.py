"""Tests for ``pyrtma.data_logger.formatters.quicklogger``."""

from __future__ import annotations

from pathlib import Path

from pyrtma.data_logger.formatters.quicklogger import QLFormatter
from pyrtma.utils.log_reader import LogReader

from .ql_files import starts, v1_file
from .test_msg_defs import test_defs as td


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
