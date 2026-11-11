"""Tests for ``pyrtma.utils.raw_reader``: reading, damage recovery, decoding.

Files are written by a real ``DatasetWriter`` with the ``raw`` formatter into
``tmp_path``. Damaged copies are made by editing those bytes.
"""

from __future__ import annotations

import ctypes
import zlib
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from pyrtma import core_defs as cd
from pyrtma.data_logger.data_formatter import UndecodedMessage
from pyrtma.data_logger.dataset_writer import DatasetWriter
from pyrtma.data_logger.formatters import raw
from pyrtma.exceptions import InvalidMessageDefinition, RawFormatError
from pyrtma.header import MessageHeader
from pyrtma.message import Message
from pyrtma.utils import raw_reader
from pyrtma.utils.raw_reader import RawFile, RawRecord, source_gaps

from .helpers import FakeClock, wait_for

DEFS = cd.get_message_definitions()


def message(i: int) -> Message:
    """Make a ``DATASET_STATUS`` from source 20 with ``msg_count`` ``i``."""
    data = cd.MDF_DATASET_STATUS()
    data.name = f"m{i}"
    data.elapsed_time = float(i)
    header = MessageHeader()
    header.msg_type = data.type_id
    header.num_data_bytes = data.type_size
    header.msg_count = i
    header.src_mod_id = 20
    return Message(header, data)


RECORD_SIZE: int = len(raw.encode_record(message(1).header, message(1).data))


def write(
    tmp_path: Path, count: int, max_size_mb: int = 500, undecoded: int = 0
) -> list[Path]:
    """Record messages 1 to ``count`` to ``rec*.dat`` and finish the files.

    Args:
        tmp_path: The folder.
        count: Messages to record.
        max_size_mb: The dataset's file size limit.
        undecoded: Undecoded 3-byte messages to record after them.

    Returns:
        The files, in order.
    """
    writer = DatasetWriter(
        "ds",
        str(tmp_path),
        "rec",
        "raw",
        0,
        [cd.ALL_MESSAGE_TYPES],
        max_size_mb=max_size_mb,
        clock=FakeClock(),
        definitions=DEFS,
    )
    writer.start()
    for i in range(1, count + 1):
        writer.update(message(i))
    for i in range(undecoded):
        header = message(count + 1 + i).header
        header.num_data_bytes = 3
        writer.update(UndecodedMessage(header, b"\xaa\xbb\xcc"))
    writer.stop()
    assert wait_for(lambda: writer.dead), "the write thread didn't end"
    return sorted(tmp_path.glob("rec*.dat"))


def read(path: Path) -> tuple[RawFile, list[RawRecord]]:
    with RawFile(path) as f:
        return f, list(f.records())


@pytest.fixture
def written(tmp_path: Path) -> Path:
    """A finished file of 1000 records."""
    return write(tmp_path, 1000)[0]


@pytest.fixture
def damaged(
    written: Path, tmp_path: Path
) -> Callable[[Callable[[bytearray], bytearray | None]], Path]:
    """Make a copy of ``written`` changed by an edit function."""

    def make(edit: Callable[[bytearray], bytearray | None]) -> Path:
        data = bytearray(written.read_bytes())
        data = edit(data) or data
        out = tmp_path / "damaged.dat"
        out.write_bytes(bytes(data))
        return out

    return make


def record_offset(path: Path, index: int) -> int:
    with RawFile(path) as f:
        return f.data_start + index * RECORD_SIZE


class TestReading:
    def test_intact_file_reads_completely(self, written: Path) -> None:
        f, records = read(written)

        assert f.complete
        assert (len(records), f.trailer_records, f.damage) == (1000, 1000, [])
        assert (f.metadata["dataset"], f.metadata["part"]) == ("ds", 0)
        decoded = records[41].decode(DEFS)
        assert (decoded.data.name, decoded.data.elapsed_time) == ("m42", 42.0)

    def test_parts_continue_without_gaps(self, tmp_path: Path) -> None:
        count = int(1.5e6 / RECORD_SIZE)  # two 1 MB parts

        paths = write(tmp_path, count, max_size_mb=1)

        gaps = None
        total = 0
        for part, path in enumerate(paths):
            f, records = read(path)
            assert f.complete
            assert f.metadata["part"] == part
            gaps = source_gaps(records, gaps)
            total += len(records)
        assert [p.name for p in paths] == ["rec.dat", "rec_0001.dat"]
        assert gaps is not None
        assert (total, gaps.gaps, gaps.restarts) == (count, [], [])

    def test_gaps_and_restarts_per_source(self) -> None:
        headers = [message(i).header for i in (1, 2, 5, 6, 1, 2)]
        records = [RawRecord(0, 0, h, b"") for h in headers]

        gaps = source_gaps(records)

        assert (gaps.gaps, gaps.restarts, gaps.missing) == (
            [(20, 2, 5)],
            [(20, 6, 1)],
            2,
        )


