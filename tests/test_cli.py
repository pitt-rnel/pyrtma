"""Tests for ``pyrtma.data_logger.cli``, with its prompts scripted.

``answer()`` replaces ``rich.prompt.Prompt.ask`` with one that returns the
given answers in turn. Like rich, it returns the prompt's default for an empty
answer when there is one.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

import pyrtma
from pyrtma import core_defs as cd
from pyrtma.data_logger import cli

from .helpers import ManagerHarness
from .test_dataset import RecordingClient


def answer(monkeypatch: pytest.MonkeyPatch, *answers: str) -> list[str]:
    """Script the prompts.

    Returns:
        The prompts asked, in order, without their markup.
    """
    queue = list(answers)
    asked: list[str] = []

    def ask(prompt: str = "", *args: Any, **kwargs: Any) -> Any:
        asked.append(prompt.rsplit("]", 1)[-1])
        if not queue:
            raise AssertionError(f"no answer left for {asked[-1]!r}")
        value = queue.pop(0)
        if value == "" and "default" in kwargs:
            return kwargs["default"]
        return value

    monkeypatch.setattr(cli.Prompt, "ask", staticmethod(ask))
    return asked


def add(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    msg_type: list[str],
    size: list[str],
) -> tuple[RecordingClient, list[str]]:
    """Run ``add_dataset`` with valid answers apart from those given."""
    asked = answer(monkeypatch, "ds", str(tmp_path), "rec", "json", *msg_type, *size)
    client = RecordingClient()
    cli.add_dataset(cast(pyrtma.Client, client))
    return client, asked


class TestAddDataset:
    def test_uses_the_cli_client(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        client, _ = add(monkeypatch, tmp_path, msg_type=["all"], size=[""])

        request = client.sent[-1]
        assert request.type_id == cd.MT_DATASET_ADD
        assert request.dataset.name == "ds"
        assert request.dataset.save_path == str(tmp_path)
        assert list(request.dataset.msg_types[:1]) == [cd.ALL_MESSAGE_TYPES]

    @pytest.mark.parametrize("bad", ["   ", "0", "abc", "1 -2", "1 x 3"])
    def test_bad_message_types_are_asked_again(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bad: str
    ) -> None:
        client, asked = add(
            monkeypatch, tmp_path, msg_type=[bad, "1001, 1002"], size=[""]
        )

        assert asked.count("msg_type") == 2
        assert list(client.sent[-1].dataset.msg_types[:3]) == [1001, 1002, 0]

    def test_too_many_message_types_are_asked_again(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        too_many = " ".join(str(1000 + i) for i in range(65))
        _, asked = add(monkeypatch, tmp_path, msg_type=[too_many, "1001"], size=[""])

        assert asked.count("msg_type") == 2

    @pytest.mark.parametrize("bad", ["n" * 32, "é"])
    def test_bad_name_is_asked_again(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, bad: str
    ) -> None:
        asked = answer(monkeypatch, bad, "ds", str(tmp_path), "rec", "json", "all", "")
        client = RecordingClient()

        cli.add_dataset(cast(pyrtma.Client, client))

        assert asked.count("name") == 2
        assert client.sent[-1].dataset.name == "ds"

    @pytest.mark.parametrize(
        ("answers", "expected"),
        [([""], 500), (["20"], 20), (["0", "20"], 20), (["501", "x", "20"], 20)],
        ids=["default", "given", "zero", "too_large_then_text"],
    )
    def test_max_size_mb_is_asked_until_in_range(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        answers: list[str],
        expected: int,
    ) -> None:
        client, asked = add(monkeypatch, tmp_path, msg_type=["all"], size=answers)

        assert asked.count("max_size_mb") == len(answers)
        assert client.sent[-1].dataset.max_size_mb == expected


@pytest.mark.integration
class TestMain:
    def test_add_uses_the_given_server(
        self,
        manager: ManagerHarness,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        used: list[pyrtma.Client] = []

        def fake_add(client: pyrtma.Client | None = None) -> None:
            assert client is not None
            used.append(client)

        monkeypatch.setattr(cli, "add_dataset", fake_add)
        monkeypatch.setattr(sys, "argv", ["data_logger_cli", manager.address])
        answer(monkeypatch, "add", "q")

        cli.main()

        assert len(used) == 1
        assert used[0].connected
        assert manager.address.endswith(f":{used[0].server[1]}")

    @pytest.mark.parametrize("command", ["remove " + "n" * 40, "start é"])
    def test_bad_argument_is_reported_not_raised(
        self,
        manager: ManagerHarness,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        command: str,
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["data_logger_cli", manager.address])
        answer(monkeypatch, command, "q")

        cli.main()

        out = capsys.readouterr().out
        assert "Goodbye" in out
        assert "name" in out.lower()

    def test_exits_cleanly_without_manager(
        self,
        free_port: int,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        monkeypatch.setattr(sys, "argv", ["data_logger_cli", f"127.0.0.1:{free_port}"])

        with pytest.raises(SystemExit) as exited:
            cli.main()

        assert exited.value.code == 1
        assert "MessageManagerNotFound" in capsys.readouterr().err
