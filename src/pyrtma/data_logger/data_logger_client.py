"""pyrtma.data_logger.data_logger_client

Subclass of :py:class:`pyrtma.Client` that provides additional functions for managing the pyrtma data_logger
"""

from __future__ import annotations

import pyrtma
import pyrtma.core_defs as cd
from pyrtma.data_logger.exceptions import NoClientError
from pyrtma.exceptions import UnknownMessageType
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, List, Dict, Any, Union, Optional


if TYPE_CHECKING:
    from _typeshed import StrPath

__all__ = ["DatasetConfig", "DataLoggerClient"]


@dataclass
class DatasetConfig:
    """Configuration for a data_logger dataset"""

    name: str
    save_path: StrPath
    filename: str
    formatter: str
    subdivide_interval: int = 0
    msg_types: List[int] = field(default_factory=lambda: [cd.ALL_MESSAGE_TYPES])

    def __post_init__(self):
        self.save_path = Path(self.save_path)
        self._client: Optional[pyrtma.Client] = None

    def register_client(self, client: pyrtma.Client):
        """Register a pyrtma client with this dataset config

        Args:
            client (pyrtma.Client): client to register
        """
        self._client = client

    def add(self, client: Optional[pyrtma.Client] = None):
        """Add dataset config to data_logger

        Args:
            client (Optional[pyrtma.Client], optional): Client to register. If None (default), assumes :py:func:`send_message` has already been called.

        Raises:
            NoClientError: Client must be input or registered first
        """
        if client:
            self.register_client(client)
        if self._client:
            msg = cd.MDF_DATASET_ADD()
            msg.dataset.name = self.name
            msg.dataset.save_path = str(self.save_path)
            msg.dataset.filename = self.filename
            msg.dataset.formatter = self.formatter
            msg.dataset.msg_types[: len(self.msg_types)] = self.msg_types
            msg.dataset.subdivide_interval = self.subdivide_interval
            self._client.send_message(msg)
        else:
            raise NoClientError

    def remove(self, client: Optional[pyrtma.Client] = None):
        """Remove dataset config from data_logger

        Args:
            client (Optional[pyrtma.Client], optional): Client to register. If None (default), assumes :py:func:`send_message` has already been called.

        Raises:
            NoClientError: Client must be input or registered first
        """
        if client:
            self.register_client(client)
        if self._client:
            msg = cd.MDF_DATASET_REMOVE()
            msg.name = self.name
            self._client.send_message(msg)
        else:
            raise NoClientError

    def start(self, client: Optional[pyrtma.Client] = None):
        """Start dataset recording in data_logger

        Args:
            client (Optional[pyrtma.Client], optional): Client to register. If None (default), assumes :py:func:`send_message` has already been called.

        Raises:
            NoClientError: Client must be input or registered first
        """
        if client:
            self.register_client(client)
        if self._client:
            msg = cd.MDF_DATASET_START()
            msg.name = self.name
            self._client.send_message(msg)
        else:
            raise NoClientError

    def stop(self, client: Optional[pyrtma.Client] = None):
        """Stop dataset recording in data_logger

        Args:
            client (Optional[pyrtma.Client], optional): Client to register. If None (default), assumes :py:func:`send_message` has already been called.

        Raises:
            NoClientError: Client must be input or registered first
        """
        if client:
            self.register_client(client)
        if self._client:
            msg = cd.MDF_DATASET_STOP()
            msg.name = self.name
            self._client.send_message(msg)
        else:
            raise NoClientError

    def pause(self, client: Optional[pyrtma.Client] = None):
        """Pause dataset recording in data_logger

        Args:
            client (Optional[pyrtma.Client], optional): Client to register. If None (default), assumes :py:func:`send_message` has already been called.

        Raises:
            NoClientError: Client must be input or registered first
        """
        if client:
            self.register_client(client)
        if self._client:
            msg = cd.MDF_DATASET_PAUSE()
            msg.name = self.name
            self._client.send_message(msg)
        else:
            raise NoClientError

    def resume(self, client: Optional[pyrtma.Client] = None):
        """Resume dataset recording in data_logger

        Args:
            client (Optional[pyrtma.Client], optional): Client to register. If None (default), assumes :py:func:`send_message` has already been called.

        Raises:
            NoClientError: Client must be input or registered first
        """
        if client:
            self.register_client(client)
        if self._client:
            msg = cd.MDF_DATASET_RESUME()
            msg.name = self.name
            self._client.send_message(msg)
        else:
            raise NoClientError


