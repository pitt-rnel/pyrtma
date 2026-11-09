"""End-to-end throughput benchmark: publishers to subscribers through a manager.

Each publisher and subscriber runs in its own process, so the numbers include
the manager and the operating system as a lab sees them. Publishers send
``TEST_MSG_<size>`` messages as fast as they can; subscribers read them. A
publisher's rate is the messages it sent over the time its send loop took. A
subscriber's rate is the messages it received over the time from its first
message to its last, as in earlier versions of this script, so results can
be compared with older runs.

The messages come from the compiled test definitions in
``tests/test_msg_defs/test_defs.py``, found relative to this file, so the
benchmark runs from any directory. Run it against a manager that is already
running, or let it start its own with ``--start-manager``::

    python utils/pyrtma_bench.py --start-manager -np 1 -ns 4 -ms 128 -n 10000 -r 5
    python utils/pyrtma_bench.py -s 127.0.0.1:7111 -ns 1

With ``-r`` the benchmark is repeated, and the median and range of the rates
are reported, since single runs vary by several percent.
"""

from __future__ import annotations

import argparse
import ctypes
import multiprocessing
import platform
import queue
import socket
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Sequence

import pyrtma
from pyrtma.definitions import MessageDefinitions
from pyrtma.exceptions import MessageManagerNotFound

DEFS_PATH = (
    Path(__file__).resolve().parent.parent / "tests" / "test_msg_defs" / "test_defs.py"
)
MSG_SIZES = (128, 256, 512, 1024, 2048, 4096, 8192)
HEADER_SIZE = ctypes.sizeof(pyrtma.MessageHeader)

# A run that hasn't finished after this many seconds is stopped with EXIT.
ABORT_TIMEOUT = 120.0
# A subscriber that has received messages stops after this long without one.
IDLE_LIMIT = 1.0
# How long a started manager has to accept connections.
MANAGER_START_TIMEOUT = 10.0


@dataclass(frozen=True)
class Settings:
    """One benchmark configuration.

    Attributes:
        num_msgs: Messages per run, shared by the publishers; each
            subscriber should receive all of them.
        msg_size: Payload size in bytes, one of ``MSG_SIZES``.
        num_publishers: Publisher processes.
        num_subscribers: Subscriber processes.
        server: The manager's address, as ``host:port``.
    """

    num_msgs: int
    msg_size: int
    num_publishers: int
    num_subscribers: int
    server: str

    @property
    def per_publisher(self) -> int:
        """Messages each publisher sends."""
        return self.num_msgs // self.num_publishers

    @property
    def total(self) -> int:
        """Messages each subscriber should receive: what the publishers send.

        Less than ``num_msgs`` when it isn't a multiple of the publishers.
        """
        return self.per_publisher * self.num_publishers


@dataclass(frozen=True)
class RoleResult:
    """What one publisher or subscriber reports at the end of a run.

    Attributes:
        role: ``"publisher"`` or ``"subscriber"``.
        index: The process's number within its role, from 1.
        count: Messages sent or received.
        expected: Messages it should have sent or received.
        seconds: The time its count is measured over.
    """

    role: str
    index: int
    count: int
    expected: int
    seconds: float

    @property
    def rate(self) -> float:
        """Messages per second, or 0 when nothing was timed."""
        return self.count / self.seconds if self.seconds > 0 else 0.0


@dataclass(frozen=True)
class RunSummary:
    """The rates of one run.

    Attributes:
        publisher_rate: Mean publisher rate in messages per second.
        subscriber_rate: Mean subscriber rate, or None without subscribers.
        slowest_subscriber_rate: The lowest subscriber rate, or None.
        received: The fraction of the expected messages that subscribers
            received, from 0 to 1, or None without subscribers.
    """

    publisher_rate: float
    subscriber_rate: Optional[float]
    slowest_subscriber_rate: Optional[float]
    received: Optional[float]


def summarize_run(results: Sequence[RoleResult]) -> RunSummary:
    """Combine one run's results.

    Args:
        results: Every publisher's and subscriber's result for the run.

    Returns:
        The run's summary.
    """
    publishers = [r for r in results if r.role == "publisher"]
    subscribers = [r for r in results if r.role == "subscriber"]
    publisher_rate = statistics.mean(r.rate for r in publishers) if publishers else 0.0
    if not subscribers:
        return RunSummary(publisher_rate, None, None, None)
    expected = sum(r.expected for r in subscribers)
    return RunSummary(
        publisher_rate=publisher_rate,
        subscriber_rate=statistics.mean(r.rate for r in subscribers),
        slowest_subscriber_rate=min(r.rate for r in subscribers),
        received=sum(r.count for r in subscribers) / expected if expected else 1.0,
    )


