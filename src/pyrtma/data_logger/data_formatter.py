"""DataFormatter abstract base class and formatter registration functions"""

import os

import pyrtma
from typing import Type, Optional, ClassVar, IO, Any, Union, List, Dict
from abc import ABC
from .exceptions import InvalidFormatter, DataFormatterKeyError


def _size_on_disk(chunk: Union[str, bytes]) -> int:
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


class DataFormatter(ABC):
    name: ClassVar[str] = "base"
    mode: ClassVar[str] = "wt"
    ext: ClassVar[str] = ".txt"
    #: The most bytes a file may hold. The data logger continues a dataset in
    #: a new file before a message would pass it. A file always holds at
    #: least one message, even one larger than this.
    max_bytes: ClassVar[int] = 500_000_000

    def __init__(self, fd: IO[Any], **kwargs):
        self.fd = fd
        #: Bytes in the file so far, the header included.
        self.bytes_written = 0
        #: Messages in the file so far.
        self.messages_written = 0
        # Off while finalizing, which writes whatever it is given.
        self._limit_enabled = True
        self._footer_size: Optional[int] = None
        if hdr := self.format_header():
            self.fd.write(hdr)
            self.bytes_written += _size_on_disk(hdr)

    def format_header(self) -> Optional[Union[bytes, str]]:
        return None

    def format_footer(self) -> Optional[Union[bytes, str]]:
        return None

    def format_message(self, msg: pyrtma.Message) -> Optional[Union[str, bytes]]:
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

    def write(self, wbuf: List[pyrtma.Message]) -> int:
        """Write messages, as many as fit within :py:attr:`max_bytes`.

        Args:
            wbuf: The messages, in order.

        Returns:
            How many messages from the start of ``wbuf`` were written. Fewer
            than all means the file is full: the data logger finishes it and
            writes the rest to a new file. A subclass that overrides this
            and returns None is treated as having written them all.
        """
        chunks: list[Union[str, bytes]] = []
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

    def finalize(self, wbuf: List[pyrtma.Message]):
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


_formatter_map: Dict[str, Type[DataFormatter]] = {}


def add_formatter(fmt_cls: Type[DataFormatter]):
    assert issubclass(fmt_cls, DataFormatter)
    if _formatter_map.get(fmt_cls.name) is not None:
        raise DataFormatterKeyError(
            msg=f"A DataFormatter already exists with the name: {fmt_cls.name}"
        )

    _formatter_map[fmt_cls.name] = fmt_cls


def get_formatter(name: str) -> Type[DataFormatter] | None:
    return _formatter_map.get(name)
