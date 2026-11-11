"""Tests for ``pyrtma.utils.raw_to_ql``: raw files converted to QuickLogger.

Raw files are written by a real ``DatasetWriter`` with the ``raw`` formatter,
and the QuickLogger files are read back with ``LogReader``, both with the
test definitions.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pyrtma import core_defs as cd
from pyrtma.data_logger.data_formatter import UndecodedMessage
from pyrtma.data_logger.dataset_writer import DatasetWriter
from pyrtma.data_logger.formatters import raw
from pyrtma.data_logger.formatters.quicklogger import QLFormatter
from pyrtma.exceptions import RawFormatError
from pyrtma.header import MessageHeader
from pyrtma.message import Message
from pyrtma.utils import raw_to_ql
from pyrtma.utils.log_reader import LogReader
from pyrtma.utils.raw_reader import RawFile

from .helpers import FakeClock, wait_for
from .test_msg_defs import test_defs as td

DEFS = td.get_message_definitions()


def header(msg_type: int, size: int, count: int) -> MessageHeader:
    """A header from source 20, as received, with ``msg_count`` ``count``."""
    h = MessageHeader()
    h.msg_type = msg_type
    h.num_data_bytes = size
    h.msg_count = count
    h.src_mod_id = 20
    h.recv_time = float(count)
    return h


def start(i: int) -> Message:
    data = td.MDF_TEST_START()
    data.id = i
    return Message(header(data.type_id, data.type_size, i), data)


def undecoded(msg_type: int, payload: bytes, count: int) -> UndecodedMessage:
    return UndecodedMessage(header(msg_type, len(payload), count), payload)


def write_raw(
    folder: Path, items: list[Message | UndecodedMessage], name: str = "rec"
) -> Path:
    """Record ``items`` to ``folder/name.dat`` and finish the file."""
    writer = DatasetWriter(
        "ds",
        str(folder),
        name,
        "raw",
        0,
        [cd.ALL_MESSAGE_TYPES],
        clock=FakeClock(),
        definitions=DEFS,
    )
    writer.start()
    for item in items:
        writer.update(item)
    writer.stop()
    assert wait_for(lambda: writer.dead), "the write thread didn't end"
    return folder / f"{name}.dat"


def read_ql(*paths: Path) -> list[Message]:
    """The ``TEST_START`` messages in QuickLogger files, by receive time."""
    return list(LogReader(DEFS).load(list(paths)).iter_by_mt(td.MT_TEST_START))


class TestConvert:
    def test_every_message_converts_with_its_header(self, tmp_path: Path) -> None:
        source = write_raw(tmp_path, [start(i) for i in range(1, 101)])

        result = raw_to_ql.convert(source, tmp_path / "rec.bin", DEFS)

        messages = read_ql(tmp_path / "rec.bin")
        assert (result.written, result.ok) == (100, True)
        assert [m.data.id for m in messages] == list(range(1, 101))
        assert [bytes(m.header) for m in messages] == [
            bytes(start(i).header) for i in range(1, 101)
        ]

    def test_undecodable_records_are_left_out_and_counted(self, tmp_path: Path) -> None:
        source = write_raw(
            tmp_path,
            [
                start(1),
                undecoded(td.MT_TEST_START, b"\x00" * 8, 2),  # stale size
                undecoded(7777, b"\x00" * 4, 3),  # unknown type
                start(4),
            ],
        )

        result = raw_to_ql.convert(source, tmp_path / "rec.bin", DEFS)

        assert result.written == 2
        assert result.skipped == {td.MT_TEST_START: 1, 7777: 1}
        assert not result.ok
        assert [m.data.id for m in read_ql(tmp_path / "rec.bin")] == [1, 4]

    def test_undecoded_record_that_decodes_is_kept(self, tmp_path: Path) -> None:
        payload = bytes(start(2).data)
        source = write_raw(
            tmp_path, [start(1), undecoded(td.MT_TEST_START, payload, 2)]
        )

        result = raw_to_ql.convert(source, tmp_path / "rec.bin", DEFS)

        assert (result.written, result.skipped) == (2, {})
        assert [m.data.id for m in read_ql(tmp_path / "rec.bin")] == [1, 2]

    def test_file_cut_short_converts_what_is_readable(self, tmp_path: Path) -> None:
        source = write_raw(tmp_path, [start(i) for i in range(1, 11)])
        record = len(raw.encode_record(start(1).header, start(1).data))
        with RawFile(source) as f:
            cut = f.data_start + 6 * record + 5
        source.write_bytes(source.read_bytes()[:cut])

        result = raw_to_ql.convert(source, tmp_path / "rec.bin", DEFS)

        assert result.written == 6
        assert not result.source_complete
        assert result.damage == [(cut - 5, 5)]
        assert [m.data.id for m in read_ql(tmp_path / "rec.bin")] == list(range(1, 7))

    def test_existing_destination_is_refused_unless_overwrite(
        self, tmp_path: Path
    ) -> None:
        source = write_raw(tmp_path, [start(1)])
        destination = tmp_path / "rec.bin"
        destination.write_bytes(b"keep")

        with pytest.raises(FileExistsError):
            raw_to_ql.convert(source, destination, DEFS)
        kept = destination.read_bytes()
        raw_to_ql.convert(source, destination, DEFS, overwrite=True)

        assert kept == b"keep"
        assert [m.data.id for m in read_ql(destination)] == [1]

    def test_failure_leaves_no_partial_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        source = write_raw(tmp_path, [start(i) for i in range(1, 6)])

        def fail(self: QLFormatter, wbuf: list[Message]) -> int:
            raise OSError("disk full")

        monkeypatch.setattr(QLFormatter, "write", fail)

        with pytest.raises(OSError, match="disk full"):
            raw_to_ql.convert(source, tmp_path / "rec.bin", DEFS)

        assert sorted(p.name for p in tmp_path.iterdir()) == ["rec.dat"]

    def test_data_past_the_spill_threshold_converts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(QLFormatter, "spill_threshold", 100)
        monkeypatch.setattr(raw_to_ql, "BATCH_SIZE", 7)
        source = write_raw(tmp_path, [start(i) for i in range(1, 51)])

        raw_to_ql.convert(source, tmp_path / "rec.bin", DEFS)

        assert [m.data.id for m in read_ql(tmp_path / "rec.bin")] == list(range(1, 51))
        assert sorted(p.name for p in tmp_path.iterdir()) == ["rec.bin", "rec.dat"]

    def test_too_much_for_one_quicklogger_file_raises(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(raw_to_ql, "QL_MAX_BYTES", 200)
        source = write_raw(tmp_path, [start(i) for i in range(1, 51)])

        with pytest.raises(OverflowError, match="QuickLogger"):
            raw_to_ql.convert(source, tmp_path / "rec.bin", DEFS)

        assert not (tmp_path / "rec.bin").exists()

    def test_not_a_raw_file_raises(self, tmp_path: Path) -> None:
        source = tmp_path / "rec.dat"
        source.write_bytes(b"not a raw file at all")

        with pytest.raises(RawFormatError):
            raw_to_ql.convert(source, tmp_path / "rec.bin", DEFS)

        assert sorted(p.name for p in tmp_path.iterdir()) == ["rec.dat"]


class TestCommandLine:
    def test_converts_each_file_into_the_output_folder(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        first = write_raw(tmp_path, [start(1), start(2)], name="rec")
        second = write_raw(tmp_path, [start(3)], name="rec_0001")
        out = tmp_path / "ql"

        status = raw_to_ql.main(
            ["-d", td.__file__, "-o", str(out), str(first), str(second)]
        )

        printed = capsys.readouterr().out
        assert status == 0
        assert sorted(p.name for p in out.iterdir()) == ["rec.bin", "rec_0001.bin"]
        assert "rec.dat -> " in printed
        assert "2 messages" in printed
        messages = read_ql(out / "rec.bin", out / "rec_0001.bin")
        assert [m.data.id for m in messages] == [1, 2, 3]

    def test_problems_are_reported_and_set_the_status(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mixed = write_raw(
            tmp_path, [start(1), undecoded(7777, b"\x00" * 4, 2)], name="mixed"
        )
        missing = tmp_path / "missing.dat"

        status = raw_to_ql.main(["-d", td.__file__, str(mixed), str(missing)])

        captured = capsys.readouterr()
        assert status == 1
        assert "left out, not decodable with these definitions: 7777x1" in captured.out
        assert "missing.dat" in captured.err
        assert (tmp_path / "mixed.bin").exists()