def median_and_range(values: Sequence[float]) -> tuple[float, float, float]:
    """Return the median, lowest and highest of some values.

    Args:
        values: At least one value.

    Returns:
        ``(median, lowest, highest)``.
    """
    return statistics.median(values), min(values), max(values)


def load_definitions() -> MessageDefinitions:
    """Load the compiled test definitions the benchmark's messages come from.

    Returns:
        The definitions.
    """
    return pyrtma.load_message_definitions(DEFS_PATH)


def _client(defs: MessageDefinitions, server: str) -> pyrtma.Client:
    """Connect a client that uses the test definitions.

    Args:
        defs: The test definitions.
        server: The manager's address.

    Returns:
        The connected client, which has sent ``MODULE_READY``.
    """
    client = pyrtma.Client(definitions=defs)
    client.connect(server_name=server)
    client.send_module_ready()
    return client


def publisher_loop(index: int, settings: Settings, results: Any) -> None:
    """Send this publisher's share of the messages, once every subscriber is ready.

    Runs in its own process. The result, or the error that stopped it, goes
    on ``results`` as a tuple, since dataclasses defined in ``__main__``
    don't unpickle in the parent.

    Args:
        index: This publisher's number, from 1.
        settings: The run's configuration.
        results: A ``multiprocessing`` queue for the result.
    """
    try:
        defs = load_definitions()
        mt = defs.MT
        client = _client(defs, settings.server)
        client.subscribe([mt["SUBSCRIBER_READY"]])
        client.send_signal(mt["PUBLISHER_READY"])

        ready = 0
        while ready < settings.num_subscribers:
            msg = client.read_message(timeout=-1)
            if msg is not None and msg.type_id == mt["SUBSCRIBER_READY"]:
                ready += 1

        count = settings.per_publisher
        msg_data = defs.MDF[f"TEST_MSG_{settings.msg_size}"].from_random()
        tic = time.perf_counter()
        for _ in range(count):
            client.send_message(msg_data)
        toc = time.perf_counter()

        client.disconnect()
        results.put(("publisher", index, count, count, toc - tic))
    except BaseException as e:
        results.put(("error", index, f"publisher {index}: {e!r}"))


def subscriber_loop(index: int, settings: Settings, results: Any) -> None:
    """Receive messages until all have arrived, they stop coming, or EXIT.

    Runs in its own process, and reports as :func:`publisher_loop` does.

    Args:
        index: This subscriber's number, from 1.
        settings: The run's configuration.
        results: A ``multiprocessing`` queue for the result.
    """
    try:
        defs = load_definitions()
        mt = defs.MT
        test_type = mt[f"TEST_MSG_{settings.msg_size}"]
        client = _client(defs, settings.server)
        client.subscribe([test_type, mt["EXIT"]])
        client.send_signal(mt["SUBSCRIBER_READY"])

        count = 0
        tic = toc = 0.0
        while count < settings.total:
            msg = client.read_message(timeout=0.1)
            now = time.perf_counter()
            if msg is not None:
                if msg.type_id == test_type:
                    if count == 0:
                        tic = now
                    toc = now
                    count += 1
                elif msg.type_id == mt["EXIT"]:
                    break
            if count and now - toc > IDLE_LIMIT:
                break

        client.disconnect()
        results.put(("subscriber", index, count, settings.total, toc - tic))
    except BaseException as e:
        results.put(("error", index, f"subscriber {index}: {e!r}"))


class BenchmarkError(Exception):
    """A run couldn't be completed."""


