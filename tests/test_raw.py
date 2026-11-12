"""Tests for ``pyrtma.data_logger.formatters.raw``: the raw file format.

Files are written to a ``BytesIO`` with a ``RawFormatter``, or by a real
``DatasetWriter`` into ``tmp_path``, and their bytes are taken apart here
with the format's own constants, independently of ``pyrtma.utils.raw_reader``.
"""

from __future__ import annotations

import ctypes
import io
import json
import zlib
from pathlib import Path
from typing import Any

from pyrtma import core_defs as cd
from pyrtma.data_logger.data_formatter import FileContext, UndecodedMessage
from pyrtma.data_logger.dataset_writer import DatasetWriter
from pyrtma.data_logger.formatters import raw
from pyrtma.header import MessageHeader
from pyrtma.message import Message

from .helpers import FakeClock, wait_for

HEADER_SIZE: int = ctypes.sizeof(MessageHeader)


def message(i: int = 1) -> Message:
    """Make a ``DATASET_STATUS`` message from source 20 with ``msg_count`` ``i``."""
    data = cd.MDF_DATASET_STATUS()
    data.name = f"m{i}"
    header = MessageHeader()
    header.msg_type = data.type_id
    header.num_data_bytes = data.type_size
    header.msg_count = i
    header.src_mod_id = 20
    return Message(header, data)


def parse_file_header(data: bytes) -> tuple[bytes, int, int, dict[str, Any], bool, int]:
    """Take a raw file's header apart.

    Returns:
        The magic, version, header size, metadata, whether the CRC matches,
        and where the records start.
    """
    magic, version, header_size, meta_len = raw.FILE_HEADER_PREFIX.unpack_from(data)
    end = raw.FILE_HEADER_PREFIX.size + meta_len
    (crc,) = raw.CRC.unpack_from(data, end)
    meta = json.loads(data[raw.FILE_HEADER_PREFIX.size : end])
    return magic, version, header_size, meta, crc == zlib.crc32(data[:end]), end + 4


class TestFileHeader:
    def test_header_fields(self) -> None:
        defs = cd.get_message_definitions()
        context = FileContext("ds", Path("/x/rec_0002.dat"), 2, defs)
        buf = io.BytesIO()

        raw.RawFormatter(
            buf,
            context=context,
            wall_clock=lambda: 1_700_000_000.25,
            perf_clock=lambda: 42.5,
            host=lambda: "hub",
            byte_order="little",
        )

        magic, version, header_size, meta, crc_ok, _ = parse_file_header(buf.getvalue())
        assert (magic, version, header_size, crc_ok) == (
            raw.FILE_MAGIC,
            raw.FORMAT_VERSION,
            HEADER_SIZE,
            True,
        )
        assert meta["format"] == "rtma-raw"
        assert (meta["dataset"], meta["file"], meta["part"]) == (
            "ds",
            "rec_0002.dat",
            2,
        )
        assert meta["clock"] == {"wall": 1_700_000_000.25, "monotonic": 42.5}
        assert meta["created_utc"] == "2023-11-14T22:13:20.250+00:00"
        assert (meta["host"], meta["byte_order"]) == ("hub", "little")

    def test_types_table_lists_the_definitions(self) -> None:
        defs = cd.get_message_definitions()
        buf = io.BytesIO()

        raw.RawFormatter(buf, context=FileContext("ds", Path("rec.dat"), 0, defs))

        meta = parse_file_header(buf.getvalue())[3]
        types = {t["name"]: t for t in meta["definitions"]["types"]}
        status = cd.MDF_DATASET_STATUS
        assert types["DATASET_STATUS"] == {
            "id": status.type_id,
            "name": "DATASET_STATUS",
            "size": status.type_size,
            "hash": status.type_hash,
        }
        assert len(types) == len(defs.MDF)
        assert meta["definitions"]["compiled_version"] == defs.compiled_version

    def test_header_without_context(self) -> None:
        buf = io.BytesIO()

        raw.RawFormatter(buf)

        *_, meta, crc_ok, _ = parse_file_header(buf.getvalue())
        assert crc_ok
        assert (meta["dataset"], meta["file"], meta["definitions"]) == (
            None,
            None,
            None,
        )

    def test_dataset_writer_writes_the_header(self, tmp_path: Path) -> None:
        writer = DatasetWriter(
            "ds",
            str(tmp_path),
            "rec",
            "raw",
            0,
            [cd.ALL_MESSAGE_TYPES],
            clock=FakeClock(),
            definitions=cd.get_message_definitions(),
        )
        writer.start()
        writer.update(message())

        writer.stop()

        assert wait_for(lambda: writer.dead), "the write thread didn't end"
        data = (tmp_path / "rec.dat").read_bytes()
        *_, meta, crc_ok, start = parse_file_header(data)
        assert crc_ok
        assert (meta["dataset"], meta["file"]) == ("ds", "rec.dat")
        assert len(data) > start


