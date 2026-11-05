"""Tests for ``pyrtma.client``: the ``Client`` and ``client_context`` signatures."""

from __future__ import annotations

from typing import Any

import pytest

from pyrtma.client import Client, client_context


@pytest.mark.parametrize(
    ("factory", "args"),
    [
        (Client, (0, 0, "name")),
        (client_context, (0, "127.0.0.1:7111", None, 0, False)),
    ],
    ids=["Client", "client_context"],
)
def test_options_after_host_id_are_keyword_only(
    factory: Any, args: tuple[Any, ...]
) -> None:
    with pytest.raises(TypeError):
        factory(*args)


@pytest.mark.parametrize("factory", [Client, client_context])
def test_timecode_argument_is_rejected(factory: Any) -> None:
    with pytest.raises(TypeError, match="timecode"):
        factory(timecode=True)
