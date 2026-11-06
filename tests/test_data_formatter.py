"""Tests for ``pyrtma.data_logger.data_formatter``."""

from __future__ import annotations

from typing import ClassVar

import pytest

from pyrtma.data_logger import data_formatter
from pyrtma.data_logger.data_formatter import DataFormatter, add_formatter
from pyrtma.data_logger.exceptions import DataFormatterKeyError


def test_duplicate_formatter_name_error_has_its_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Twice(DataFormatter):
        name: ClassVar[str] = "twice"

    monkeypatch.setattr(data_formatter, "_formatter_map", {})
    add_formatter(Twice)

    with pytest.raises(DataFormatterKeyError) as caught:
        add_formatter(Twice)

    assert caught.value.dataset == ""
    assert "twice" in caught.value.msg
