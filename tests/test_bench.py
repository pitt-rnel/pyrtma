"""Tests for the benchmark scripts in ``utils/``.

The scripts aren't part of the package, so they're run as a user would run
them, from another directory, and their reporting functions are loaded from
the file.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

UTILS = Path(__file__).resolve().parent.parent / "utils"
BENCH = UTILS / "pyrtma_bench.py"
MICROBENCH = UTILS / "pyrtma_microbench.py"

# Seconds a script may take; less than pytest-timeout's 60 per test.
SCRIPT_TIMEOUT = 50


def run_script(
    script: Path, args: list[str], cwd: Path
) -> subprocess.CompletedProcess[str]:
    """Run a script with this interpreter, in another directory.

    Args:
        script: The script.
        args: Its arguments.
        cwd: The directory to run it in.

    Returns:
        The finished process, with its output as text.
    """
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=SCRIPT_TIMEOUT,
    )


@pytest.fixture
def bench(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """The benchmark script, loaded as a module.

    It's registered in ``sys.modules`` while the test runs, since dataclasses
    look their module up there.

    Returns:
        The module.
    """
    spec = importlib.util.spec_from_file_location("pyrtma_bench", BENCH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "pyrtma_bench", module)
    spec.loader.exec_module(module)
    return module


@pytest.mark.integration
def test_bench_runs_from_another_directory(tmp_path: Path) -> None:
    result = run_script(
        BENCH, ["--start-manager", "-n", "200", "-ns", "2", "-r", "2"], tmp_path
    )

    assert result.returncode == 0, result.stderr
    rows = [line for line in result.stdout.splitlines() if line.endswith("100.0%")]
    assert len(rows) == 2
    assert "Subscriber rate: median" in result.stdout


@pytest.mark.integration
def test_bench_fails_cleanly_without_a_manager(tmp_path: Path, free_port: int) -> None:
    result = run_script(BENCH, ["-s", f"127.0.0.1:{free_port}"], tmp_path)

    assert result.returncode == 1
    assert "Benchmark failed" in result.stderr
    assert "Traceback" not in result.stderr


def test_subscribers_expect_what_publishers_send(bench: ModuleType) -> None:
    settings = bench.Settings(
        num_msgs=1000, msg_size=128, num_publishers=3, num_subscribers=1, server=""
    )

    assert settings.per_publisher == 333
    assert settings.total == 999


def test_summary_counts_missed_messages(bench: ModuleType) -> None:
    results = [
        bench.RoleResult("publisher", 1, 100, 100, 0.01),
        bench.RoleResult("subscriber", 1, 100, 100, 0.02),
        bench.RoleResult("subscriber", 2, 50, 100, 0.01),
    ]

    summary = bench.summarize_run(results)

    assert summary.publisher_rate == pytest.approx(10_000)
    assert summary.subscriber_rate == pytest.approx(5_000)
    assert summary.slowest_subscriber_rate == pytest.approx(5_000)
    assert summary.received == pytest.approx(0.75)


def test_summary_without_subscribers(bench: ModuleType) -> None:
    results = [
        bench.RoleResult("publisher", 1, 100, 100, 0.01),
        bench.RoleResult("publisher", 2, 100, 100, 0.02),
    ]

    summary = bench.summarize_run(results)

    assert summary.publisher_rate == pytest.approx(7_500)
    assert summary.subscriber_rate is None
    assert summary.received is None


def test_report_gives_median_and_range(bench: ModuleType) -> None:
    settings = bench.Settings(
        num_msgs=100, msg_size=128, num_publishers=1, num_subscribers=1, server=""
    )
    summaries = [
        bench.RunSummary(30_000, 20_000, 19_000, 1.0),
        bench.RunSummary(10_000, 22_000, 21_000, 1.0),
        bench.RunSummary(20_000, 21_000, 20_000, 0.5),
    ]

    text = bench.report(settings, summaries)

    assert "1 publisher, 1 subscriber, 100 messages of 128 bytes" in text
    assert "Publisher rate:  median 20,000 msg/s, range 10,000 to 30,000" in text
    assert "Subscriber rate: median 21,000 msg/s, range 20,000 to 22,000" in text
    assert text.count("100.0%") == 2 and "50.0%" in text


@pytest.mark.integration
def test_microbench_times_every_operation(tmp_path: Path) -> None:
    result = run_script(MICROBENCH, ["-n", "200", "-r", "2"], tmp_path)

    assert result.returncode == 0, result.stderr
    for name in (
        "header field read",
        "header field write, validated",
        "header fill, as sent",
        "message int32 field write",
        "array element write",
        "send_message, 128 B",
        "read_message, 128 B",
    ):
        assert name in result.stdout
