"""data_logger legacy QuickLogger Formatter

The QuickLogger version 1 layout can't be written as one stream: a file
header, then every message header, then a 32-bit offset per message, then
all the message data, so the data's position depends on how many messages the
file ends up holding. Headers go straight into the file as they arrive; the
data waits in a :py:class:`_SpillBuffer` and is appended when the file is
finished.
"""

import array
import ctypes
import io
import os
import pathlib
import shutil
import tempfile

import pyrtma

from pyrtma.utils.log_reader import BinFileHeader
from ..data_formatter import DataFormatter
from typing import ClassVar, IO, List, Optional

# The array type code for 32-bit unsigned offsets, as the format stores them.
_OFFSET_TYPECODE = next(t for t in "IL" if array.array(t).itemsize == 4)

# The largest file the v1 header's 32-bit sizes can describe.
_V1_MAX_BYTES = 0xFFFFFFFF


class _SpillBuffer:
    """Message data for the end of a QuickLogger file.

    It is kept in memory until it would pass a threshold, then moved to a file
    beside the recording, named by adding a suffix to the recording's name, so
    that a left-over one shows what it was. That file is deleted when the
    recording is finished or discarded. A file left by a crashed logger is
    simply replaced; the recording it belonged to can't be finished.
    """

    def __init__(self, path: Optional[pathlib.Path], threshold: int):
        """Start an empty buffer.

        Args:
            path: Where to spill to, or None to spill to an anonymous file in
                the system's temporary folder.
            threshold: The most bytes to keep in memory.
        """
        self._path = path
        self._threshold = threshold
        self._memory: Optional[io.BytesIO] = io.BytesIO()
        self._file: Optional[IO[bytes]] = None

    @property
    def spilled(self) -> bool:
        """True once the data has moved from memory to a file."""
        return self._file is not None

    def write(self, data: bytes) -> None:
        """Add data at the end.

        Args:
            data: The bytes.
        """
        if self._file is None:
            assert self._memory is not None
            if self._memory.tell() + len(data) <= self._threshold:
                self._memory.write(data)
                return
            self._spill()
        assert self._file is not None
        self._file.write(data)

    def _spill(self) -> None:
        """Move the data held in memory to the spill file."""
        assert self._memory is not None
        if self._path is None:
            spill: IO[bytes] = tempfile.TemporaryFile()
        else:
            spill = open(self._path, "w+b")
        spill.write(self._memory.getbuffer())
        self._memory = None
        self._file = spill

    def copy_to(self, fd: IO[bytes]) -> None:
        """Append all the data to a file.

        Args:
            fd: The recording, positioned at its end.
        """
        if self._file is None:
            assert self._memory is not None
            fd.write(self._memory.getbuffer())
            return
        self._file.seek(0, os.SEEK_SET)
        shutil.copyfileobj(self._file, fd, 1 << 20)

    def discard(self) -> None:
        """Free the memory, and close and delete the spill file."""
        self._memory = None
        if self._file is not None:
            self._file.close()
            self._file = None
            if self._path is not None:
                self._path.unlink(missing_ok=True)


class QLFormatter(DataFormatter):
    name: ClassVar[str] = "quicklogger"
    mode: ClassVar[str] = "wb"
    ext: ClassVar[str] = ".bin"
    #: Message data kept in memory per file before it moves to a spill file.
    spill_threshold: ClassVar[int] = 32 * 1024 * 1024
    #: Added to the recording's name to name its spill file, which is deleted
    #: when the recording is finished.
    spill_suffix: ClassVar[str] = ".tmp"

    def __init__(self, fd: IO[bytes]):
        # Initialize the quicklogger file header
        hdr = pyrtma.get_header_cls()
        self.ql_header = BinFileHeader()
        self.ql_header.format_version = 1
        self.ql_header.num_messages = 0
        self.ql_header.message_header_size = ctypes.sizeof(hdr)
        self.ql_header.data_block_offset_size = 4
        self.ql_header.total_bytes = ctypes.sizeof(self.ql_header)

        self.ofs = 0
        #: Each message's data offset, 4 bytes apiece.
        self.offsets = array.array(_OFFSET_TYPECODE)

        name = getattr(fd, "name", None)
        spill_path = (
            pathlib.Path(name + type(self).spill_suffix)
            if isinstance(name, str)
            else None
        )
        self.data = _SpillBuffer(spill_path, type(self).spill_threshold)

        super().__init__(fd)

    def format_header(self) -> bytes:
        # Initially add a placeholder for the
        return bytes(self.ql_header)

    def write(self, wbuf: List[pyrtma.Message]) -> int:
        """Write messages' headers, and buffer their data.

        The file's size is known exactly as it grows, so a message is left
        for the next file if the finished file would pass ``max_bytes``, or
        the 4 GiB that the format's 32-bit sizes allow, whichever is less.

        Args:
            wbuf: The messages, in order.

        Returns:
            How many messages from the start of ``wbuf`` were taken.
        """
        per_message = (
            self.ql_header.message_header_size + self.ql_header.data_block_offset_size
        )
        limit = min(self.max_bytes, _V1_MAX_BYTES)
        count = 0
        for msg in wbuf:
            size = per_message + msg.data.type_size
            if (
                self._limit_enabled
                and self.messages_written + count > 0
                and self.ql_header.total_bytes + size > limit
            ):
                break
            self.offsets.append(self.ofs)
            self.ofs += msg.data.type_size
            self.ql_header.num_messages += 1
            self.ql_header.num_data_bytes += msg.data.type_size
            self.ql_header.total_bytes += size
            count += 1

        if count:
            batch = wbuf[:count]
            self.fd.write(b"".join(bytes(msg.header) for msg in batch))
            self.update_file_header()
            # The data is appended when the file is finished, to keep the v1
            # layout.
            self.data.write(b"".join(bytes(msg.data) for msg in batch))
            self.messages_written += count
            self.bytes_written = self.ql_header.total_bytes
        return count

    def write_offsets(self):
        self.fd.write(self.offsets.tobytes())

    def update_file_header(self):
        self.fd.seek(0, os.SEEK_SET)
        self.fd.write(bytes(self.ql_header))
        self.fd.seek(0, os.SEEK_END)

    def finalize(self, wbuf: List[pyrtma.Message]):
        """Write the last messages, the offsets and the data.

        Args:
            wbuf: The last messages; all of them are written.
        """
        self._limit_enabled = False
        if wbuf:
            self.write(wbuf)
        self.write_offsets()
        self.data.copy_to(self.fd)
        self.data.discard()

    def discard(self) -> None:
        """Free the buffered data and delete the spill file."""
        self.data.discard()
