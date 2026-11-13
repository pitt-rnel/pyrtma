"""Tests for ``pyrtma.data_logger.data_formatter``."""

from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar

import pytest

from pyrtma.data_logger import data_formatter
from pyrtma.message import Message
from pyrtma.data_logger.data_formatter import DataFormatter, add_formatter
from pyrtma.data_logger.exceptions import DataFormatterKeyError

from .ql_files import starts

# Bytes a "\n" takes on disk in a text file, which is two on Windows.
NEWLINE: int = len(os.linesep)
# "header\n" and "footer\n" on disk.
HEADER: int = 6 + NEWLINE


def test_duplicate_formatter_name_error_has_its_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Twice(DataFormatter):
        name: ClassVar[str] = "twice"

    monkeypatch.setattr(data_formatter, "_formatter_map", {})
    add_formatter(Twice)

    with pytest.raises(DataFormatterKeyError) as caught:
        add_formatter(Twice)

    assert caught.value.dataset == ""
    assert "twice" in caught.value.msg


class Lines(DataFormatter):
    """A text formatter writing a 7-byte header and footer and one line each."""

    name: ClassVar[str] = "lines"

    def format_header(self) -> str:
        return "header\n"

    def format_footer(self) -> str:
        return "footer\n"

    def format_message(self, msg: Message) -> str:
        return f"{msg.data.id}\n"


def test_default_limit_is_500_mb() -> None:
    assert DataFormatter.max_bytes == 500_000_000


def test_write_leaves_room_for_the_footer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The header, three one-digit lines and the footer.
    monkeypatch.setattr(Lines, "max_bytes", HEADER + 3 * (1 + NEWLINE) + HEADER)
    messages = starts(5)

    with open(tmp_path / "rec.txt", "x", encoding="utf-8") as fd:
        formatter = Lines(fd)
        assert formatter.write(messages) == 3
        assert formatter.write(messages[3:]) == 0
        formatter.finalize([])

    text = (tmp_path / "rec.txt").read_text(encoding="utf-8")
    assert text == "header\n0\n1\n2\nfooter\n"
    assert (tmp_path / "rec.txt").stat().st_size == Lines.max_bytes


def test_first_message_is_written_even_past_the_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Lines, "max_bytes", 1)

    with open(tmp_path / "rec.txt", "x", encoding="utf-8") as fd:
        formatter = Lines(fd)
        assert formatter.write(starts(2)) == 1
        formatter.finalize([])

    assert (tmp_path / "rec.txt").read_text(encoding="utf-8") == "header\n0\nfooter\n"


def test_limit_counts_encoded_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Accented(Lines):
        def format_message(self, msg: Message) -> str:
            return "é\n"  # 2 bytes in UTF-8, then the newline

    monkeypatch.setattr(Accented, "max_bytes", HEADER + 2 * (2 + NEWLINE) + HEADER)

    with open(tmp_path / "rec.txt", "x", encoding="utf-8") as fd:
        formatter = Accented(fd)
        assert formatter.write(starts(3)) == 2
        formatter.finalize([])

    assert (tmp_path / "rec.txt").stat().st_size == Accented.max_bytes
