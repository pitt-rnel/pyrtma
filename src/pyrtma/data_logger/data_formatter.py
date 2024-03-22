import pyrtma
from typing import Type, Optional, ClassVar, IO, Any
from abc import ABC
from .exceptions import InvalidFormatter, DataFormatterKeyError


_formatter_map = {}


class DataFormatter(ABC):
    name: ClassVar[str] = "base"
    mode: ClassVar[str] = "wt"
    ext: ClassVar[str] = ".txt"

    def __init__(self, fd: IO[Any], **kwargs):
        self.fd = fd
        if hdr := self.format_header():
            self.fd.write(hdr)

    def format_header(self) -> Optional[bytes | str]:
        return None

    def format_footer(self) -> Optional[bytes | str]:
        return None

    def format_message(self, msg: pyrtma.Message) -> Optional[str | bytes]:
        return None

    def write(self, wbuf: list[pyrtma.Message]):
        self.fd.writelines(self.format_message(msg) for msg in wbuf)

    def finalize(self):
        if footer := self.format_footer():
            self.fd.write(footer)


def add_formatter(fmt_cls: Type[DataFormatter]):
    assert issubclass(fmt_cls, DataFormatter)
    if _formatter_map.get(fmt_cls.name) is not None:
        raise DataFormatterKeyError(
            f"A DataFormatter already exists with the name: {fmt_cls.name}"
        )

    _formatter_map[fmt_cls.name] = fmt_cls


def get_formatter(name: str) -> Type[DataFormatter]:
    fmt_cls = _formatter_map.get(name)

    if fmt_cls is not None:
        return fmt_cls
    else:
        raise InvalidFormatter(f"No DataFormatter class named {name}")
