import time

import pyrtma
import pyrtma.core_defs as cd

from pyrtma.exceptions import UnknownMessageType

from .data_set import DataSet
from .data_formatter import get_formatter
from .exceptions import *


class DataLogger:
    MAX_DATA_SETS = 6
    ALL_SETS = ("*", "all")

    def __init__(self, rtma_server_ip: str, log_level: int):
        self.client = pyrtma.Client(module_id=cd.MID_DATA_LOGGER, name="data_logger")
        self.client.logger.level = log_level
        self.client.connect(rtma_server_ip, logger_status=True)
        self.logger = self.client.logger
        self.ctrl_msg_types = [
            cd.MT_DATA_SET_START,
            cd.MT_DATA_SET_STOP,
            cd.MT_DATA_SET_PAUSE,
            cd.MT_DATA_SET_RESUME,
            cd.MT_DATA_SET_ADD,
            cd.MT_DATA_SET_REMOVE,
            cd.MT_DATA_SET_STATUS_REQUEST,
            cd.MT_DATA_LOGGER_CONFIG_REQUEST,
            cd.MT_DATA_LOGGER_RESET,
            cd.MT_EXIT,
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
            self.rm_data_set(name)

    def rm_data_set(self, name: str):
        try:
            self.datasets.pop(name)
            self.logger.info(f"Removed data set: '{name}'")
        except KeyError:
            pass

    def send_status(self, name: str = "all"):
        msg = cd.MDF_DATA_SET_STATUS()
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
                raise DataSetNotFound(f"Data set named '{name}' not found.")

            msg.name = ds.name
            msg.elapsed_time = ds.elapsed_time
            msg.is_recording = ds.recording
            msg.is_paused = ds.paused
            self.client.send_message(msg)

    def send_config(self):
        msg = cd.MDF_DATA_LOGGER_CONFIG()

        msg.num_data_sets = len(self.datasets)

        for i, ds in enumerate(self.datasets.values()):
            d = msg.data_sets[i]

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
                start_msg = cd.MDF_DATA_SET_STARTED()
                start_msg.name = ds.name
                self.client.send_message(start_msg)
        else:
            ds = self.datasets.get(name)
            if ds is None:
                raise DataSetNotFound(f"Data set named '{name}' not found.")

            if ds.recording:
                raise DataSetInProgress(
                    f"Recording in progresss for data set '{ds.name}'"
                )

            ds.start()
            start_msg = cd.MDF_DATA_SET_STARTED()
            start_msg.name = ds.name
            self.client.send_message(start_msg)

        self.send_status()

    def stop_logging(self, name: str):
        if name in DataLogger.ALL_SETS:
            for ds in self.datasets.values():
                ds.stop()
                stop_msg = cd.MDF_DATA_SET_STOPPED()
                stop_msg.name = ds.name
                self.client.send_message(stop_msg)
        else:
            ds = self.datasets.get(name)
            if ds is None:
                raise DataSetNotFound(f"Data set named '{name}' not found.")

            ds.stop()

            stop_msg = cd.MDF_DATA_SET_STOPPED()
            stop_msg.name = ds.name
            self.client.send_message(stop_msg)

        self.send_status()

    def pause_logging(self, name: str):
        if name in DataLogger.ALL_SETS:
            for ds in self.datasets.values():
                ds.pause()
        else:
            ds = self.datasets.get(name)
            if ds is None:
                raise DataSetNotFound(f"Data set named '{name}' not found.")

            ds.pause()

        self.send_status()

    def resume_logging(self, name: str):
        if name in DataLogger.ALL_SETS:
            for ds in self.datasets.values():
                ds.resume()
        else:
            ds = self.datasets.get(name)
            if ds is None:
                raise DataSetNotFound(f"Data set named '{name}' not found.")

            ds.resume()

        self.send_status()

    def add_data_set(self, msg: cd.MDF_DATA_SET_ADD):
        data_set = DataSet(
            name=msg.data_set.name,
            save_path=msg.data_set.save_path,
            filename=msg.data_set.filename,
            msg_types=msg.data_set.msg_types[:],
            formatter_cls=get_formatter(msg.data_set.formatter),
            subdivide_interval=msg.data_set.subdivide_interval,
            parent_logger=self.logger,
        )

        if len(self.datasets) == DataLogger.MAX_DATA_SETS:
            raise DataLoggerFullError(
                "Logger has maximum allowed data sets configured."
            )

        if data_set.name in self.datasets.keys():
            raise DataSetExistsError(
                "A data set with name '{data_set.name}' already exists"
            )

        self.datasets[data_set.name] = data_set
        self.logger.info(f"Added data set: {data_set.name}")

    def reset(self):
        self.client.info(f"Reset DataLogger. All Data Sets will be cleared")
        for ds in self.datasets.values():
            ds.stop()
            self.rm_data_set(ds.name)

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
                    match (msg.data):
                        case cd.MDF_DATA_SET_START():
                            self.start_logging(msg.data.name)
                        case cd.MDF_DATA_SET_STOP():
                            self.stop_logging(msg.data.name)
                        case cd.MDF_DATA_SET_PAUSE():
                            self.pause_logging(msg.data.name)
                        case cd.MDF_DATA_SET_RESUME():
                            self.resume_logging(msg.data.name)
                        case cd.MDF_DATA_SET_ADD():
                            self.add_data_set(msg.data)
                        case cd.MDF_DATA_SET_REMOVE():
                            self.rm_data_set(msg.data.name)
                        case cd.MDF_DATA_LOGGER_RESET():
                            self.reset()
                        case cd.MDF_DATA_SET_STATUS_REQUEST():
                            self.send_status(msg.data.name)
                        case cd.MDF_DATA_LOGGER_CONFIG_REQUEST():
                            self.send_config()
                        case cd.MDF_EXIT():
                            if msg.header.dest_mod_id == self.client.module_id:
                                self._running = False
                                self.client.info("Received EXIT request. Closing...")

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
