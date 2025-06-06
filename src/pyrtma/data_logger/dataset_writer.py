"""DataSet class used internally by data_logger"""

import pathlib
import io
import math
import time
import threading
import pyrtma

import pyrtma.core_defs as cd
from ..message import Message
from ..core_defs import ALL_MESSAGE_TYPES
from typing import Type, Optional, IO, Any, List

from .data_formatter import DataFormatter
from .exceptions import (
    DatasetExistsError,
    DatasetThreadError,
    DataLoggerError,
    DatasetError,
)


class DatasetWriter:
    MIN_INTERVAL = 30
    MAX_INTERVAL = 600
    CONTINUOUS = math.inf
    WRITE_PERIOD = 15.0

    def __init__(
        self,
        mm_ip: str,
        name: str,
        save_path: str,
        filename: str,
        formatter_cls: Type[DataFormatter],
        subdivide_interval: int,
        msg_types: List[int],
    ):
        self.client = pyrtma.Client(0, name=f"dataset.{name}")
        self.client.connect(mm_ip)
        self.logger = self.client.logger
        self.name = name
        self.save_path = pathlib.Path(save_path)
        self.formatter_cls = formatter_cls

        # Append the formatter extension
        self.filename = filename + formatter_cls.ext
        self.base_file_name = filename

        if subdivide_interval <= 0:
            self.subdivide_interval = DatasetWriter.CONTINUOUS
        elif subdivide_interval < DatasetWriter.MIN_INTERVAL:
            self.subdivide_interval = DatasetWriter.MIN_INTERVAL
        elif subdivide_interval > DatasetWriter.MAX_INTERVAL:
            self.subdivide_interval = DatasetWriter.MAX_INTERVAL
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

        self._dead = False

        self.write_to_disk = threading.Event()
        self.write_finished = threading.Event()

        self.stop_flag = threading.Event()

        self.use_thread = True
        self.write_thread = threading.Thread(target=self.write)

        self.msg_types = [m for m in msg_types if m > 0]
        if ALL_MESSAGE_TYPES in msg_types:
            self.all_sub = True
        else:
            self.all_sub = False

        self._recording = False
        self._paused = False
        self._close = False

        self._elapsed_time = 0.0
        self.ref_time = -1
        self.start_time = -1

        self.subdivide_flag = False
        self.next_subdivide = math.inf
        self.sub_index = 0

        # Save location
        self.save_path.mkdir(parents=True, exist_ok=True)
        self.file_path = self.save_path / self.filename

        if self.file_path.exists():
            raise DatasetExistsError(self.name, f"{self.file_path} already exists.")

    def __del__(self):
        if self._dead:
            return
        else:
            if self.recording:
                self.stop()

    def pause(self):
        elapsed = self.elapsed_time
        self._elapsed_time = elapsed
        self._paused = True

    def resume(self):
        self._paused = False
        self.ref_time = time.time()

    @property
    def elapsed_time(self) -> float:
        if self.stopped:
            return 0

        if self.paused:
            return self._elapsed_time

        return self._elapsed_time + (time.time() - self.ref_time)

    @property
    def total_elapsed_time(self) -> float:
        return time.time() - self.start_time

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def recording(self) -> bool:
        return self._recording

    @property
    def stopped(self) -> bool:
        return not self._recording

    @property
    def dead(self) -> bool:
        return self._dead

    def start(self):
        # Reset some tracking vars
        self.sub_index = 0
        self.subdivide_flag = False

        # Start the write thread
        self.write_thread.start()

        self.logger.info(f"Saving Dataset:{self.name} to {self.file_path}")

        self.fd = open(self.file_path, self.formatter_cls.mode)
        self.formatter = self.formatter_cls(self.fd)
        self.next_subdivide = self.subdivide_interval

        self.start_time = time.time()
        self.ref_time = self.start_time

        self.next_write = DatasetWriter.WRITE_PERIOD
        self._recording = True
        self._paused = False

    def update(self, msg: Optional[Message]):
        if self._paused or not self._recording:
            return

        if not self.write_thread.is_alive():
            raise DatasetThreadError(
                self.name,
                "Data collection write thread is no longer active. Reset the logger.",
            )

        if msg:
            if self.all_sub or msg.type_id in self.msg_types:
                self.rbuf.append(msg)

        elapsed = self.elapsed_time
        if elapsed > self.next_subdivide:
            self.next_subdivide = elapsed + self.subdivide_interval
            self.subdivide_flag = True
            write = True
        elif elapsed > self.next_write:
            write = True
        else:
            write = False

        if write:
            if self.write_to_disk.is_set():
                # TODO: What is the right behavior here?
                self.logger.warning("Unable to write fast enough.")
            else:
                self.next_write = elapsed + DatasetWriter.WRITE_PERIOD
                self.stage_for_write()

    def send_saved(self):
        msg = cd.MDF_DATASET_SAVED()
        msg.name = self.name
        msg.filepath = str(self.file_path)
        self.client.send_message(msg)

    def subdivide(self):
        self.sub_index += 1
        self.formatter.finalize(self.wbuf)

        if self.fd:
            self.fd.close()
            self.send_saved()

        new_filename = (
            f"{self.base_file_name}_{self.sub_index:04d}{self.formatter_cls.ext}"
        )
        self.file_path = self.file_path.parent / new_filename

        if self.file_path.exists():
            raise DatasetExistsError(self.name, f"{self.file_path} already exists.")

        self.logger.info(f"Sub-dividing dataset: {self.file_path}")

        self.fd = open(self.file_path, self.formatter_cls.mode)
        self.formatter = self.formatter_cls(self.fd)

    def stop(self):
        if self.recording:
            self.stop_flag.set()
            self.logger.info(f"Stopping dataset: {self.name}")
            self.start_time = -1
            self.ref_time = -1
            self._recording = False
            self._paused = False
            self.next_write = -1.0
        else:
            self.logger.warning(f"Dataset {self.name} is not recording")

    def send_error(self, exc: DataLoggerError):
        err = cd.MDF_DATA_LOGGER_ERROR()
        err.dataset_name = exc.dataset
        err.exc_type = type(exc).__name__
        err.msg = exc.msg
        self.client.send_message(err)

    def stage_for_write(self):
        """Set the write buffer data for the data collection write thread"""
        self.wbuf = self.rbuf
        self.rbuf = []

        self.write_finished.clear()
        self.write_to_disk.set()

        self.logger.debug("Writing dataset buffers to disk.")

    def write(self):
        """Write Threads main function"""
        try:
            while True:
                if self.write_to_disk.wait(0.5):
                    self.formatter.write(self.wbuf)
                    self.wbuf.clear()

                    if not self.stopped and self.subdivide_flag:
                        self.subdivide_flag = False
                        self.subdivide()

                    self.write_to_disk.clear()
                    self.write_finished.set()
                elif self.stop_flag.is_set():
                    self.stage_for_write()
                    self.formatter.finalize(self.wbuf)
                    if self.fd is not None:
                        self.fd.close()
                        self.send_saved()
                    self._dead = True
                    break

        except KeyboardInterrupt:
            pass
        except DataLoggerError as e:
            self.client.error(e.msg)
            self.send_error(e)
        finally:
            self.logger.debug("Collection write thread exited.")

    def blocking_write(self):
        """Blocking write without bg thread"""
        if self.write_to_disk.wait(0.5):
            self.write()
            self.write_to_disk.clear()
            self.write_finished.set()
