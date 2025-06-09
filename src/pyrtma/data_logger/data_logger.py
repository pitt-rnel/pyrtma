"""DataLogger class

Run with python -m pyrtma.data_logger
"""

import time

import pyrtma
import pyrtma.core_defs as cd

from pyrtma.exceptions import UnknownMessageType

from .dataset_writer import DatasetWriter
from .data_formatter import get_formatter
from .exceptions import *

from typing import cast


class DataLogger:
    MAX_DATASETS = 6
    ALL_SETS = ("*", "all")

    def __init__(self, rtma_server_ip: str, log_level: int):
        self.mm_ip = rtma_server_ip

        self.client = pyrtma.Client(module_id=cd.MID_DATA_LOGGER, name="data_logger")
        self.client.logger.set_all_levels(log_level)
        self.client.connect(rtma_server_ip, logger_status=True)
        self.logger = self.client.logger
        self.ctrl_msg_types = [
            cd.MT_DATASET_START,
            cd.MT_DATASET_STOP,
            cd.MT_DATASET_PAUSE,
            cd.MT_DATASET_RESUME,
            cd.MT_DATASET_ADD,
            cd.MT_DATASET_REMOVE,
            cd.MT_DATASET_STATUS_REQUEST,
            cd.MT_DATA_LOGGER_CONFIG_REQUEST,
            cd.MT_DATA_LOGGER_RESET,
            cd.MT_EXIT,
            cd.MT_LM_EXIT,
        ]

        # self.client.subscribe(self.ctrl_msg_types)
        self.client.subscribe([cd.ALL_MESSAGE_TYPES])

        self.client.send_module_ready()

        self.client.info("DataLogger connected and waiting for configuration.")

        self.datasets: dict[str, DatasetWriter] = {}

    def update(self, msg: pyrtma.Message):
        dead = []
        for name, ds in self.datasets.items():
            if ds.dead:
                dead.append(name)
            else:
                ds.update(msg)

            if ds.file_saved.is_set():
                self.client.send_message(ds.save_msg)
                ds.file_saved.clear()
                self.logger.info(f"Saved file: {ds.save_msg.filepath}")
            elif ds.error_event.is_set():
                self.client.send_message(ds.error)
                self.client.error(ds.error)

        for name in dead:
            self.rm_dataset(name)

    def rm_dataset(self, name: str, dest_mod_id: int = 0):
        try:
            self.datasets.pop(name)
            reply = cd.MDF_DATASET_REMOVED()
            reply.name = name
            self.client.send_message(reply, dest_mod_id=dest_mod_id)
            self.logger.info(f"Removed dataset: '{name}'")
        except KeyError:
            pass

    def send_status(self, name: str = "all", dest_mod_id: int = 0):
        msg = cd.MDF_DATASET_STATUS()
        msg.timestamp = time.time()

        if name in DataLogger.ALL_SETS:
            for ds in self.datasets.values():
                msg.name = ds.name
                msg.elapsed_time = ds.elapsed_time
                msg.is_recording = ds.recording
                msg.is_paused = ds.paused
                self.client.send_message(msg, dest_mod_id=dest_mod_id)
        else:
            ds = self.datasets.get(name)
            if ds is None:
                raise DatasetNotFound(name, f"Dataset named '{name}' not found.")

            msg.name = ds.name
            msg.elapsed_time = ds.elapsed_time
            msg.is_recording = ds.recording
            msg.is_paused = ds.paused
            self.client.send_message(msg, dest_mod_id=dest_mod_id)

    def send_config(self, dest_mod_id: int = 0):
        msg = cd.MDF_DATA_LOGGER_CONFIG()

        msg.num_datasets = len(self.datasets)

        for i, ds in enumerate(self.datasets.values()):
            d = msg.datasets[i]

            d.name = ds.name
            d.save_path = str(ds.save_path)
            d.filename = ds.filename
            d.formatter = ds.formatter_cls.name
            d.msg_types[: len(ds.msg_types)] = ds.msg_types
            d.subdivide_interval = (
                0 if isinstance(ds.subdivide_interval, float) else ds.subdivide_interval
            )

        self.client.send_message(msg, dest_mod_id=dest_mod_id)

    def start_logging(self, name: str, dest_mod_id: int = 0):
        if name in DataLogger.ALL_SETS:
            for ds in self.datasets.values():
                ds.start()
                self.logger.info(f"Saving Dataset:{ds.name} to {ds.file_path}")
                start_msg = cd.MDF_DATASET_STARTED()
                start_msg.name = ds.name
                self.client.send_message(start_msg)
        else:
            ds = self.datasets.get(name)
            if ds is None:
                raise DatasetNotFound(name, f"Dataset named '{name}' not found.")

            if ds.recording:
                raise DatasetInProgress(
                    name, f"Recording in progresss for dataset '{ds.name}'"
                )

            ds.start()
            start_msg = cd.MDF_DATASET_STARTED()
            start_msg.name = ds.name
            self.client.send_message(start_msg)

        self.send_status(dest_mod_id=dest_mod_id)

    def stop_logging(self, name: str, dest_mod_id: int = 0):
        rm = []
        if name in DataLogger.ALL_SETS:
            for ds in self.datasets.values():
                if not ds.recording:
                    self.logger.warning(f"Dataset {ds.name} is not recording")
                    continue
                ds.stop()
                self.logger.info(f"Stopping dataset: '{ds.name}'")
                rm.append(ds.name)
                stop_msg = cd.MDF_DATASET_STOPPED()
                stop_msg.name = ds.name
                self.client.send_message(stop_msg)
        else:
            ds = self.datasets.get(name)
            if ds is None:
                raise DatasetNotFound(name, f"Dataset named '{name}' not found.")

            if not ds.recording:
                self.logger.warning(f"Dataset {ds.name} is not recording")
                return

            rm.append(ds.name)
            ds.stop()
            self.logger.info(f"Stopping dataset: '{ds.name}'")

            stop_msg = cd.MDF_DATASET_STOPPED()
            stop_msg.name = ds.name
            self.client.send_message(stop_msg)

        self.send_status(dest_mod_id=dest_mod_id)

        # Remove the dataset after stoppping
        for name in rm:
            self.rm_dataset(name)

    def pause_logging(self, name: str, dest_mod_id: int = 0):
        if name in DataLogger.ALL_SETS:
            for ds in self.datasets.values():
                ds.pause()
        else:
            ds = self.datasets.get(name)
            if ds is None:
                raise DatasetNotFound(name, f"Dataset named '{name}' not found.")

            if ds.paused:
                self.logger.warning(f"Dataset {ds.name} is already paused")
                return

            ds.pause()
            self.logger.info(f"Pausing dataset: '{ds.name}'")

        self.send_status(dest_mod_id=dest_mod_id)

    def resume_logging(self, name: str, dest_mod_id: int = 0):
        if name in DataLogger.ALL_SETS:
            for ds in self.datasets.values():
                ds.resume()
        else:
            ds = self.datasets.get(name)
            if ds is None:
                raise DatasetNotFound(name, f"Dataset named '{name}' not found.")

            if not ds.paused:
                self.logger.warning(f"Dataset {ds.name} is not paused")
                return

            ds.resume()
            self.logger.info(f"Resuming dataset: {ds.name}")

        self.send_status(dest_mod_id=dest_mod_id)

    def add_dataset(self, msg: cd.MDF_DATASET_ADD, dest_mod_id: int = 0):
        dataset = DatasetWriter(
            name=msg.dataset.name,
            save_path=msg.dataset.save_path,
            filename=msg.dataset.filename,
            msg_types=msg.dataset.msg_types[:],
            formatter_cls=get_formatter(msg.dataset.formatter),
            subdivide_interval=msg.dataset.subdivide_interval,
        )

        if len(self.datasets) == DataLogger.MAX_DATASETS:
            raise DataLoggerFullError(
                dataset.name, "Logger has maximum allowed datasets configured."
            )

        if dataset.name in self.datasets.keys():
            raise DatasetExistsError(
                dataset.name, f"A dataset with name '{dataset.name}' already exists"
            )

        self.datasets[dataset.name] = dataset
        reply = cd.MDF_DATASET_ADDED()
        reply.name = dataset.name
        self.client.send_message(reply, dest_mod_id=dest_mod_id)

        self.logger.info(f"Added dataset: '{dataset.name}'")

    def reset(self, dest_mod_id: int = 0):
        self.client.info(f"Reset DataLogger. All Datasets will be cleared")
        rm = []
        for ds in self.datasets.values():
            ds.stop()
            rm.append(ds.name)

        for name in rm:
            self.rm_dataset(name, dest_mod_id=dest_mod_id)

    def send_error(self, exc: DataLoggerError):
        err = cd.MDF_DATA_LOGGER_ERROR()
        err.dataset_name = exc.dataset
        err.exc_type = type(exc).__name__
        err.msg = exc.msg
        self.client.send_message(err)

    def run(self):
        try:
            self._running = True
            while self._running:
                try:
                    msg = self.client.read_message(0.100)
                except UnknownMessageType as e:
                    self.client.warning(f"UnknownMessageType: {e.args[0]}")
                    continue

                if msg is None:
                    continue

                try:
                    dest_mod_id = msg.header.dest_mod_id
                    match (msg.data.type_id):
                        case cd.MT_DATASET_START:
                            self.start_logging(
                                cast(str, msg.data.name), dest_mod_id=dest_mod_id
                            )
                        case cd.MT_DATASET_STOP:
                            self.stop_logging(
                                cast(str, msg.data.name), dest_mod_id=dest_mod_id
                            )
                        case cd.MT_DATASET_PAUSE:
                            self.pause_logging(
                                cast(str, msg.data.name), dest_mod_id=dest_mod_id
                            )
                        case cd.MT_DATASET_RESUME:
                            self.resume_logging(
                                cast(str, msg.data.name), dest_mod_id=dest_mod_id
                            )
                        case cd.MT_DATASET_ADD:
                            self.add_dataset(
                                cast(cd.MDF_DATASET_ADD, msg.data),
                                dest_mod_id=dest_mod_id,
                            )
                        case cd.MT_DATASET_REMOVE:
                            self.rm_dataset(
                                cast(str, msg.data.name), dest_mod_id=dest_mod_id
                            )
                        case cd.MT_DATA_LOGGER_RESET:
                            self.reset(dest_mod_id=0)
                        case cd.MT_DATASET_STATUS_REQUEST:
                            self.send_status(
                                cast(str, msg.data.name),
                                dest_mod_id=msg.header.src_mod_id,
                            )
                        case cd.MT_DATA_LOGGER_CONFIG_REQUEST:
                            self.send_config(dest_mod_id=dest_mod_id)
                        case cd.MT_EXIT:
                            if msg.header.dest_mod_id == self.client.module_id:
                                self._running = False
                                self.client.info("Received EXIT request. Closing...")
                        case cd.MT_LM_EXIT:
                            self._running = False
                            self.client.info("Received LM_EXIT request. Closing...")

                    self.update(msg)
                except DataLoggerError as e:
                    self.client.error(e.msg)
                    self.send_error(e)

        except KeyboardInterrupt:
            pass
        finally:
            for ds in self.datasets.values():
                ds.stop()

            if self.client.connected:
                self.client.disconnect()

            self.client.info("DataLogger is exiting...")
