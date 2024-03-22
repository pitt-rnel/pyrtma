import pyrtma

from ..data_formatter import DataFormatter
from typing import ClassVar


class JsonFormatter(DataFormatter):
    name: ClassVar[str] = "json"
    mode: ClassVar[str] = "wt"
    ext: ClassVar[str] = ".json"

    def format_message(self, msg: pyrtma.Message) -> str:
        return msg.to_json(minify=True) + "\n"
