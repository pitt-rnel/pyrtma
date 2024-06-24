import pathlib
import io
import logging
import math

from ..message import Message
from ..core_defs import ALL_MESSAGE_TYPES
from typing import Type, Optional, IO, Any, List

from .metadata import LoggingMetadata
from .data_formatter import DataFormatter
from .exceptions import DataSetExistsError


class DataSet:
    MIN_INTERVAL = 30
    MAX_INTERVAL = 600
    CONTINUOUS = math.inf

    def __init__(
        self,
        collection_name: str,
        name: str,
        sub_dir_fmt: str,
        file_name_fmt: str,
        formatter_cls: Type[DataFormatter],
        subdivide_interval: int,
        msg_types: List[int],
        metadata: LoggingMetadata,
    ):
        self.logger = logging.getLogger("data_logger").getChild(
            f"{collection_name}.{name}"
        )
        self.logger.name = f"{collection_name}.{name}"
        self.collection_name = collection_name
        self.name = name
        self.sub_dir_fmt = sub_dir_fmt
        self.file_name_fmt = file_name_fmt
        self.formatter_cls = formatter_cls

        if subdivide_interval <= 0:
            self.subdivide_interval = DataSet.CONTINUOUS
        elif subdivide_interval < DataSet.MIN_INTERVAL:
            self.subdivide_interval = DataSet.MIN_INTERVAL
        elif subdivide_interval > DataSet.MAX_INTERVAL:
            self.subdivide_interval = DataSet.MAX_INTERVAL
        else:
            self.subdivide_interval = subdivide_interval

        # Placeholder for type checking purposes
        if "b" in self.formatter_cls.mode:
            self.formatter = formatter_cls(io.BytesIO())
        else:
            self.formatter = formatter_cls(io.StringIO())

        self.rbuf: List[Message] = []
        self.wbuf: List[Message] = []

        self.fd: Optional[IO[Any]] = None
        self.file_path = pathlib.Path()
        self.metadata = metadata

        self.msg_types = [m for m in msg_types if m > 0]
        if ALL_MESSAGE_TYPES in msg_types:
            self.all_sub = True
        else:
            self.all_sub = False

        self.subdivide_flag = False
        self.next_subdivide = math.inf
        self.sub_index = 0
        self.collection_stopped = False
        self.base_file_name: str = ""

    def start(self, base_path: pathlib.Path):
        # Reset some tracking vars
        self.sub_index = 0
        self.collection_stopped = False
        self.subdivide_flag = False

        # Expand data set save directory
        save_dir = self.metadata.expand_format(self.sub_dir_fmt)

        save_path = base_path.joinpath(save_dir)
        save_path.mkdir(parents=True, exist_ok=True)

        # Expand data set file name
        filename = self.metadata.expand_format(
            self.file_name_fmt + self.formatter_cls.ext
        )

        self.file_path = save_path / filename

        if self.file_path.exists():
            raise DataSetExistsError(f"{self.file_path} already exists.")

        self.logger.info(f"Saving Data Set:{self.name} to {self.file_path}")

        self.fd = open(self.file_path, self.formatter_cls.mode)
        self.formatter = self.formatter_cls(self.fd)
        self.next_subdivide = self.subdivide_interval

    def subdivide(self):
        self.sub_index += 1
        self.formatter.finalize(self.wbuf)

        if self.fd:
            self.fd.close()

        base_name = self.metadata.expand_format(self.file_name_fmt)
        new_filename = f"{base_name}_{self.sub_index:04d}{self.formatter_cls.ext}"
        self.file_path = self.file_path.parent / new_filename

        if self.file_path.exists():
            raise DataSetExistsError(f"{self.file_path} already exists.")

        self.logger.info(f"Sub-dividing data set: {self.file_path}")

        self.fd = open(self.file_path, self.formatter_cls.mode)
        self.formatter = self.formatter_cls(self.fd)

    def stop(self):
        self.stage_for_write()
        self.formatter.finalize(self.wbuf)

    def close(self):
        if self.fd is not None:
            self.fd.close()

    def stage_for_write(self):
        """Set the write buffer data for the data collection write thread"""
        self.wbuf = self.rbuf
        self.rbuf = []

    def write(self):
        self.formatter.write(self.wbuf)
        self.wbuf.clear()

        if not self.collection_stopped and self.subdivide_flag:
            self.subdivide_flag = False
            self.subdivide()
