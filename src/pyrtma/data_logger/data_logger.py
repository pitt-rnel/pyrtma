import time

import pyrtma
import pyrtma.core_defs as cd

from pyrtma.exceptions import UnknownMessageType
from typing import Optional, cast

from .metadata import LoggingMetadata
from .data_collection import DataCollection
from .data_set import DataSet
from .data_formatter import get_formatter
from .exceptions import *


class DataLogger:
    def __init__(self, rtma_server_ip: str, log_level: int):
        self.mod = pyrtma.Client(module_id=cd.MID_DATA_LOGGER, name="data_logger")
        self.mod.logger.level = log_level
        self.mod.connect(rtma_server_ip, logger_status=True)
        self.ctrl_msg_types = [
            cd.MT_DATA_LOGGER_START,
            cd.MT_DATA_LOGGER_STOP,
            cd.MT_DATA_LOGGER_PAUSE,
            cd.MT_DATA_LOGGER_RESUME,
            cd.MT_DATA_LOGGER_RESET,
            cd.MT_ADD_DATA_COLLECTION,
            cd.MT_ADD_DATA_SET,
            cd.MT_REMOVE_DATA_COLLECTION,
            cd.MT_REMOVE_DATA_SET,
            cd.MT_DATA_COLLECTION_CONFIG_REQUEST,
            cd.MT_DATA_LOGGER_STATUS_REQUEST,
            cd.MT_DATA_LOGGER_METADATA_UPDATE,
            cd.MT_DATA_LOGGER_METADATA_REQUEST,
            cd.MT_EXIT,
        ]

        self.mod.subscribe(self.ctrl_msg_types)

        self.mod.send_module_ready()

        self.mod.info("DataLogger connected and waiting for configuration.")

        self.metadata = LoggingMetadata()
        self.collection: Optional[DataCollection] = None

        self._running = False
        self._recording = False
        self._paused = False
        self._elapsed_time = 0.0

    def send_status(self):
        msg = cd.MDF_DATA_LOGGER_STATUS()
        msg.timestamp = time.time()
        if self._recording and self.collection:
            msg.elapsed_time = self.collection.elapsed_time
        else:
            msg.elapsed_time = -1
        msg.is_recording = self._recording
        msg.is_paused = self._paused

        self.mod.send_message(msg)

    def collection_info(self) -> cd.DATA_COLLECTION_INFO:
        if self.collection:
            c = cd.DATA_COLLECTION_INFO()

            c.name = self.collection.name
            c.save_path = str(self.collection.save_path)
            c.num_data_sets = len(self.collection.datasets)

            for i, ds in enumerate(self.collection.datasets):
                c.data_sets[i].name = ds.name
                c.data_sets[i].formatter = ds.formatter_cls.name
                c.data_sets[i].save_path = str(ds.file_path)
                c.data_sets[i].subdivide_interval = (
                    0
                    if isinstance(ds.subdivide_interval, float)
                    else ds.subdivide_interval
                )
                c.data_sets[i].msg_types[: len(ds.msg_types)] = ds.msg_types

        return c

    def send_config(self):
        msg = cd.MDF_DATA_COLLECTION_CONFIG()

        if self.collection is None:
            self.mod.send_message(msg)
            return

        msg.collection.name = self.collection.name
        msg.collection.base_path = str(self.collection.base_path)
        msg.collection.dir_fmt = self.collection.dir_fmt
        msg.collection.num_data_sets = len(self.collection.datasets)

        for i, ds in enumerate(self.collection.datasets):
            d = msg.collection.data_sets[i]

            d.name = ds.name
            d.sub_dir_fmt = ds.sub_dir_fmt
            d.file_name_fmt = ds.file_name_fmt
            d.formatter = ds.formatter_cls.name
            d.msg_types[: len(ds.msg_types)] = ds.msg_types
            d.subdivide_interval = (
                0 if isinstance(ds.subdivide_interval, float) else ds.subdivide_interval
            )

        self.mod.send_message(msg)

    def start_logging(self):
        if self.collection:
            if self._recording:
                raise DataCollectionInProgress(
                    "Cannot start collection while recording in progresss."
                )

            self.mod.subscribe([cd.ALL_MESSAGE_TYPES])
            self.collection.start()

            msg = cd.MDF_DATA_COLLECTION_STARTED()
            msg.collection = self.collection_info()
            self.mod.send_message(msg)

            self.mod.info("Data logging started.")
            self._recording = True
            self._paused = False
        else:
            raise DataCollectionNotConfigured("Ignoring start logging request.")

        self.send_status()

    def stop_logging(self):
        if self.collection:
            if self._recording:
                self.mod.unsubscribe([cd.ALL_MESSAGE_TYPES])
                self.collection.stop()
                self.mod.subscribe(self.ctrl_msg_types)

                msg = cd.MDF_DATA_COLLECTION_STOPPED()
                msg.collection = self.collection_info()
                self.mod.send_message(msg)
                self.mod.send_signal(cd.MT_DATA_COLLECTION_SAVED)

                self.mod.info("Data logging stopped.")
            else:
                self.mod.warn("Logger not recording. Stop ignored.")
        else:
            raise DataCollectionNotConfigured("Ignoring stop logging request.")

        self._recording = False
        self._paused = False
        self.send_status()

    def pause_logging(self):
        if self.collection:
            self.collection.pause()
            self.mod.info("Data logging paused.")
            self._paused = True
        else:
            raise DataCollectionNotConfigured("Ignoring pause logging request.")

    def resume_logging(self):
        if self.collection:
            self.collection.resume()
            self.mod.info("Data logging resumed.")
            self._paused = False
        else:
            raise DataCollectionNotConfigured("Ignoring resume logging request.")

    def add_data_collection(self, msg: cd.MDF_ADD_DATA_COLLECTION):
        if self._recording:
            raise DataCollectionInProgress(
                "Cannot add data collection while recording in progresss."
            )

        if self.collection:
            self.mod.info(f"Closing previous collection: {self.collection.name}")
            self.collection.close()
            self.rm_data_collection()

        self.collection = DataCollection(
            msg.collection.name,
            msg.collection.base_path,
            msg.collection.dir_fmt,
            self.metadata,
        )
        self.mod.info(f"Created data collection: {msg.collection.name}")

        for i in range(msg.collection.num_data_sets):
            ds = msg.collection.data_sets[i]

            try:
                self.collection.add_data_set(
                    DataSet(
                        collection_name=self.collection.name,
                        name=ds.name,
                        sub_dir_fmt=ds.sub_dir_fmt,
                        file_name_fmt=ds.file_name_fmt,
                        msg_types=ds.msg_types[:],
                        formatter_cls=get_formatter(ds.formatter),
                        subdivide_interval=ds.subdivide_interval,
                        metadata=self.collection.metadata,
                    )
                )
            except (DataFormatterKeyError, InvalidFormatter, DataSetExistsError) as e:
                self.mod.error(e.args[0])
                self.send_error(f"{e.__class__.__name__}:{e.args[0]}")
                continue

    def add_data_set(self, msg: cd.MDF_ADD_DATA_SET):
        if self._recording:
            raise DataCollectionInProgress(
                "Cannot add data set while recording in progresss."
            )

        if self.collection is None:
            raise DataCollectionNotConfigured(
                "Cannot add data set without setting up a collection first."
            )

        if msg.collection_name != self.collection.name:
            DataCollectionNotFound(
                f"add_data_set: trying to add to an unknown collection: {msg.collection_name}"
            )

        ds = DataSet(
            collection_name=self.collection.name,
            name=msg.data_set.name,
            sub_dir_fmt=msg.data_set.sub_dir_fmt,
            file_name_fmt=msg.data_set.file_name_fmt,
            msg_types=msg.data_set.msg_types[:],
            formatter_cls=get_formatter(msg.data_set.formatter),
            subdivide_interval=msg.data_set.subdivide_interval,
            metadata=self.collection.metadata,
        )

        self.collection.add_data_set(ds)

    def rm_data_collection(self):
        if self._recording:
            raise DataCollectionInProgress(
                "Cannot remove collection while recording in progress."
            )

        if self.collection:
            self.mod.info(f"Removed data collection: {self.collection.name}")
            self.collection.close()
            self.collection = None

    def rm_data_set(self, msg: cd.MDF_REMOVE_DATA_SET):
        if self._recording:
            raise DataCollectionInProgress(
                "Cannot remove data set while recording in progress."
            )

        if self.collection:
            self.collection.rm_data_set(msg.name)

    def reset(self):
        if (c := self.collection) is not None:
            if self._recording:
                self.mod.warn("Reset while recording in progress. Stopping collection!")
                self.stop_logging()

            self.rm_data_collection()

        self.metadata.clear()
        self._recording = False
        self._paused = False
        self.mod.info(f"Reset DataLogger. All collection/sets are cleared")

    def update_metadata(self, json_str: str):
        if self._recording:
            raise DataCollectionInProgress(
                "Cannot update metadata while recording in progress."
            )

        self.metadata.update(json_str)

    def send_error(self, msg: str):
        err = cd.MDF_DATA_LOGGER_ERROR()
        err.msg = msg
        self.mod.send_message(err)

    def run(self):
        try:
            self._running = True
            while self._running:
                try:
                    msg = self.mod.read_message(0.100)
                except UnknownMessageType as e:
                    self.mod.warn(f"UnknownMessageType: {e.args[0]}")
                    continue

                if self.collection and self._recording:
                    self.collection.update(msg)

                if msg is None:
                    continue

                try:
                    match (msg.data):
                        case cd.MT_DATA_LOGGER_START:
                            self.start_logging()
                        case cd.MT_DATA_LOGGER_STOP:
                            self.stop_logging()
                        case cd.MT_DATA_LOGGER_PAUSE:
                            self.pause_logging()
                        case cd.MT_DATA_LOGGER_RESUME:
                            self.resume_logging()
                        case cd.MT_ADD_DATA_COLLECTION:
                            self.add_data_collection(
                                cast(cd.MDF_ADD_DATA_COLLECTION, msg.data)
                            )
                        case cd.MT_ADD_DATA_SET:
                            self.add_data_set(cast(cd.MDF_ADD_DATA_SET, msg.data))
                        case cd.MT_REMOVE_DATA_COLLECTION:
                            self.rm_data_collection()
                        case cd.MT_REMOVE_DATA_SET:
                            self.rm_data_set(cast(cd.MDF_REMOVE_DATA_SET, msg.data))
                        case cd.MT_DATA_LOGGER_RESET:
                            self.reset()
                        case cd.MT_DATA_LOGGER_STATUS_REQUEST:
                            self.send_status()
                        case cd.MT_DATA_COLLECTION_CONFIG_REQUEST:
                            self.send_config()
                        case cd.MT_DATA_LOGGER_METADATA_UPDATE:
                            self.update_metadata(
                                cast(cd.MDF_DATA_LOGGER_METADATA_UPDATE, msg.data).json
                            )
                        case cd.MT_DATA_LOGGER_METADATA_REQUEST:
                            meta = cd.MDF_DATA_LOGGER_METADATA()
                            meta.json = self.metadata.to_json()
                            self.mod.send_message(meta)
                        case cd.MT_EXIT:
                            if msg.header.dest_mod_id == self.mod.module_id:
                                self._running = False
                                self.mod.info("Received EXIT request. Closing...")
                except DataLoggerError as e:
                    self.mod.error(e.args[0])
                    self.send_error(f"{e.__class__.__name__}:{e.args[0]}")
                    if self._recording:
                        self.stop_logging()

        except KeyboardInterrupt:
            pass
        finally:
            if self.collection and self._recording:
                self.stop_logging()

            self._running = False

            if self.collection:
                self.collection.close()

            if self.mod.connected:
                self.mod.disconnect()
            self.mod.info("DataLogger is exiting...")
