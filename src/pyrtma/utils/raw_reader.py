"""Read RTMA raw files (``.dat``) written by the data logger's raw formatter.

The format is described in :py:mod:`pyrtma.data_logger.formatters.raw`.
Records are verified as they are read: a record that fails its sync word or
CRC is skipped, the reader resumes at the next good record, and the skipped
byte ranges are reported in :py:attr:`RawFile.damage`.

    with RawFile("trial001.dat") as f:
        print(f.metadata["dataset"])
        for rec in f.records():
            msg = rec.decode(definitions)
        print(f.complete, f.damage)

Command line::

    python -m pyrtma.utils.raw_reader FILE [FILE ...] [-d DEFS_FILE]
"""

from __future__ import annotations

import argparse
import collections
import ctypes
import json
import mmap
import os
import pathlib
import struct
import sys
import zlib
from dataclasses import dataclass, field
from typing import Any, Iterable, Iterator

from pyrtma.data_logger.formatters.raw import (
    CRC,
    FILE_HEADER_PREFIX,
    FLAG_UNDECODED,
    FILE_MAGIC,
    FORMAT_VERSION,
    RECORD_PREFIX,
    RECORD_SYNC,
    TRAILER_MAGIC,
    TRAILER_PREFIX,
    TRAILER_SIZE,
)
from pyrtma.exceptions import InvalidMessageDefinition, RawFormatError
from pyrtma.header import MessageHeader, get_header_cls
from pyrtma.message import Message

_SYNC_BYTES = struct.pack("<H", RECORD_SYNC)


@dataclass(frozen=True)
class RawRecord:
    """One verified record.

    Attributes:
        offset: Where the record starts in the file.
        flags: The record's flags.
        header: The RTMA message header.
        payload: The payload bytes.
    """

    offset: int
    flags: int
    header: MessageHeader
    payload: bytes

    @property
    def undecoded(self) -> bool:
        """The logger couldn't decode this message and recorded it as received.

        It may decode with the sending module's definitions.
        """
        return bool(self.flags & FLAG_UNDECODED)

    def decode(self, definitions: Any) -> Message:
        """Decode the payload with ``definitions``.

        Args:
            definitions: Message definitions, such as from
                ``pyrtma.load_message_definitions()``.

        Returns:
            The decoded message.

        Raises:
            UnknownMessageType: The definitions have no such type.
            InvalidMessageDefinition: The payload's size doesn't match the
                definition.
        """
        msg_cls = definitions.get_msg_cls(self.header.msg_type)
        if msg_cls.type_size != len(self.payload):
            raise InvalidMessageDefinition(
                f"{msg_cls.type_name} is {msg_cls.type_size} bytes in the "
                f"definitions but {len(self.payload)} bytes in the file."
            )
        return Message(self.header, msg_cls.from_buffer_copy(self.payload))


@dataclass
class SourceGaps:
    """Discontinuities in a source module's msg_count.

    Each client counts the messages it sends, and the message manager
    forwards that count unchanged (it sends its own messages with 0). So for
    one source the count rises by exactly 1 per message; a jump means
    messages missing from the files, a drop means the source restarted.
    """

    gaps: list[tuple[int, int, int]] = field(default_factory=list)  # (src, last, next)
    restarts: list[tuple[int, int, int]] = field(default_factory=list)
    last: dict[int, int] = field(default_factory=dict)

    def add(self, header: MessageHeader) -> None:
        """Check one more record's header, in file order.

        Args:
            header: The record's RTMA header.
        """
        count = header.msg_count
        if count == 0:
            return
        src = header.src_mod_id
        prev = self.last.get(src)
        if prev is not None:
            if count <= prev:
                self.restarts.append((src, prev, count))
            elif count != prev + 1:
                self.gaps.append((src, prev, count))
        self.last[src] = count

    @property
    def missing(self) -> int:
        """Messages missing across all the gaps."""
        return sum(b - a - 1 for _, a, b in self.gaps)


def source_gaps(
    records: Iterable[RawRecord], gaps: SourceGaps | None = None
) -> SourceGaps:
    """Check ``msg_count`` continuity per source.

    Args:
        records: Records in file order.
        gaps: The previous file's result, to continue across the files of one
            dataset, or None.

    Returns:
        The gaps and restarts found, including those in ``gaps``.
    """
    gaps = gaps or SourceGaps()
    for rec in records:
        gaps.add(rec.header)
    return gaps