def run_once(settings: Settings) -> list[RoleResult]:
    """Run the benchmark once.

    Publishers start first; subscribers start once every publisher is
    connected and listening for them. A run that takes longer than
    ``ABORT_TIMEOUT`` is stopped with ``EXIT``, and what was received by
    then is reported.

    Args:
        settings: The configuration.

    Raises:
        BenchmarkError: A publisher or subscriber failed, or didn't report.

    Returns:
        Every publisher's and subscriber's result.
    """
    # Spawned processes, as on Windows, so every platform measures the same
    # thing and nothing is inherited from this process's client.
    ctx = multiprocessing.get_context("spawn")
    results: Any = ctx.Queue()
    defs = load_definitions()
    mt = defs.MT
    control = _client(defs, settings.server)
    processes: list[Any] = []
    try:
        control.subscribe([mt["PUBLISHER_READY"]])
        for n in range(1, settings.num_publishers + 1):
            processes.append(
                ctx.Process(target=publisher_loop, args=(n, settings, results))
            )
            processes[-1].start()

        deadline = time.monotonic() + ABORT_TIMEOUT
        ready = 0
        while ready < settings.num_publishers:
            if time.monotonic() > deadline:
                raise BenchmarkError("The publishers didn't connect in time.")
            msg = control.read_message(timeout=0.1)
            if msg is not None and msg.type_id == mt["PUBLISHER_READY"]:
                ready += 1
            _raise_reported_error(results)

        for n in range(1, settings.num_subscribers + 1):
            processes.append(
                ctx.Process(target=subscriber_loop, args=(n, settings, results))
            )
            processes[-1].start()

        collected: list[RoleResult] = []
        exit_sent = False
        while len(collected) < len(processes):
            try:
                item = results.get(timeout=0.1)
            except queue.Empty:
                if time.monotonic() > deadline:
                    if exit_sent:
                        raise BenchmarkError(
                            "The run was stopped, but not every process reported."
                        )
                    print("Run timed out; sending EXIT.", file=sys.stderr)
                    control.send_signal(mt["EXIT"])
                    exit_sent = True
                    deadline = time.monotonic() + 10
                continue
            if item[0] == "error":
                raise BenchmarkError(item[2])
            collected.append(RoleResult(*item))
        return sorted(collected, key=lambda r: (r.role, r.index))
    finally:
        for process in processes:
            process.join(timeout=10)
            if process.is_alive():
                process.terminate()
        control.disconnect()


def _raise_reported_error(results: Any) -> None:
    """Raise an error a process has reported while publishers are starting.

    Args:
        results: The run's result queue. Nothing but errors can be on it yet.

    Raises:
        BenchmarkError: A process reported an error.
    """
    try:
        item = results.get_nowait()
    except queue.Empty:
        return
    raise BenchmarkError(item[2] if item[0] == "error" else f"Unexpected {item!r}")


def wait_for_manager(
    server: str,
    timeout: float,
    process: Optional[subprocess.Popen[bytes]] = None,
) -> None:
    """Wait until a manager accepts a client.

    Args:
        server: The manager's address.
        timeout: Seconds to keep trying.
        process: The manager's process, if the benchmark started it; waiting
            stops if it exits.

    Raises:
        BenchmarkError: No manager accepted a client in time.
    """
    defs = load_definitions()
    deadline = time.monotonic() + timeout
    while True:
        try:
            probe = pyrtma.Client(definitions=defs)
            probe.connect(server_name=server, timeout=1)
            probe.disconnect()
            return
        except MessageManagerNotFound as e:
            exited = process is not None and process.poll() is not None
            if exited or time.monotonic() > deadline:
                raise BenchmarkError(str(e)) from e
            time.sleep(0.05)