class TestDamage:
    def test_file_cut_short_mid_record(
        self, written: Path, damaged: Callable[..., Path]
    ) -> None:
        cut = record_offset(written, 600) + 30

        f, records = read(damaged(lambda d: d[:cut]))

        assert len(records) == 600
        assert f.trailer_records is None
        assert not f.complete
        assert f.damage == [(record_offset(written, 600), 30)]

    def test_zero_filled_tail_gives_no_records(
        self, written: Path, damaged: Callable[..., Path]
    ) -> None:
        f, records = read(damaged(lambda d: d[: -raw.TRAILER_SIZE] + bytes(4096)))

        assert len(records) == 1000
        assert f.damage == [(record_offset(written, 1000), 4096)]

    def test_flipped_length_bit_loses_one_record(
        self, written: Path, damaged: Callable[..., Path]
    ) -> None:
        length = getattr(MessageHeader, "_num_data_bytes").offset
        offset = record_offset(written, 9) + raw.RECORD_PREFIX.size + length

        def flip(d: bytearray) -> None:
            d[offset] ^= 0x04

        f, records = read(damaged(flip))

        assert len(records) == 999
        assert [r.header.msg_count for r in records[8:11]] == [9, 11, 12]
        assert f.damage == [(record_offset(written, 9), RECORD_SIZE)]
        assert (f.trailer_records, f.complete) == (1000, False)

    def test_flipped_payload_bit_loses_one_record(
        self, written: Path, damaged: Callable[..., Path]
    ) -> None:
        offset = record_offset(written, 500) + 100

        def flip(d: bytearray) -> None:
            d[offset] ^= 0x10

        f, records = read(damaged(flip))

        assert len(records) == 999
        assert 501 not in [r.header.msg_count for r in records]

    def test_garbage_with_a_false_sync_word_is_skipped(
        self, written: Path, damaged: Callable[..., Path]
    ) -> None:
        offset = record_offset(written, 300)
        garbage = b"\xa5\x5a" + bytes(range(256)) * 4

        def insert(d: bytearray) -> None:
            d[offset:offset] = garbage

        f, records = read(damaged(insert))

        assert len(records) == 1000
        assert f.damage == [(offset, len(garbage))]

    @pytest.mark.parametrize("damage", ["magic", "crc", "short"])
    def test_damaged_file_header_raises(
        self, damaged: Callable[..., Path], damage: str
    ) -> None:
        def edit(d: bytearray) -> bytearray | None:
            if damage == "short":
                return d[:10]
            d[0 if damage == "magic" else 20] ^= 0x01
            return None

        path = damaged(edit)

        with pytest.raises(RawFormatError):
            RawFile(path)

    def test_header_size_mismatch_raises(self, damaged: Callable[..., Path]) -> None:
        def edit(d: bytearray) -> None:
            meta_len = raw.FILE_HEADER_PREFIX.unpack_from(d)[3]
            d[10:12] = (ctypes.sizeof(MessageHeader) + 8).to_bytes(2, "little")
            end = raw.FILE_HEADER_PREFIX.size + meta_len
            d[end : end + 4] = raw.CRC.pack(zlib.crc32(bytes(d[:end])))

        with pytest.raises(RawFormatError, match="RTMA headers"):
            RawFile(damaged(edit))


class TestDefinitions:
    def test_decode_with_mismatched_definitions_raises(self, tmp_path: Path) -> None:
        _, (record,) = read(write(tmp_path, 1)[0])
        small = SimpleNamespace(type_size=4, type_name="SMALL")
        definitions = SimpleNamespace(get_msg_cls=lambda msg_type: small)

        with pytest.raises(InvalidMessageDefinition):
            record.decode(definitions)

    def test_undecoded_records_are_marked(self, tmp_path: Path) -> None:
        f, records = read(write(tmp_path, 2, undecoded=1)[0])

        assert f.complete
        assert [r.undecoded for r in records] == [False, False, True]
        assert records[2].payload == b"\xaa\xbb\xcc"
        with pytest.raises(InvalidMessageDefinition):
            records[2].decode(DEFS)

    def test_definition_mismatches_name_the_type(self, tmp_path: Path) -> None:
        status = cd.MDF_DATASET_STATUS
        changed = SimpleNamespace(
            type_id=status.type_id,
            type_name=status.type_name,
            type_size=status.type_size + 8,
            type_hash=status.type_hash,
        )
        other = SimpleNamespace(MDF={**DEFS.MDF, "DATASET_STATUS": changed})

        with RawFile(write(tmp_path, 1)[0]) as f:
            same = f.definition_mismatches(DEFS)
            different = f.definition_mismatches(other)

        assert same == []
        assert len(different) == 1
        assert "DATASET_STATUS" in different[0]


def test_command_line_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (path,) = write(tmp_path, 10)

    status = raw_reader.main([str(path)])

    out = capsys.readouterr().out
    assert status == 0
    assert "10 records, complete" in out
    assert "0 gap(s)" in out
    assert "undecoded" not in out


def test_command_line_lists_undecoded_records(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (path,) = write(tmp_path, 2, undecoded=2)

    raw_reader.main([str(path)])

    status_type = cd.MDF_DATASET_STATUS.type_id
    assert f"undecoded (the logger's definitions didn't match): {status_type}x2" in (
        capsys.readouterr().out
    )
