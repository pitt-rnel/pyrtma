"""DataLogger class

Run with python -m pyrtma.data_logger
"""

import time

import pyrtma
import pyrtma.core_defs as cd

from pyrtma.exceptions import UnknownMessageType

from .dataset import DataSet
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

        self.datasets: dict[str, DataSet] = {}

    def update(self, msg: pyrtma.Message):
        dead = []
        for name, ds in self.datasets.items():
            if ds.dead:
                dead.append(name)
            else:
                ds.update(msg)

        for name in dead:
            self.rm_dataset(name)

    def rm_dataset(self, name: str):
        try:
            self.datasets.pop(name)
            reply = cd.MDF_DATASET_ADDED()
            reply.name = name
            self.client.send_message(reply)
            self.logger.info(f"Removed dataset: '{name}'")
        except KeyError:
            pass

    def send_status(self, name: str = "all"):
        msg = cd.MDF_DATASET_STATUS()
        msg.timestamp = time.time()

        if name in DataLogger.ALL_SETS:
            for ds in self.datasets.values():
                msg.name = ds.name
                msg.elapsed_time = ds.elapsed_time
                msg.is_recording = ds.recording
                msg.is_paused = ds.paused
                self.client.send_message(msg)
        else:
            ds = self.datasets.get(name)
            if ds is None:
                raise DataSetNotFound(f"Dataset named '{name}' not found.")

            msg.name = ds.name
            msg.elapsed_time = ds.elapsed_time
            msg.is_recording = ds.recording
            msg.is_paused = ds.paused
            self.client.send_message(msg)

    def send_config(self):
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

        self.client.send_message(msg)

    def start_logging(self, name: str):
        if name in DataLogger.ALL_SETS:
            for ds in self.datasets.values():
                ds.start()
                start_msg = cd.MDF_DATASET_STARTED()
                start_msg.name = ds.name
                self.client.send_message(start_msg)
        else:
            ds = self.datasets.get(name)
            if ds is None:
                raise DataSetNotFound(f"Dataset named '{name}' not found.")

            if ds.recording:
                raise DataSetInProgress(
                    f"Recording in progresss for dataset '{ds.name}'"
                )

            ds.start()
            start_msg = cd.MDF_DATASET_STARTED()
            start_msg.name = ds.name
            self.client.send_message(start_msg)

        self.send_status()

    def stop_logging(self, name: str):
        rm = []
        if name in DataLogger.ALL_SETS:
            for ds in self.datasets.values():
                ds.stop()
                rm.append(ds.name)
                stop_msg = cd.MDF_DATASET_STOPPED()
                stop_msg.name = ds.name
                self.client.send_message(stop_msg)
        else:
            ds = self.datasets.get(name)
            if ds is None:
                raise DataSetNotFound(f"Dataset named '{name}' not found.")

            rm.append(ds.name)
            ds.stop()

            stop_msg = cd.MDF_DATASET_STOPPED()
            stop_msg.name = ds.name
            self.client.send_message(stop_msg)

        self.send_status()

        # Remove the dataset after stoppping
        for name in rm:
            self.rm_dataset(name)

    def pause_logging(self, name: str):
        if name in DataLogger.ALL_SETS:
            for ds in self.datasets.values():
                ds.pause()
        else:
            ds = self.datasets.get(name)
            if ds is None:
                raise DataSetNotFound(f"Dataset named '{name}' not found.")

            if ds.paused:
                self.logger.warning(f"Dataset {ds.name} is already paused")
                return

            ds.pause()
            self.logger.info(f"Pausing dataset: {ds.name}")

        self.send_status()

    def resume_logging(self, name: str):
        if name in DataLogger.ALL_SETS:
            for ds in self.datasets.values():
                ds.resume()
        else:
            ds = self.datasets.get(name)
            if ds is None:
                raise DataSetNotFound(f"Dataset named '{name}' not found.")

            if not ds.paused:
                self.logger.warning(f"Dataset {ds.name} is not paused")
                return

            ds.resume()
            self.logger.info(f"Resuming dataset: {ds.name}")

        self.send_status()

    def add_dataset(self, msg: cd.MDF_DATASET_ADD):
        dataset = DataSet(
            self.mm_ip,
            name=msg.dataset.name,
            save_path=msg.dataset.save_path,
            filename=msg.dataset.filename,
            msg_types=msg.dataset.msg_types[:],
            formatter_cls=get_formatter(msg.dataset.formatter),
            subdivide_interval=msg.dataset.subdivide_interval,
        )

        if len(self.datasets) == DataLogger.MAX_DATASETS:
            raise DataLoggerFullError("Logger has maximum allowed datasets configured.")

        if dataset.name in self.datasets.keys():
            raise DataSetExistsError(
                f"A dataset with name '{dataset.name}' already exists"
            )

        self.datasets[dataset.name] = dataset
        reply = cd.MDF_DATASET_ADDED()
        reply.name = dataset.name
        self.client.send_message(reply)

        self.logger.info(f"Added dataset: {dataset.name}")

    def reset(self):
        self.client.info(f"Reset DataLogger. All Datasets will be cleared")
        rm = []
        for ds in self.datasets.values():
            ds.stop()
            rm.append(ds.name)

        for name in rm:
            self.rm_dataset(name)

    def send_error(self, msg: str):
        err = cd.MDF_DATA_LOGGER_ERROR()
        err.msg = msg
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
                    match (msg.data.type_id):
                        case cd.MT_DATASET_START:
                            self.start_logging(cast(str, msg.data.name))
                        case cd.MT_DATASET_STOP:
                            self.stop_logging(cast(str, msg.data.name))
                        case cd.MT_DATASET_PAUSE:
                            self.pause_logging(cast(str, msg.data.name))
                        case cd.MT_DATASET_RESUME:
                            self.resume_logging(cast(str, msg.data.name))
                        case cd.MT_DATASET_ADD:
                            self.add_dataset(cast(cd.MDF_DATASET_ADD, msg.data))
                        case cd.MT_DATASET_REMOVE:
                            self.rm_dataset(cast(str, msg.data.name))
                        case cd.MT_DATA_LOGGER_RESET:
                            self.reset()
                        case cd.MT_DATASET_STATUS_REQUEST:
                            self.send_status(cast(str, msg.data.name))
                        case cd.MT_DATA_LOGGER_CONFIG_REQUEST:
                            self.send_config()
                        case cd.MT_EXIT:
                            if msg.header.dest_mod_id == self.client.module_id:
                                self._running = False
                                self.client.info("Received EXIT request. Closing...")
                        case cd.MT_LM_EXIT:
                            self._running = False
                            self.client.info("Received LM_EXIT request. Closing...")

                    self.update(msg)
                except DataLoggerError as e:
                    self.client.error(e.args[0])
                    self.send_error(f"{e.__class__.__name__}:{e.args[0]}")

        except KeyboardInterrupt:
            pass
        finally:
            for ds in self.datasets.values():
                ds.stop()

            if self.client.connected:
                self.client.disconnect()

            self.client.info("DataLogger is exiting...")