class RawFile:
    """A raw file, memory-mapped.

    Attributes:
        version: The format version.
        header_size: Bytes in each record's RTMA header.
        metadata: The file header's metadata.
        damage: (offset, length) byte ranges skipped as damaged, filled in
            by :py:meth:`records`.
        trailer_records: The record count in the trailer, or None if the
            file has no valid trailer (it was cut short).
        records_read: Records returned by :py:meth:`records`.
    """

    def __init__(self, path: pathlib.Path | str):
        """Open and memory-map a raw file, and read its file header.

        Args:
            path: The file.

        Raises:
            RawFormatError: The file isn't a raw file this pyrtma can read:
                wrong magic, an unsupported version, a damaged file header,
                or records whose RTMA header size differs from this pyrtma's.
            OSError: The file can't be opened.
        """
        self.path = pathlib.Path(path)
        self._file = open(self.path, "rb")
        size = os.fstat(self._file.fileno()).st_size
        self._buf: Any = (
            mmap.mmap(self._file.fileno(), 0, access=mmap.ACCESS_READ) if size else b""
        )
        self._header_cls = get_header_cls()
        self.damage: list[tuple[int, int]] = []
        self.trailer_records: int | None = None
        self.records_read = 0
        try:
            self._read_file_header()
        except Exception:
            self.close()
            raise

    def __enter__(self) -> "RawFile":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def close(self) -> None:
        """Release the memory map and the file."""
        if isinstance(self._buf, mmap.mmap):
            self._buf.close()
        self._file.close()

    def _read_file_header(self) -> None:
        buf = self._buf
        if len(buf) < FILE_HEADER_PREFIX.size + CRC.size:
            raise RawFormatError(f"{self.path}: too short for a raw file header")
        magic, version, header_size, meta_len = FILE_HEADER_PREFIX.unpack_from(buf)
        if magic != FILE_MAGIC:
            raise RawFormatError(f"{self.path}: not a raw file (magic {magic!r})")
        if version != FORMAT_VERSION:
            raise RawFormatError(
                f"{self.path}: format version {version} is not supported"
            )
        end = FILE_HEADER_PREFIX.size + meta_len
        if end + CRC.size > len(buf):
            raise RawFormatError(f"{self.path}: file header is cut short")
        (crc,) = CRC.unpack_from(buf, end)
        if crc != zlib.crc32(buf[:end]):
            raise RawFormatError(f"{self.path}: file header fails its CRC")
        if header_size != ctypes.sizeof(self._header_cls):
            raise RawFormatError(
                f"{self.path}: records have {header_size}-byte RTMA headers; this "
                f"pyrtma's are {ctypes.sizeof(self._header_cls)} bytes"
            )
        self.version = version
        self.header_size = header_size
        self.metadata: dict[str, Any] = json.loads(
            bytes(buf[FILE_HEADER_PREFIX.size : end])
        )
        self.data_start = end + CRC.size

    # ------------------------------------------------------------------

    def _record_at(self, p: int) -> RawRecord | None:
        """The verified record at ``p``, or None."""
        buf, hs = self._buf, self.header_size
        start = p + RECORD_PREFIX.size
        if start + hs + CRC.size > len(buf):
            return None
        sync, flags = RECORD_PREFIX.unpack_from(buf, p)
        if sync != RECORD_SYNC:
            return None
        header = self._header_cls.from_buffer_copy(buf, start)
        size = header.num_data_bytes
        end = start + hs + size
        if size < 0 or end + CRC.size > len(buf):
            return None
        (crc,) = CRC.unpack_from(buf, end)
        if crc != zlib.crc32(buf[p + 2 : end]):
            return None
        return RawRecord(p, flags, header, bytes(buf[start + hs : end]))

    def _trailer_at(self, p: int) -> int | None:
        """The trailer's record count if a valid trailer ends the file at ``p``."""
        buf = self._buf
        if (
            len(buf) - p != TRAILER_SIZE
            or buf[p : p + len(TRAILER_MAGIC)] != TRAILER_MAGIC
        ):
            return None
        (crc,) = CRC.unpack_from(buf, p + TRAILER_PREFIX.size)
        if crc != zlib.crc32(buf[p : p + TRAILER_PREFIX.size]):
            return None
        return TRAILER_PREFIX.unpack_from(buf, p)[1]

    def _resync(self, start: int) -> int | None:
        """Offset of the next good record or trailer at or after ``start``."""
        buf = self._buf
        trailer_at = len(buf) - TRAILER_SIZE
        i = start
        while True:
            i = buf.find(_SYNC_BYTES, i)
            if i < 0 or i >= trailer_at:
                break
            if self._record_at(i) is not None:
                return i
            i += 1
        if trailer_at >= start and self._trailer_at(trailer_at) is not None:
            return trailer_at
        return None

    def records(self) -> Iterator[RawRecord]:
        """Read the file's records, skipping damage.

        Damaged ranges are recorded in :py:attr:`damage`, and a valid trailer
        in :py:attr:`trailer_records`.

        Yields:
            Each verified record, in file order.
        """
        self.damage, self.trailer_records, self.records_read = [], None, 0
        buf, p = self._buf, self.data_start
        while p < len(buf):
            count = self._trailer_at(p)
            if count is not None:
                self.trailer_records = count
                return
            rec = self._record_at(p)
            if rec is not None:
                self.records_read += 1
                yield rec
                p += RECORD_PREFIX.size + self.header_size + len(rec.payload) + CRC.size
                continue
            q = self._resync(p + 1)
            self.damage.append((p, (len(buf) if q is None else q) - p))
            if q is None:
                return
            p = q

    @property
    def complete(self) -> bool:
        """After :py:meth:`records`: the file was closed normally and every
        record it counts was read intact."""
        return not self.damage and self.trailer_records == self.records_read

    def definition_mismatches(self, definitions: Any) -> list[str]:
        """How ``definitions`` differ from those that wrote the file.

        Args:
            definitions: Message definitions to compare.

        Returns:
            One line per message type whose size or hash differs, or that
            only one side has; empty if they match or the file has no
            definitions table.
        """
        table = (self.metadata.get("definitions") or {}).get("types")
        if table is None:
            return []
        theirs = {t["id"]: t for t in table}
        ours = {cls.type_id: cls for cls in definitions.MDF.values()}
        out = []
        for type_id in sorted(set(theirs) | set(ours)):
            if type_id not in theirs:
                name = ours[type_id].type_name
                out.append(f"{type_id} ({name}): not in the file's definitions")
                continue
            t = theirs[type_id]
            if type_id not in ours:
                out.append(f"{type_id} ({t['name']}): not in these definitions")
                continue
            cls = ours[type_id]
            if (t["size"], t["hash"]) != (cls.type_size, cls.type_hash):
                out.append(
                    f"{type_id} ({t['name']}): file size {t['size']} hash {t['hash']}, "
                    f"here size {cls.type_size} hash {cls.type_hash}"
                )
        return out


