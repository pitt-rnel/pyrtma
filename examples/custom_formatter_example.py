import logging

import pyrtma
import pyrtma.core_defs as cd

from pyrtma.data_logger import DataLogger
from pyrtma.data_logger.data_formatter import DataFormatter, add_formatter
from typing import ClassVar, IO


class CustomFormatter(DataFormatter):
    """Custom data formatter that saves time between test packets"""

    name: ClassVar[str] = "custom"
    ext: ClassVar[str] = ".csv"

    def __init__(self, fd: IO[str]):
        self.prev_recv = None
        self.prev_send = None
        super().__init__(fd)

    def format_header(self) -> str:
        return "recv_time,send_time\n"

    def format_footer(self) -> str:
        return ""

    def format_message(self, msg: pyrtma.Message) -> str:
        if isinstance(msg.data, cd.MDF_DATA_LOG_TEST_2048):
            if self.prev_recv is None or self.prev_send is None:
                self.prev_recv = msg.header.recv_time
                self.prev_send = msg.header.send_time
                return ""
            else:
                rtmp = self.prev_recv
                stmp = self.prev_send
                self.prev_recv = msg.header.recv_time
                self.prev_send = msg.header.send_time
                return f"{msg.header.recv_time - rtmp:0.6f},{msg.header.send_time - stmp:0.6}\n"

        return ""


def main():
    DataLogger.LOG_LEVEL = logging.DEBUG
    d = DataLogger("127.0.0.1:7111")
    add_formatter(CustomFormatter)
    d.run()


if __name__ == "__main__":
    main()
