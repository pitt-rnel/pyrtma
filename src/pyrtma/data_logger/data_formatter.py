"""DataFormatter abstract base class and formatter registration functions"""

import os
import pathlib
from dataclasses import dataclass

import pyrtma
from typing import ClassVar, IO, Any, Sequence
from abc import ABC
from pyrtma.definitions import MessageDefinitions
from .exceptions import DataFormatterKeyError


def _size_on_disk(chunk: str | bytes) -> int:
    """Return how many bytes a chunk takes once written.

    Text is encoded as UTF-8, and each newline counted as the platform's line
    ending, as the data logger opens text files. A file opened with
    ``newline=""`` is overestimated, which only makes it smaller.

    Args:
        chunk: What a formatter writes.

    Returns:
        Its size in bytes.
    """
    if isinstance(chunk, bytes):
        return len(chunk)
    size = len(chunk) if chunk.isascii() else len(chunk.encode("utf-8"))
    return size + chunk.count("\n") * (len(os.linesep) - 1)


@dataclass(frozen=True)
class FileContext:
    """What the data logger tells a formatter about the file it writes.

    Attributes:
        dataset: The dataset's name.
        path: The file being written.
        part: 0 for a dataset's first file, then 1, 2, ... for the files it
            continues in when one is full.
        definitions: The data logger's message definitions, or None if the
            dataset was created without them.
    """

    dataset: str
    path: pathlib.Path
    part: int
    definitions: MessageDefinitions | None


@dataclass(frozen=True)
class UndecodedMessage:
    """A received message the data logger's definitions can't decode.

    Only formatters with ``accepts_undecoded`` are given these.

    Attributes:
        header: The message's RTMA header.
        data: The payload as received.
    """

    header: Any
    data: bytes
    undecoded: ClassVar[bool] = True

    @property
    def type_id(self) -> int:
        """The message type, from the header."""
        return self.header.msg_type


#: What a formatter is given to write: a decoded message, or, only if it sets
#: ``accepts_undecoded``, an :py:class:`UndecodedMessage`.
Recordable = pyrtma.Message | UndecodedMessage


class DataFormatter(ABC):
    name: ClassVar[str] = "base"
    mode: ClassVar[str] = "wt"
    ext: ClassVar[str] = ".txt"
    #: If true, the data logger creates the formatter with a ``context``
    #: keyword argument, a :py:class:`FileContext`. Formatters that don't
    #: set it are created with the file only, as before.
    wants_context: ClassVar[bool] = False
    #: If true, the formatter can record messages the data logger's
    #: definitions can't decode, given as :py:class:`UndecodedMessage`, and
    #: the data logger keeps its datasets recording instead of stopping them.
    accepts_undecoded: ClassVar[bool] = False
    #: The most bytes a file may hold. The data logger continues a dataset in
    #: a new file before a message would pass it. A file always holds at
    #: least one message, even one larger than this. The class value is a
    #: ceiling; the data logger lowers it per file to the dataset's
    #: ``max_size_mb``.
    max_bytes: int = 500_000_000

    def __init__(self, fd: IO[Any], **kwargs):
        self.fd = fd
        #: Bytes in the file so far, the header included.
        self.bytes_written = 0
        #: Messages in the file so far.
        self.messages_written = 0
        # Off while finalizing, which writes whatever it is given.
        self._limit_enabled = True
        self._footer_size: int | None = None
        if hdr := self.format_header():
            self.fd.write(hdr)
            self.bytes_written += _size_on_disk(hdr)

    def format_header(self) -> bytes | str | None:
        return None

    def format_footer(self) -> bytes | str | None:
        return None

    def format_message(self, msg: Recordable) -> str | bytes | None:
        return None

    def _fits(self, size: int, written: int) -> bool:
        """Return whether ``size`` more bytes, and the footer, fit the file.

        Args:
            size: The next message's bytes.
            written: Messages already accepted from this batch.
        """
        if not self._limit_enabled or self.messages_written + written == 0:
            return True
        if self._footer_size is None:
            footer = self.format_footer()
            self._footer_size = _size_on_disk(footer) if footer else 0
        return self.bytes_written + size + self._footer_size <= self.max_bytes

    def write(self, wbuf: Sequence[Recordable]) -> int:
        """Write messages, as many as fit within :py:attr:`max_bytes`.

        Args:
            wbuf: The messages, in order.

        Returns:
            How many messages from the start of ``wbuf`` were written. Fewer
            than all means the file is full: the data logger finishes it and
            writes the rest to a new file. A subclass that overrides this
            and returns None is treated as having written them all.
        """
        chunks: list[str | bytes] = []
        count = 0
        for msg in wbuf:
            chunk = self.format_message(msg)
            if chunk is not None:
                size = _size_on_disk(chunk)
                if not self._fits(size, count):
                    break
                chunks.append(chunk)
                self.bytes_written += size
            count += 1
        self.fd.writelines(chunks)
        self.messages_written += count
        return count

    def finalize(self, wbuf: Sequence[Recordable]):
        """Write the last messages and the footer.

        Every message given is written, even past :py:attr:`max_bytes`; the
        data logger passes none, having written them with :py:meth:`write`.

        Args:
            wbuf: The last messages.
        """
        self._limit_enabled = False
        # Write the last bit of data
        self.write(wbuf)

        # Write an optional footer
        if footer := self.format_footer():
            self.fd.write(footer)

    def discard(self) -> None:
        """Release what the formatter holds after writing has failed.

        The file is closed by the data logger, not finalized. The default
        does nothing.
        """


_formatter_map: dict[str, type[DataFormatter]] = {}


def add_formatter(fmt_cls: type[DataFormatter]):
    assert issubclass(fmt_cls, DataFormatter)
    if _formatter_map.get(fmt_cls.name) is not None:
        raise DataFormatterKeyError(
            msg=f"A DataFormatter already exists with the name: {fmt_cls.name}"
        )

    _formatter_map[fmt_cls.name] = fmt_cls


def get_formatter(name: str) -> type[DataFormatter] | None:
    return _formatter_map.get(name)
