"""data_logger Message Header Formatter"""

import pyrtma

from ..data_formatter import DataFormatter
from typing import ClassVar, IO


class MsgHeaderFormatter(DataFormatter):
    name: ClassVar[str] = "msg_header"
    ext: ClassVar[str] = ".csv"

    def __init__(self, fd: IO[str]):
        super().__init__(fd)

    def format_header(self) -> str:
        hdr_cls = pyrtma.get_header_cls()
        hdr = hdr_cls().to_dict()
        return ",".join(hdr.keys()) + "\n"

    def format_footer(self) -> str:
        return ""

    def format_message(self, msg: pyrtma.Message) -> str:
        d = msg.header.to_dict()
        # One field per column; the newline isn't a field of its own.
        return ",".join(map(str, d.values())) + "\n"