def main(argv: list[str] | None = None) -> int:
    """Check and summarize raw files, printing one report per file.

    Args:
        argv: Command line arguments, or None for ``sys.argv``.

    Returns:
        0 if every file is complete, otherwise 1.
    """
    ap = argparse.ArgumentParser(description="Check and summarize RTMA raw files.")
    ap.add_argument(
        "files",
        nargs="+",
        help="files in recording order; msg_count " "continuity is checked across them",
    )
    ap.add_argument("-d", "--defs", help="compiled message definitions to compare with")
    args = ap.parse_args(argv)

    definitions = None
    if args.defs:
        import pyrtma

        definitions = pyrtma.load_message_definitions(args.defs)
    gaps: SourceGaps | None = None
    status = 0
    for path in args.files:
        try:
            f = RawFile(path)
        except (RawFormatError, OSError) as e:
            print(f"{path}: {e}")
            status = 1
            continue
        with f:
            types: collections.Counter = collections.Counter()
            undecoded: collections.Counter = collections.Counter()
            gaps = gaps or SourceGaps()
            for rec in f.records():
                types[rec.header.msg_type] += 1
                if rec.undecoded:
                    undecoded[rec.header.msg_type] += 1
                gaps.add(rec.header)
            meta = f.metadata
            state = (
                "complete"
                if f.complete
                else (
                    "cut short (no trailer)" if f.trailer_records is None else "damaged"
                )
            )
            print(
                f"{pathlib.Path(path).name}: {f.records_read} records, {state}; dataset "
                f"{meta.get('dataset')!r} part {meta.get('part')}, pyrtma "
                f"{meta.get('pyrtma_version')}"
            )
            for off, length in f.damage:
                print(f"  damage: {length} bytes at offset {off}")
            print("  types: " + ", ".join(f"{t}x{n}" for t, n in sorted(types.items())))
            if undecoded:
                listed = ", ".join(f"{t}x{n}" for t, n in sorted(undecoded.items()))
                print(f"  undecoded (the logger's definitions didn't match): {listed}")
            if definitions is not None:
                for line in f.definition_mismatches(definitions):
                    print(f"  definitions: {line}")
            if not f.complete:
                status = 1
    if gaps is not None:
        print(
            f"msg_count: {len(gaps.gaps)} gap(s), {gaps.missing} messages missing, "
            f"{len(gaps.restarts)} source restart(s)"
        )
        for src, a, b in gaps.gaps:
            print(f"  gap: MID {src} {a} -> {b}")
    return status


if __name__ == "__main__":
    sys.exit(main())