class DataLoggerClient(pyrtma.Client):
    """pyrtma client with additional functions for managing data_logger

    Args:
        module_id (optional): Static module ID, which must be unique.
            Defaults to 0, which generates a dynamic module ID.
        host_id (optional): Host ID. Defaults to 0.
        timecode (optional): Add additional timecode fields to message
            header, used by some projects at RNEL. Defaults to False.
    """

    _data_client_types = (
        cd.MT_DATASET_STATUS,
        cd.MT_DATA_LOGGER_CONFIG,
        cd.MT_DATA_LOGGER_ERROR,
    )

    def __init__(
        self,
        module_id: int = 0,
        host_id: int = 0,
        timecode: bool = False,
        name: str = "",
    ):
        super().__init__(module_id, host_id, timecode, name)

    def connect(self, server_name: str = "localhost:7111", *args, **kwargs):
        """Connect to message manager server

        Args:
            server_name (optional): IP_addr:port_num string associated with message manager.
                Defaults to "localhost:7111".
            logger_status (optional): Flag to declare client as a logger module.
                Logger modules are automatically subscribed to all message types.
                Defaults to False.
            allow_multiple (optional): Flag to declare client can have multiple instances. Defaults to False.

        Raises:
            MessageManagerNotFound: Unable to connect to message manager
        """
        super().connect(server_name, *args, **kwargs)
        self.subscribe(self._data_client_types)

    def add_dataset(self, config: DatasetConfig):
        """Add dataset config to data_logger

        Args:
            config (DatasetConfig): config object to add
        """
        config.add(self)

    def rm_dataset(self, config: Union[DatasetConfig, str]):
        """Remove dataset config from data_logger

        Args:
            config (DatasetConfig | str): Dataset config object or name
        """
        if isinstance(config, str):
            msg = cd.MDF_DATASET_REMOVE()
            msg.name = config
            self.send_message(msg)
        else:
            config.remove(self)

    def start_dataset(self, config: Union[DatasetConfig, str]):
        """Start dataset recording in data_logger

        Args:
            config (DatasetConfig | str): Dataset config object or name
        """
        if isinstance(config, str):
            msg = cd.MDF_DATASET_START()
            msg.name = config
            self.send_message(msg)
        else:
            config.start(self)

    def start_all_datasets(self):
        """Start all dataset recordings in data_logger"""
        self.start_dataset(config="*")

    def stop_dataset(self, config: Union[DatasetConfig, str]):
        """Stop dataset recording in data_logger

        Args:
            config (DatasetConfig | str): Dataset config object or name
        """
        if isinstance(config, str):
            msg = cd.MDF_DATASET_STOP()
            msg.name = config
            self.send_message(msg)
        else:
            config.stop(self)

    def stop_all_datasets(self):
        """Stop all dataset recordings in data_logger"""
        self.stop_dataset(config="*")

    def pause_dataset(self, config: Union[DatasetConfig, str]):
        """Pause dataset recording in data_logger

        Args:
            config (DatasetConfig | str): Dataset config object or name
        """
        if isinstance(config, str):
            msg = cd.MDF_DATASET_PAUSE()
            msg.name = config
            self.send_message(msg)
        else:
            config.pause(self)

    def pause_all_datasets(self):
        """Pause all dataset recordings in data_logger"""
        self.pause_dataset(config="*")

    def resume_dataset(self, config: Union[DatasetConfig, str]):
        """Resume dataset recording in data_logger

        Args:
            config (DatasetConfig | str): Dataset config object or name
        """
        if isinstance(config, str):
            msg = cd.MDF_DATASET_RESUME()
            msg.name = config
            self.send_message(msg)
        else:
            config.resume(self)

    def resume_all_datasets(self):
        """Resume all dataset recordings in data_logger"""
        self.resume_dataset(config="*")

    def request_dataset_status(self, config: Union[DatasetConfig, str]):
        """Request dataset status from data_logger

        Args:
            config (DatasetConfig | str): Dataset config object or name
        """
        msg = cd.MDF_DATASET_STATUS_REQUEST()
        if isinstance(config, str):
            msg.name = config
        else:
            msg.name = config.name
        self.send_message(msg)

    def request_all_dataset_status(self):
        """Request all dataset statuses from data_logger"""
        self.request_dataset_status(config="*")

    def request_data_logger_config(self):
        """Request data_logger config"""
        self.send_signal(cd.MT_DATA_LOGGER_CONFIG_REQUEST)

    def reset_data_logger(self):
        """Reset data_logger (stop and remove all)"""
        self.send_signal(cd.MT_DATA_LOGGER_RESET)

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
