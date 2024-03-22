import pyrtma
import os
import sys
import shutil
import tempfile

from pyrtma.utils.quicklogger_reader import QLFileHeader
from ..data_formatter import DataFormatter
from typing import ClassVar, IO


class QLFormatter(DataFormatter):
    name: ClassVar[str] = "quicklogger"
    mode: ClassVar[str] = "wb"
    ext: ClassVar[str] = ".bin"

    def __init__(self, fd: IO[bytes]):
        # Initialize the quicklogger file header
        hdr = pyrtma.get_header_cls()
        self.ql_header = QLFileHeader()
        self.ql_header.format_version = 1
        self.ql_header.num_messages = 0
        self.ql_header.message_header_size = hdr().size
        self.ql_header.data_block_offset_size = 4
        self.ql_header.total_bytes = self.ql_header.size

        self.ofs = 0
        self.offsets: list[int] = []
        self.msgbuf = []

        self.data_tmp = tempfile.NamedTemporaryFile()
        # print(f"TempFile: {self.data_tmp.name}")

        super().__init__(fd)

    def format_header(self) -> bytes:
        # Initially add a placeholder for the
        return bytes(self.ql_header)

    def format_message(self, msg: pyrtma.Message) -> bytes:
        self.offsets.append(self.ofs)
        self.ofs += msg.data.type_size

        self.ql_header.num_messages += 1
        self.ql_header.num_data_bytes += msg.data.type_size
        self.ql_header.total_bytes += (
            self.ql_header.data_block_offset_size + msg.data.type_size + msg.header.size
        )

        return bytes(msg.header)

    def write(self, wbuf: list[pyrtma.Message]):
        super().write(wbuf)
        self.update_file_header()

        # Append the message data to the temp file
        # Note: This data gets copied and appended at the end
        # to preserve the QL v1 format
        self.data_tmp.writelines(bytes(msg.data) for msg in wbuf)

    def write_offsets(self):
        ofs = b"".join(x.to_bytes(4, byteorder=sys.byteorder) for x in self.offsets)
        self.fd.write(ofs)

    def update_file_header(self):
        self.fd.seek(0, os.SEEK_SET)
        self.fd.write(bytes(self.ql_header))
        self.fd.seek(0, os.SEEK_END)

    def copy_data(self):
        # Reset the file pointer back to the start
        self.data_tmp.seek(os.SEEK_SET)

        # Append the message data tempfile to the data set file
        shutil.copyfileobj(self.data_tmp, self.fd)

    def finalize(self):
        self.write_offsets()
        self.copy_data()
        self.data_tmp.close()
