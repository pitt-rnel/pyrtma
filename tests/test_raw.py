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
from pyrtma.data_logger.data_formatter import FileContext
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