class TestRecords:
    def test_record_is_framed(self) -> None:
        buf = io.BytesIO()
        formatter = raw.RawFormatter(buf)
        start = len(buf.getvalue())
        msg = message(7)

        written = formatter.write([msg])

        record = buf.getvalue()[start:]
        sync, flags = raw.RECORD_PREFIX.unpack_from(record)
        body_end = raw.RECORD_PREFIX.size + HEADER_SIZE + msg.data.type_size
        (crc,) = raw.CRC.unpack_from(record, body_end)
        assert written == 1
        assert (record[:2], sync, flags) == (b"\xa5\x5a", raw.RECORD_SYNC, 0)
        assert record[4 : 4 + HEADER_SIZE] == bytes(msg.header)
        assert record[4 + HEADER_SIZE : body_end] == bytes(msg.data)
        assert crc == zlib.crc32(record[2:body_end])
        assert len(record) == body_end + raw.CRC.size

    def test_undecoded_message_is_flagged(self) -> None:
        buf = io.BytesIO()
        formatter = raw.RawFormatter(buf)
        start = len(buf.getvalue())
        header = message().header
        header.num_data_bytes = 3

        formatter.write([UndecodedMessage(header, b"\x01\x02\x03")])

        record = buf.getvalue()[start:]
        assert raw.RECORD_PREFIX.unpack_from(record)[1] == raw.FLAG_UNDECODED
        assert record[4 + HEADER_SIZE : 4 + HEADER_SIZE + 3] == b"\x01\x02\x03"

    def test_framing_counts_toward_the_size_limit(self) -> None:
        formatter = raw.RawFormatter(io.BytesIO())
        size = len(raw.encode_record(message().header, message().data))
        # Room for two records and the trailer, which is reserved like a footer.
        formatter.max_bytes = formatter.bytes_written + 2 * size + raw.TRAILER_SIZE

        written = formatter.write([message(i) for i in range(5)])

        assert written == 2


def trailer(data: bytes) -> tuple[bytes, int, bool]:
    """Take apart what would be a raw file's trailer.

    Returns:
        The magic, record count, and whether the CRC matches.
    """
    magic, records = raw.TRAILER_PREFIX.unpack_from(data, len(data) - raw.TRAILER_SIZE)
    (crc,) = raw.CRC.unpack_from(data, len(data) - raw.CRC.size)
    body = data[-raw.TRAILER_SIZE : -raw.CRC.size]
    return magic, records, crc == zlib.crc32(body)


class TestTrailer:
    def test_trailer_written_on_finalize(self) -> None:
        buf = io.BytesIO()
        formatter = raw.RawFormatter(buf)
        formatter.write([message(i) for i in range(3)])

        formatter.finalize([message(9)])

        assert trailer(buf.getvalue()) == (raw.TRAILER_MAGIC, 4, True)

    def test_no_trailer_without_finalize(self) -> None:
        buf = io.BytesIO()
        formatter = raw.RawFormatter(buf)

        formatter.write([message(1)])

        assert trailer(buf.getvalue())[0] != raw.TRAILER_MAGIC

    def test_full_file_counts_only_its_records(self) -> None:
        buf = io.BytesIO()
        formatter = raw.RawFormatter(buf)
        size = len(raw.encode_record(message().header, message().data))
        formatter.max_bytes = formatter.bytes_written + 2 * size + raw.TRAILER_SIZE
        formatter.write([message(i) for i in range(5)])

        formatter.finalize([])

        assert trailer(buf.getvalue())[1] == 2
        assert len(buf.getvalue()) == formatter.max_bytes
