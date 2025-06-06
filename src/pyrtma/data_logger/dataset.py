"""pyrtma.data_logger.dataset"""

from __future__ import annotations

import time
import pyrtma
import pyrtma.core_defs as cd
from pyrtma.data_logger.exceptions import NoClientError
from pyrtma.exceptions import UnknownMessageType
from pathlib import Path
from typing import TYPE_CHECKING, List, Dict, Any, Union, Optional, cast


if TYPE_CHECKING:
    from _typeshed import StrPath

__all__ = ["Dataset"]


class Dataset:
    """Configuration for a data_logger dataset"""

    def __init__(
        self,
        name: str,
        save_path: StrPath,
        filename: str,
        formatter: str,
        subdivide_interval: int = 0,
        msg_types: List[int] | None = None,
        mm_ip: str = "localhost:7111",
        status_interval: float = 5.0,
    ):

        _datalogger_types = (
            cd.MT_DATASET_STATUS,
            cd.MT_DATASET_ADDED,
            cd.MT_DATASET_REMOVED,
            cd.MT_DATASET_STARTED,
            cd.MT_DATASET_STOPPED,
            cd.MT_DATASET_SAVED,
            cd.MT_DATA_LOGGER_CONFIG,
            cd.MT_DATA_LOGGER_ERROR,
        )

        self._client = pyrtma.Client(0, name=name)
        self._client.connect(mm_ip)
        self._client.subscribe(_datalogger_types)

        self._name = name
        self._save_path = Path(save_path)
        self._filename = filename
        self._formatter = formatter
        self._subdivide_interval = subdivide_interval

        self._status = cd.MDF_DATASET_STATUS()

        if msg_types is None:
            self._msg_types = tuple([cd.ALL_MESSAGE_TYPES])
        else:
            self._msg_types = tuple(msg_types)

        self._started = False
        self._added = False
        self._removed = False
        self._stopped = False
        self._saved: list[str] = []

        self.status_interval = status_interval
        self._last_status = time.time()

    @property
    def name(self) -> str:
        return self._name

    @property
    def save_path(self) -> Path:
        return self._save_path

    @property
    def filename(self) -> str:
        return self._filename

    @property
    def formatter(self) -> str:
        return self._formatter

    @property
    def subdivide_interval(self) -> int:
        return self._subdivide_interval

    @property
    def msg_types(self) -> tuple[int, ...]:
        return self._msg_types

    @property
    def added(self) -> bool:
        return self._started

    @property
    def removed(self) -> bool:
        return self._started

    @property
    def started(self) -> bool:
        return self._started

    @property
    def stopped(self) -> bool:
        return self._stopped

    @property
    def saved(self) -> tuple[str, ...]:
        return tuple(self._saved)

    @property
    def elapsed_time(self) -> float:
        return self._status.elapsed_time

    @property
    def is_recording(self) -> bool:
        return bool(self._status.is_recording)

    @property
    def is_paused(self) -> bool:
        return bool(self._status.is_paused)

    def poll(self, timeout: float = 0) -> cd.MDF_DATA_LOGGER_ERROR | None:
        if self._client is None:
            raise NoClientError

        if (now := time.time()) - self._last_request > self.status_interval:
            req = cd.MDF_DATASET_STATUS_REQUEST()
            req.name = self.name
            self._client.send_message(req)
            self._last_request = now

        while msg := self._client.read_message(timeout):
            if msg.type_id in (
                cd.MT_DATASET_STATUS,
                cd.MT_DATASET_ADDED,
                cd.MT_DATASET_STARTED,
                cd.MT_DATASET_STOPPED,
                cd.MT_DATASET_REMOVED,
                cd.MT_DATASET_SAVED,
                cd.MT_DATA_LOGGER_ERROR,
            ):
                if msg.name != self._name:
                    return

            match (msg.type_id):
                case cd.MT_DATASET_STATUS:
                    self._status = cast(cd.MDF_DATASET_STATUS, msg.data)
                    self._last_status = time.time()
                case cd.MT_DATASET_STARTED:
                    self._started = True
                case cd.MT_DATASET_STOPPED:
                    self._stopped = True
                case cd.MT_DATASET_ADDED:
                    self._added = True
                case cd.MT_DATASET_REMOVED:
                    self._removed = True
                case cd.MT_DATASET_SAVED:
                    self._saved.append(cast(cd.MDF_DATASET_SAVED, msg.data).filepath)
                case cd.MT_DATA_LOGGER_ERROR:
                    return cast(cd.MDF_DATA_LOGGER_ERROR, msg.data)
                case cd.MT_DATA_LOGGER_CONFIG:
                    self.datalogger_config = self.process_data_logger_config_msg(
                        cast(cd.MDF_DATA_LOGGER_CONFIG, msg.data)
                    )

    def add(self) -> cd.MDF_DATASET_ADD:
        msg = cd.MDF_DATASET_ADD()
        msg.dataset.name = self.name
        msg.dataset.save_path = str(self.save_path)
        msg.dataset.filename = self.filename
        msg.dataset.formatter = self.formatter
        msg.dataset.msg_types[: len(self.msg_types)] = self.msg_types
        msg.dataset.subdivide_interval = self.subdivide_interval

        if self._client:
            self._client.send_message(msg)
        else:
            raise NoClientError

        return msg

    def remove(self) -> cd.MDF_DATASET_REMOVE:
        """Remove dataset config from data_logger"""
        msg = cd.MDF_DATASET_REMOVE()
        msg.name = self.name

        if self._client:
            self._client.send_message(msg)
        else:
            raise NoClientError

        return msg

    def start(self) -> cd.MDF_DATASET_START:
        """Start dataset recording in data_logger"""
        msg = cd.MDF_DATASET_START()
        msg.name = self.name
        if self._client:
            self._client.send_message(msg)
        else:
            raise NoClientError

        return msg

    def stop(self) -> cd.MDF_DATASET_STOP:
        """Stop dataset recording in data_logger"""
        msg = cd.MDF_DATASET_STOP()
        msg.name = self.name

        if self._client:
            self._client.send_message(msg)
        else:
            raise NoClientError

        return msg

    def pause(self) -> cd.MDF_DATASET_PAUSE:
        """Pause dataset recording in data_logger"""
        msg = cd.MDF_DATASET_PAUSE()
        msg.name = self.name

        if self._client:
            self._client.send_message(msg)
        else:
            raise NoClientError

        return msg

    def resume(self) -> cd.MDF_DATASET_RESUME:
        """Resume dataset recording in data_logger"""
        msg = cd.MDF_DATASET_RESUME()
        msg.name = self.name

        if self._client:
            self._client.send_message(msg)
        else:
            raise NoClientError

        return msg

    def status_request(self) -> cd.MDF_DATASET_STATUS_REQUEST:
        """Request dataset status in data_logger"""
        msg = cd.MDF_DATASET_STATUS_REQUEST()
        msg.name = self.name

        if self._client:
            self._client.send_message(msg)
        else:
            raise NoClientError

        return msg

    def request_data_logger_config(self):
        """Request data_logger config"""
        if self._client:
            self._client.send_signal(cd.MT_DATA_LOGGER_CONFIG_REQUEST)
        else:
            raise NoClientError

    def reset_data_logger(self):
        """Reset data_logger (stop and remove all)"""
        if self._client:
            self._client.send_signal(cd.MT_DATA_LOGGER_RESET)
        else:
            raise NoClientError

    def process_data_logger_config_msg(
        self, msg_data: cd.MDF_DATA_LOGGER_CONFIG
    ) -> Dict[str, Any]:
        """Process a data_logger config message

        Args:
            msg_data (cd.MDF_DATA_LOGGER_CONFIG): unprocessed message data

        Returns:
            Dict[str, Any]: data_logger config dict
        """
        d = msg_data.to_dict()
        for ds in d["datasets"]:
            names = []
            for msg_type in ds["msg_types"]:
                if msg_type < 1:
                    continue
                if msg_type == cd.ALL_MESSAGE_TYPES:
                    names.append("ALL_MESSAGE_TYPES")
                else:
                    try:
                        names.append(pyrtma.get_msg_cls(msg_type).type_name)
                    except UnknownMessageType:
                        names.append(msg_type)
            ds["msg_types"] = names
        d["datasets"] = d["datasets"][: d["num_datasets"]]
        return d
