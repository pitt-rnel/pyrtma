"""data_logger Raw Formatter"""

import pyrtma

from ..data_formatter import DataFormatter
from typing import ClassVar


class RawFormatter(DataFormatter):
    name: ClassVar[str] = "raw"
    mode: ClassVar[str] = "wb"
    ext: ClassVar[str] = ".dat"

    def format_message(self, msg: pyrtma.Message) -> bytes:
        return bytes(msg.header) + bytes(msg.data)
