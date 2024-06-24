import pathlib
import logging
import threading
import time

from ..message import Message
from .metadata import LoggingMetadata
from .data_set import DataSet
from .exceptions import (
    DataCollectionThreadError,
    DataCollectionFullError,
    BasePathNotFound,
)

from typing import Optional


class DataCollection:
    MAX_DATA_SETS = 6
    WRITE_PERIOD = 15.0

    def __init__(
        self,
        name: str,
        base_path: str,
        dir_fmt: str,
        metadata: LoggingMetadata,
        use_thread: bool = True,
    ):
        self._dead = False

        self.logger = logging.getLogger("data_logger").getChild(name)
        self.logger.name = name
        self._recording = False
        self._paused = False
        self._close = False

        self._elapsed_time = 0.0
        self.ref_time = -1
        self.start_time = -1
        self.next_write = -1.0

        self.name = name

        self.dir_fmt = dir_fmt

        self.metadata = metadata
        self.datasets: list[DataSet] = []
        self.write_to_disk = threading.Event()
        self.write_finished = threading.Event()

        ex_base_path = self.metadata.expand_format(base_path)
        p = pathlib.Path(ex_base_path)
        if not p.exists() or not p.is_dir():
            raise BasePathNotFound(
                f"The base_path directory specified does not exist: {base_path}"
            )

        self.base_path = p
        self.save_path = p

        if use_thread:
            self.use_thread = use_thread
            self.write_thread = threading.Thread(target=self.write)
            self.write_thread.start()

    def __del__(self):
        if self._dead:
            return
        self.close()

    def close(self):
        self._close = True
        if self.use_thread:
            self.logger.info(f"Waiting for {self.name} write thread to close...")
            self.write_thread.join()

        for ds in self.datasets:
            ds.close()

        self._dead = True

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
    def stopped(self) -> bool:
        return not self._recording

    def start(self):
        if self.use_thread and not self.write_thread.is_alive():
            raise DataCollectionThreadError(
                "Data collection write thread is no longer active. Reset the logger."
            )

        # Expand collection save directory
        save_dir = self.metadata.expand_format(self.dir_fmt)

        p = self.base_path
        self.save_path = p.joinpath(save_dir)

        self.save_path.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Saving collection: {self.name} -> {self.save_path}")

        self.start_time = time.time()
        self.ref_time = self.start_time

        # Start up all the data set files
        for ds in self.datasets:
            ds.start(self.save_path)

        self.next_write = DataCollection.WRITE_PERIOD
        self._recording = True
        self._paused = False

    def stop(self):
        self.logger.info(f"Stopping collection: {self.name} -> {self.save_path}")
        # Check if we are currently writing some data
        if self.write_to_disk.is_set():
            while not self.write_finished.wait(0.250):
                pass

        self.write_to_disk.clear()
        self.write_finished.clear()

        # Close all the Data Set files in the collection
        for ds in self.datasets:
            ds.collection_stopped = True
            ds.stop()
            ds.close()

        self.start_time = -1
        self.ref_time = -1
        self._recording = False
        self._paused = False
        self.next_write = -1.0

        self.logger.info(f"Stopped collection: {self.name}")

    def update_metadata(self, metadata: LoggingMetadata):
        self.metadata = metadata

        for ds in self.datasets:
            ds.metadata = metadata

    def update(self, msg: Optional[Message]):
        if self._paused or not self._recording:
            return

        if self.use_thread and not self.write_thread.is_alive():
            raise DataCollectionThreadError(
                "Data collection write thread is no longer active. Reset the logger."
            )

        write = False
        elapsed = self.elapsed_time
        for ds in self.datasets:
            if msg:
                if ds.all_sub or msg.type_id in ds.msg_types:
                    ds.rbuf.append(msg)

            if elapsed > ds.next_subdivide:
                ds.next_subdivide = elapsed + ds.subdivide_interval
                ds.subdivide_flag = True
                write = True

        if elapsed > self.next_write:
            write = True

        if write:
            if self.write_to_disk.is_set():
                self.logger.warning("Unable to write fast enough.")
            else:
                self.next_write = elapsed + DataCollection.WRITE_PERIOD
                self.trigger_write()

    def trigger_write(self):
        for ds in self.datasets:
            ds.stage_for_write()

        self.write_finished.clear()
        self.write_to_disk.set()

        if not self.use_thread:
            self.blocking_write()
        self.logger.debug("Writing data set buffers to disk.")

    def add_data_set(self, data_set: DataSet):
        if data_set.name in [ds.name for ds in self.datasets]:
            # Remove the entry that we are overwriting
            self.datasets = [ds for ds in self.datasets if ds.name != data_set.name]
            self.logger.info(f"Updated data set: '{data_set.name}'")
        elif len(self.datasets) == DataCollection.MAX_DATA_SETS:
            raise DataCollectionFullError(
                "Collection has maximum allowed data sets configured."
            )
        else:
            self.logger.info(f"Added data set: {self.name}->{data_set.name}")

        self.datasets.append(data_set)

    def rm_data_set(self, name: str):
        self.datasets = [ds for ds in self.datasets if ds.name != name]
        self.logger.info(f"Removed data set: '{name}'")

    def write(self):
        """Write Threads main function"""
        try:
            while not self._close:
                if self.write_to_disk.wait(0.5):
                    for ds in self.datasets:
                        ds.write()
                    self.write_to_disk.clear()
                    self.write_finished.set()
        except KeyboardInterrupt:
            pass
        finally:
            print("Collection write thread exited.")

    def blocking_write(self):
        """Blocking write without bg thread"""
        if self.write_to_disk.wait(0.5):
            for ds in self.datasets:
                ds.write()
            self.write_to_disk.clear()
            self.write_finished.set()
