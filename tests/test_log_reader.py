"""Tests for ``pyrtma.utils.log_reader``, on files built by hand."""

from __future__ import annotations

import importlib
import logging
import sys
from pathlib import Path

import pytest

from pyrtma.exceptions import MessageDefinitionsError, UnknownMessageType
from pyrtma.utils.log_reader import LogReader

from .ql_files import message, starts, v1_file
from .test_msg_defs import test_defs as td

from pyrtma.message_base import MessageMeta
from pyrtma.message_data import MessageData
from pyrtma.validators import Int32
from typing import ClassVar

# A type the test definitions don't define.
UNKNOWN_TYPE: int = 7777


class StaleTestEnd(MessageData, metaclass=MessageMeta):
    """``TEST_END`` as an out-of-date definition has it: 8 bytes, not 4."""

    type_id: ClassVar[int] = td.MT_TEST_END
    type_name: ClassVar[str] = "TEST_END"
    type_hash: ClassVar[int] = 0
    type_size: ClassVar[int] = 8
    type_source: ClassVar[str] = "test_log_reader"
    type_def: ClassVar[str] = ""

    id: Int32 = Int32()
    extra: Int32 = Int32()


class UnknownMessage(MessageData, metaclass=MessageMeta):
    type_id: ClassVar[int] = UNKNOWN_TYPE
    type_name: ClassVar[str] = "UNKNOWN"
    type_hash: ClassVar[int] = 0
    type_size: ClassVar[int] = 4
    type_source: ClassVar[str] = "test_log_reader"
    type_def: ClassVar[str] = ""

    value: Int32 = Int32()


def write(path: Path, data: bytes) -> Path:
    path.write_bytes(data)
    return path


def reader() -> LogReader:
    return LogReader(td.get_message_definitions())


def start_ids(log) -> list[int]:
    return [m.data.id for m in log.iter_by_mt(td.MT_TEST_START)]


def test_reads_a_file_with_the_v1_layout(tmp_path: Path) -> None:
    path = write(tmp_path / "old.bin", v1_file(starts(4)))

    log = reader().load([path])

    assert start_ids(log) == [0, 1, 2, 3]


@pytest.mark.parametrize(
    ("other", "exclude"),
    [
        (StaleTestEnd(), [td.MT_TEST_END]),
        (StaleTestEnd(), ["TEST_END"]),
        (UnknownMessage(), [UNKNOWN_TYPE]),
    ],
    ids=["stale_by_number", "stale_by_name", "unknown_by_number"],
)
def test_excluded_type_is_skipped_before_it_is_checked(
    tmp_path: Path, other: MessageData, exclude: list
) -> None:
    messages = starts(2) + [message(other, 2.0)] + starts(1, first=3)
    path = write(tmp_path / "rec.bin", v1_file(messages))

    log = reader().load([path], exclude=exclude)

    assert start_ids(log) == [0, 1, 3]


def test_included_types_are_chosen_before_others_are_checked(
    tmp_path: Path,
) -> None:
    messages = starts(2) + [
        message(StaleTestEnd(), 2.0),
        message(UnknownMessage(), 3.0),
    ]
    path = write(tmp_path / "rec.bin", v1_file(messages))

    log = reader().load([path], include=["TEST_START"])

    assert start_ids(log) == [0, 1]


def test_stale_type_still_raises_when_not_filtered(tmp_path: Path) -> None:
    messages = starts(1) + [message(StaleTestEnd(), 1.0)]
    path = write(tmp_path / "rec.bin", v1_file(messages))

    with pytest.raises(MessageDefinitionsError, match="TEST_END"):
        reader().load([path])


@pytest.mark.parametrize(
    ("cut", "expected"),
    [
        (2, [0, 1, 2]),  # inside the last message's data
        (2 * 4, [0, 1]),  # the last two messages' data
    ],
    ids=["mid_message", "whole_messages"],
)
def test_truncated_data_loads_as_far_as_it_goes(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    cut: int,
    expected: list[int],
) -> None:
    whole = v1_file(starts(4))
    path = write(tmp_path / "rec.bin", whole[:-cut])

    log = reader().load([path], throw=False)

    assert start_ids(log) == expected
    assert "truncated" in caplog.text


@pytest.mark.parametrize(
    "keep", [10, 24 + 48, 24 + 4 * 48 + 4], ids=["file_header", "headers", "offsets"]
)
def test_file_truncated_before_its_data_loads_nothing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, keep: int
) -> None:
    path = write(tmp_path / "rec.bin", v1_file(starts(4))[:keep])

    log = reader().load([path], throw=False)

    assert start_ids(log) == []
    assert "truncated" in caplog.text


def test_truncated_file_raises_a_clear_error(tmp_path: Path) -> None:
    path = write(tmp_path / "rec.bin", v1_file(starts(4))[:-2])

    with pytest.raises(ValueError, match="truncated"):
        reader().load([path])


def test_imports_without_tkinter(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "tkinter", None)
    monkeypatch.delitem(sys.modules, "pyrtma.utils.log_reader")

    module = importlib.import_module("pyrtma.utils.log_reader")

    with pytest.raises(RuntimeError, match="tkinter"):
        module.LogReader(None)