def start_manager() -> tuple[subprocess.Popen[bytes], str]:
    """Start a message manager on a free loopback port.

    Raises:
        BenchmarkError: It exited, or didn't accept a client in time.

    Returns:
        The manager's process and its address.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    server = f"127.0.0.1:{port}"
    process = subprocess.Popen(
        [sys.executable, "-m", "pyrtma.manager"]
        + ["-a", "127.0.0.1", "-p", str(port), "--log-level", "WARN"],
        stdout=subprocess.DEVNULL,
    )
    try:
        wait_for_manager(server, MANAGER_START_TIMEOUT, process)
    except BenchmarkError:
        process.kill()
        process.wait()
        raise
    return process, server


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _rate(value: Optional[float]) -> str:
    return "-" if value is None else f"{value:,.0f}"


def report(settings: Settings, summaries: Sequence[RunSummary]) -> str:
    """Format a table of the runs, with the median and range of the rates.

    Args:
        settings: The configuration that was run.
        summaries: One summary per run, in order.

    Returns:
        The report's lines.
    """
    wire = HEADER_SIZE + settings.msg_size
    lines = [
        f"{_count(settings.num_publishers, 'publisher')}, "
        f"{_count(settings.num_subscribers, 'subscriber')}, "
        f"{_count(settings.total, 'message')} of {settings.msg_size} bytes "
        f"({wire} with the header), {_count(len(summaries), 'run')}",
        "",
        f"{'Run':>4}  {'Publisher msg/s':>15}  {'Subscriber msg/s':>16}"
        f"  {'Slowest':>8}  {'MB/s':>7}  {'Received':>8}",
    ]
    for n, s in enumerate(summaries, start=1):
        mbps = (s.subscriber_rate or s.publisher_rate) * wire / 1e6
        received = "-" if s.received is None else f"{s.received:.1%}"
        lines.append(
            f"{n:>4}  {_rate(s.publisher_rate):>15}  {_rate(s.subscriber_rate):>16}"
            f"  {_rate(s.slowest_subscriber_rate):>8}  {mbps:>7.1f}  {received:>8}"
        )
    lines.append("")
    pub = median_and_range([s.publisher_rate for s in summaries])
    lines.append(
        f"Publisher rate:  median {pub[0]:,.0f} msg/s, range {pub[1]:,.0f} to {pub[2]:,.0f}"
    )
    sub_rates = [s.subscriber_rate for s in summaries if s.subscriber_rate is not None]
    if sub_rates:
        sub = median_and_range(sub_rates)
        lines.append(
            f"Subscriber rate: median {sub[0]:,.0f} msg/s, range {sub[1]:,.0f} to {sub[2]:,.0f}"
        )
    return "\n".join(lines)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse the command line.

    Args:
        argv: The arguments, without the program name; ``sys.argv`` if None.

    Returns:
        The parsed arguments.
    """
    parser = argparse.ArgumentParser(description="pyrtma throughput benchmark")
    parser.add_argument(
        "-ms",
        dest="msg_size",
        type=int,
        default=128,
        choices=MSG_SIZES,
        help="Message payload size in bytes. Default: 128.",
    )
    parser.add_argument(
        "-n",
        dest="num_msgs",
        type=int,
        default=100000,
        help="Messages per run, shared by the publishers. Default: 100000.",
    )
    parser.add_argument(
        "-np",
        dest="num_publishers",
        type=int,
        default=1,
        help="Publisher processes. Default: 1.",
    )
    parser.add_argument(
        "-ns",
        dest="num_subscribers",
        type=int,
        default=1,
        help="Subscriber processes. Default: 1.",
    )
    parser.add_argument(
        "-r",
        dest="runs",
        type=int,
        default=1,
        help="Times to repeat the run. Default: 1.",
    )
    where = parser.add_mutually_exclusive_group()
    where.add_argument(
        "-s",
        dest="server",
        default="127.0.0.1:7111",
        help="Address of a running message manager. Default: 127.0.0.1:7111.",
    )
    where.add_argument(
        "--start-manager",
        action="store_true",
        help="Start a message manager on a free loopback port for the benchmark.",
    )
    args = parser.parse_args(argv)
    for name in ("num_msgs", "num_publishers", "runs"):
        if getattr(args, name) < 1:
            parser.error(f"{name} must be at least 1")
    if args.num_subscribers < 0:
        parser.error("num_subscribers can't be negative")
    return args


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the benchmark and print its report.

    Args:
        argv: The arguments, without the program name; ``sys.argv`` if None.

    Returns:
        The exit status: 0, or 1 if a run failed.
    """
    args = parse_args(argv)
    manager: Optional[subprocess.Popen[bytes]] = None
    try:
        server = args.server
        if args.start_manager:
            manager, server = start_manager()
        else:
            wait_for_manager(server, 0)
        settings = Settings(
            num_msgs=args.num_msgs,
            msg_size=args.msg_size,
            num_publishers=args.num_publishers,
            num_subscribers=args.num_subscribers,
            server=server,
        )
        where = "started by the benchmark" if manager else "already running"
        print(
            f"pyrtma {pyrtma.__version__}, Python {platform.python_version()}, "
            f"{platform.system()}; manager at {server}, {where}"
        )
        summaries = []
        for _ in range(args.runs):
            summaries.append(summarize_run(run_once(settings)))
        print(report(settings, summaries))
        return 0
    except (BenchmarkError, MessageManagerNotFound) as e:
        print(f"Benchmark failed: {e}", file=sys.stderr)
        return 1
    finally:
        if manager is not None:
            manager.terminate()
            try:
                manager.wait(timeout=10)
            except subprocess.TimeoutExpired:
                manager.kill()


if __name__ == "__main__":
    sys.exit(main())
