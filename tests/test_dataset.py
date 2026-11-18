"""Tests for ``pyrtma.data_logger.dataset``, without a manager.

The ``Dataset`` is given a stand-in client that records what it would send.
"""

from __future__ import annotations

import ctypes
import inspect
from pathlib import Path
from typing import Any, cast

import pytest

import pyrtma
from pyrtma import core_defs as cd
from pyrtma.data_logger.dataset import Dataset
from pyrtma.header import MessageHeader


class RecordingClient:
    """Stands in for a connected client, keeping what is sent."""

    def __init__(self) -> None:
        self.definitions = cd.get_message_definitions()
        self.sent: list[Any] = []

    def send_message(self, msg: Any, dest_mod_id: int = 0) -> None:
        self.sent.append(msg)


def make(tmp_path: Path, **kwargs: Any) -> tuple[Dataset, RecordingClient]:
    dataset = Dataset("ds", tmp_path, "rec", "json", create_client=False, **kwargs)
    client = RecordingClient()
    dataset.register_client(cast(pyrtma.Client, client))
    return dataset, client


def test_default_manager_address_uses_the_core_host_and_port() -> None:
    default = inspect.signature(Dataset).parameters["mm_ip"].default

    assert default == f"{cd.DEFAULT_HOST}:{cd.DEFAULT_PORT}"


def test_max_size_mb_is_sent_when_added(tmp_path: Path) -> None:
    dataset, client = make(tmp_path, max_size_mb=20)

    dataset.add()

    assert dataset.max_size_mb == 20
    assert client.sent[-1].dataset.max_size_mb == 20


def test_default_max_size_is_1_gb(tmp_path: Path) -> None:
    dataset, client = make(tmp_path)

    dataset.add()

    assert client.sent[-1].dataset.max_size_mb == cd.DATASET_MAX_SIZE_MB == 1000


def test_max_size_mb_zero_is_sent_for_the_largest(tmp_path: Path) -> None:
    dataset, client = make(tmp_path, max_size_mb=0)

    dataset.add()

    assert dataset.max_size_mb == 0
    assert client.sent[-1].dataset.max_size_mb == 0


@pytest.mark.filterwarnings("error::pytest.PytestUnraisableExceptionWarning")
def test_subdivide_interval_is_gone(tmp_path: Path) -> None:
    # The half-built Dataset is cleaned up too, without an error of its own.
    with pytest.raises(TypeError, match="subdivide_interval"):
        Dataset("ds", tmp_path, "rec", "json", subdivide_interval=30)  # type: ignore[call-arg]


def test_fifth_argument_is_msg_types(tmp_path: Path) -> None:
    dataset = Dataset("ds", tmp_path, "rec", "json", [7001], create_client=False)

    assert dataset.msg_types == (7001,)


@pytest.mark.parametrize("size", [-1, cd.DATASET_MAX_SIZE_MB + 1])
def test_max_size_mb_outside_its_range_raises(tmp_path: Path, size: int) -> None:
    with pytest.raises(ValueError, match="max_size_mb"):
        make(tmp_path, max_size_mb=size)


def logger_message(data: Any) -> pyrtma.Message:
    header = MessageHeader()
    header.msg_type = data.type_id
    header.num_data_bytes = ctypes.sizeof(data)
    return pyrtma.Message(header, data)


def error(dataset: str) -> cd.MDF_DATA_LOGGER_ERROR:
    data = cd.MDF_DATA_LOGGER_ERROR()
    data.dataset_name = dataset
    data.exc_type = "DatasetError"
    data.msg = "something went wrong"
    return data


class TestProcessMsg:
    def test_error_for_this_dataset_is_returned(self, tmp_path: Path) -> None:
        dataset, _ = make(tmp_path)

        result = dataset.process_msg(logger_message(error("ds")))

        assert result is not None
        assert result.exc_type == "DatasetError"

    def test_error_for_another_dataset_is_ignored(self, tmp_path: Path) -> None:
        dataset, _ = make(tmp_path)

        assert dataset.process_msg(logger_message(error("other"))) is None

    def test_error_for_no_dataset_is_returned(self, tmp_path: Path) -> None:
        dataset, _ = make(tmp_path)

        result = dataset.process_msg(logger_message(error("")))

        assert result is not None
        assert result.dataset_name == ""

    def test_config_is_stored(self, tmp_path: Path) -> None:
        dataset, _ = make(tmp_path)
        config = cd.MDF_DATA_LOGGER_CONFIG()
        config.num_datasets = 1
        config.datasets[0].name = "ds"

        result = dataset.process_msg(logger_message(config))

        assert result is None
        assert dataset.datalogger_config is not None
        assert dataset.datalogger_config.num_datasets == 1
        assert dataset.datalogger_config.datasets[0].name == "ds"

    def test_config_is_none_until_received(self, tmp_path: Path) -> None:
        dataset, _ = make(tmp_path)

        assert dataset.datalogger_config is None

    def test_status_for_this_dataset_is_kept(self, tmp_path: Path) -> None:
        dataset, _ = make(tmp_path)
        status = cd.MDF_DATASET_STATUS()
        status.name = "ds"
        status.is_recording = 1

        dataset.process_msg(logger_message(status))

        assert dataset.is_recording
