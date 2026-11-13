"""Tests for ``pyrtma.data_logger.formatters.msg_headers``."""

from __future__ import annotations

import csv
from pathlib import Path

from pyrtma.data_logger.formatters.msg_headers import MsgHeaderFormatter

from .ql_files import starts


def test_rows_have_one_field_per_column(tmp_path: Path) -> None:
    messages = starts(3)
    for i, msg in enumerate(messages):
        msg.header.send_time = 1000.5 + i
        msg.header.src_mod_id = 7

    with open(tmp_path / "rec.csv", "x", encoding="utf-8", newline="") as fd:
        formatter = MsgHeaderFormatter(fd)
        formatter.write(messages)
        formatter.finalize([])

    with open(tmp_path / "rec.csv", encoding="utf-8", newline="") as fd:
        header, *rows = list(csv.reader(fd))
    assert header == list(messages[0].header.to_dict())
    assert [len(row) for row in rows] == [len(header)] * 3
    for row, msg in zip(rows, messages):
        assert row == [str(v) for v in msg.header.to_dict().values()]
