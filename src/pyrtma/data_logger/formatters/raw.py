"""data_logger Raw Formatter: the RTMA raw file format, version 1.

A raw file stores each message exactly as the data logger received it: the
RTMA message header followed by the payload bytes. A file can be read without
the message definitions and decoded later with the right ones.

File layout::

    File       = FileHeader Record* [Trailer]

    FileHeader (integers little-endian)
        magic        8 bytes   FILE_MAGIC, b"RTMARAW" and a zero byte
        version      u16       FORMAT_VERSION
        header_size  u16       bytes in the RTMA message header of each record
        meta_length  u32       bytes of metadata
        metadata     meta_length bytes: a UTF-8 JSON object, below
        header_crc   u32       CRC-32 (zlib.crc32) of every file header byte
                               before it

    Record (integers little-endian)
        sync         u16       RECORD_SYNC, the bytes A5 5A
        flags        u16       bit 0, FLAG_UNDECODED: the data logger's
                               definitions couldn't decode the message, so
                               it was recorded as received; other bits 0
        header       header_size bytes: the RTMA message header as received
        payload      header.num_data_bytes bytes
        crc          u32       CRC-32 of flags, header and payload

    Trailer (integers little-endian), written only when the file is closed
    normally, so its absence marks a file cut short by a crash or power loss
        magic        8 bytes   TRAILER_MAGIC, b"RTMAEND" and a zero byte
        records      u64       records in the file
        crc          u32       CRC-32 of magic and records

The sync word and CRC let a reader reject a damaged record, and a zero-filled
or garbled region, instead of misreading everything after it. It resumes at
the next sync word whose record passes its CRC.

The RTMA header and payload are in the logging machine's byte order, recorded
as ``byte_order`` in the metadata. Metadata keys:

    format          "rtma-raw"
    pyrtma_version  the data logger's pyrtma version
    created_utc     when the file was created, ISO 8601
    clock           {"wall": Unix time, "monotonic": time.perf_counter()},
                    read together when the file was created. Header send and
                    receive times are perf_counter() seconds; this pair maps
                    them to wall time on the logging machine.
    host            the logging machine's host name
    byte_order      "little" or "big"
    dataset         the dataset's name (null if not written by a data logger)
    file            the file's name (null if not written by a data logger)
    part            0 for a dataset's first file, then 1, 2, ...
    definitions     {"compiled_version": ..., "types": [{"id", "name", "size",
                    "hash"}, ...]} for the logger's definitions, or null. A
                    reader can compare these with the definitions it decodes
                    with.
"""

import ctypes
import json
import socket
import struct
import sys
import time
import zlib
from datetime import datetime, timezone
from typing import IO, Any, Callable, ClassVar

import pyrtma
from pyrtma.header import get_header_cls

from ..data_formatter import DataFormatter, FileContext, Recordable

FORMAT_VERSION: int = 1
FILE_MAGIC: bytes = b"RTMARAW\x00"
#: magic, version, header_size, meta_length
FILE_HEADER_PREFIX: struct.Struct = struct.Struct("<8sHHI")
CRC: struct.Struct = struct.Struct("<I")
RECORD_SYNC: int = 0x5AA5
FLAG_UNDECODED: int = 0x0001
#: sync, flags
RECORD_PREFIX: struct.Struct = struct.Struct("<HH")
_FLAGS: struct.Struct = struct.Struct("<H")
_SYNC_BYTES: bytes = _FLAGS.pack(RECORD_SYNC)
TRAILER_MAGIC: bytes = b"RTMAEND\x00"
#: magic, records
TRAILER_PREFIX: struct.Struct = struct.Struct("<8sQ")
TRAILER_SIZE: int = TRAILER_PREFIX.size + CRC.size


def file_metadata(
    context: FileContext | None,
    *,
    wall_clock: Callable[[], float] = time.time,
    perf_clock: Callable[[], float] = time.perf_counter,
    host: Callable[[], str] = socket.gethostname,
    byte_order: str = sys.byteorder,
) -> dict[str, Any]:
    """Build the metadata for a new raw file.

    Args:
        context: The file's context from the data logger, or None.
        wall_clock: Unix time, for ``created_utc`` and the clock pair.
        perf_clock: The clock header times are taken from.
        host: Returns the machine's host name.
        byte_order: The byte order of headers and payloads.

    Returns:
        The metadata, ready to encode as JSON.
    """
    definitions = None
    defs = context.definitions if context is not None else None
    if defs is not None:
        types = sorted(defs.MDF.values(), key=lambda cls: cls.type_id)
        definitions = {
            "compiled_version": defs.compiled_version,
            "types": [
                {
                    "id": t.type_id,
                    "name": t.type_name,
                    "size": t.type_size,
                    "hash": t.type_hash,
                }
                for t in types
            ],
        }
    wall = wall_clock()
    monotonic = perf_clock()
    created = datetime.fromtimestamp(wall, tz=timezone.utc)
    return {
        "format": "rtma-raw",
        "pyrtma_version": pyrtma.__version__,
        "created_utc": created.isoformat(timespec="milliseconds"),
        "clock": {"wall": wall, "monotonic": monotonic},
        "host": host(),
        "byte_order": byte_order,
        "dataset": context.dataset if context is not None else None,
        "file": context.path.name if context is not None else None,
        "part": context.part if context is not None else 0,
        "definitions": definitions,
    }


def encode_record(header: Any, payload: Any, flags: int = 0) -> bytes:
    """Encode one framed record.

    Args:
        header: The RTMA message header.
        payload: The payload, as a message data object or bytes.
        flags: The record's flags.

    Returns:
        The record's bytes.
    """
    body = _FLAGS.pack(flags) + bytes(header) + bytes(payload)
    return _SYNC_BYTES + body + CRC.pack(zlib.crc32(body))


def encode_file_header(metadata: dict[str, Any]) -> bytes:
    """Encode a raw file's header.

    Args:
        metadata: The metadata, as from :py:func:`file_metadata`.

    Returns:
        The header bytes, ending with their CRC.
    """
    meta = json.dumps(metadata, separators=(",", ":")).encode("utf-8")
    prefix = FILE_HEADER_PREFIX.pack(
        FILE_MAGIC, FORMAT_VERSION, ctypes.sizeof(get_header_cls()), len(meta)
    )
    body = prefix + meta
    return body + CRC.pack(zlib.crc32(body))


class RawFormatter(DataFormatter):
    """Writes the raw format described in this module."""

    name: ClassVar[str] = "raw"
    mode: ClassVar[str] = "wb"
    ext: ClassVar[str] = ".dat"
    wants_context: ClassVar[bool] = True
    accepts_undecoded: ClassVar[bool] = True

    def __init__(
        self,
        fd: IO[bytes],
        *,
        context: FileContext | None = None,
        **metadata_sources: Any,
    ) -> None:
        """Start a raw file.

        Args:
            fd: The open file.
            context: The file's context from the data logger, or None.
            **metadata_sources: Passed to :py:func:`file_metadata`, for tests.
        """
        self.context = context
        self._metadata_sources = metadata_sources
        super().__init__(fd)

    def format_header(self) -> bytes:
        return encode_file_header(file_metadata(self.context, **self._metadata_sources))

    def format_footer(self) -> bytes:
        body = TRAILER_PREFIX.pack(TRAILER_MAGIC, self.messages_written)
        return body + CRC.pack(zlib.crc32(body))

    def format_message(self, msg: Recordable) -> bytes:
        flags = FLAG_UNDECODED if getattr(msg, "undecoded", False) else 0
        return encode_record(msg.header, msg.data, flags)
