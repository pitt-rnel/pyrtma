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

With ``--logger``, a data logger runs too, in its own process, and records
each run's messages in a QuickLogger dataset, in a temporary folder deleted at
the end. The manager waits for logger modules, so a logger that can't keep up
slows every module down. The report adds the fraction of messages logged,
read from the saved files' headers.
"""

from __future__ import annotations

import argparse
import contextlib
import ctypes
import multiprocessing
import platform
import queue
import socket
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

import pyrtma
from pyrtma.data_logger.dataset import Dataset
from pyrtma.definitions import MessageDefinitions
from pyrtma.exceptions import MessageManagerNotFound
from pyrtma.utils.log_reader import BinFileHeader

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
# How long the data logger has to start, or to answer a dataset request.
LOGGER_TIMEOUT = 60.0


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
        logged: The fraction of the messages sent that the data logger
            recorded, or None without ``--logger``.
    """

    publisher_rate: float
    subscriber_rate: float | None
    slowest_subscriber_rate: float | None
    received: float | None
    logged: float | None = None


def summarize_run(
    results: Sequence[RoleResult], logged: float | None = None
) -> RunSummary:
    """Combine one run's results.

    Args:
        results: Every publisher's and subscriber's result for the run.
        logged: The fraction of the messages that the data logger recorded,
            if one was recording.

    Returns:
        The run's summary.
    """
    publishers = [r for r in results if r.role == "publisher"]
    subscribers = [r for r in results if r.role == "subscriber"]
    publisher_rate = statistics.mean(r.rate for r in publishers) if publishers else 0.0
    if not subscribers:
        return RunSummary(publisher_rate, None, None, None, logged)
    expected = sum(r.expected for r in subscribers)
    return RunSummary(
        publisher_rate=publisher_rate,
        subscriber_rate=statistics.mean(r.rate for r in subscribers),
        slowest_subscriber_rate=min(r.rate for r in subscribers),
        received=sum(r.count for r in subscribers) / expected if expected else 1.0,
        logged=logged,
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
        # The manager handles a module's messages in order, so once this
        # reaches the benchmark, it has forwarded every message, to the data
        # logger too.
        client.send_signal(mt["PUBLISHER_DONE"])

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
        control.subscribe([mt["PUBLISHER_READY"], mt["PUBLISHER_DONE"]])
        for n in range(1, settings.num_publishers + 1):
            processes.append(
                ctx.Process(target=publisher_loop, args=(n, settings, results))
            )
            processes[-1].start()

        deadline = time.monotonic() + ABORT_TIMEOUT
        ready = 0
        # Without subscribers, a publisher can finish before the others are
        # ready, so its PUBLISHER_DONE is counted here too.
        done = 0
        while ready < settings.num_publishers:
            if time.monotonic() > deadline:
                raise BenchmarkError("The publishers didn't connect in time.")
            msg = control.read_message(timeout=0.1)
            if msg is not None and msg.type_id == mt["PUBLISHER_READY"]:
                ready += 1
            elif msg is not None and msg.type_id == mt["PUBLISHER_DONE"]:
                done += 1
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

        # Every publisher reported, so its PUBLISHER_DONE has been sent; wait
        # for the manager to have handled them all before the run ends.
        while done < settings.num_publishers:
            if time.monotonic() > deadline:
                raise BenchmarkError("The manager didn't pass on PUBLISHER_DONE.")
            msg = control.read_message(timeout=0.1)
            if msg is not None and msg.type_id == mt["PUBLISHER_DONE"]:
                done += 1
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
    process: subprocess.Popen[bytes] | None = None,
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


def count_logged(path: Path) -> int:
    """Count the messages in a QuickLogger file, from its header alone.

    Args:
        path: The file.

    Returns:
        How many messages it holds.
    """
    with path.open("rb") as file:
        header = BinFileHeader.from_buffer_copy(file.read(ctypes.sizeof(BinFileHeader)))
    return header.num_messages


class DataLoggerRecording:
    """A data logger, in its own process, recording each run's messages.

    Each run gets a QuickLogger dataset of the benchmark's message type,
    started before the run and removed after it. Everything is written to a
    temporary folder, which :meth:`close` deletes along with the process.

    Args:
        server: The manager's address.
        msg_size: The benchmark's message size, which sets the type recorded.

    Raises:
        BenchmarkError: The data logger didn't start.
    """

    def __init__(self, server: str, msg_size: int) -> None:
        self._server = server
        self._defs = load_definitions()
        self._msg_type = self._defs.MT[f"TEST_MSG_{msg_size}"]
        self._runs = 0
        self._folder = Path(tempfile.mkdtemp(prefix="pyrtma_bench_"))
        self._process = subprocess.Popen(
            [sys.executable, "-m", "pyrtma.data_logger"]
            + ["-m", server, "-d", str(DEFS_PATH), "--log-level", "WARN"],
            stdout=subprocess.DEVNULL,
        )
        try:
            self._wait_until_ready()
        except BaseException:
            self.close()
            raise

    def __enter__(self) -> DataLoggerRecording:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def _dataset(self, name: str) -> Dataset:
        return Dataset(
            name=name,
            save_path=self._folder,
            filename=name,
            formatter="quicklogger",
            msg_types=[self._msg_type],
            mm_ip=self._server,
            definitions=self._defs,
        )

    def _wait_until_ready(self) -> None:
        """Ask for the data logger's configuration until it answers.

        Raises:
            BenchmarkError: It exited, or didn't answer in time.
        """
        probe = self._dataset("bench_probe")
        try:
            deadline = time.monotonic() + LOGGER_TIMEOUT
            next_request = 0.0
            while probe.datalogger_config is None:
                if self._process.poll() is not None:
                    raise BenchmarkError("The data logger exited before it was ready.")
                now = time.monotonic()
                if now > deadline:
                    raise BenchmarkError("The data logger didn't answer in time.")
                if now >= next_request:
                    probe.request_data_logger_config()
                    next_request = now + 0.25
                probe.poll(timeout=0.05)
        finally:
            probe.close()

    def _wait(self, dataset: Dataset, done: Callable[[], bool], what: str) -> None:
        """Read the data logger's replies until a dataset reaches a state.

        Args:
            dataset: The dataset.
            done: Whether it has reached the state.
            what: The state, for the error message.

        Raises:
            BenchmarkError: The data logger reported an error, exited, or
                didn't reply in time.
        """
        deadline = time.monotonic() + LOGGER_TIMEOUT
        while not done():
            if self._process.poll() is not None:
                raise BenchmarkError("The data logger exited.")
            if time.monotonic() > deadline:
                raise BenchmarkError(f"The data logger didn't report {what} in time.")
            error = dataset.poll(timeout=0.1)
            if error is not None:
                raise BenchmarkError(
                    f"The data logger reported {error.exc_type}: {error.msg}"
                )

    def start(self) -> Dataset:
        """Add and start a dataset for the next run.

        Raises:
            BenchmarkError: As for :meth:`_wait`.

        Returns:
            The recording dataset.
        """
        self._runs += 1
        dataset = self._dataset(f"bench{self._runs}")
        try:
            dataset.add()
            self._wait(dataset, lambda: dataset.added, "the dataset added")
            dataset.start()
            self._wait(dataset, lambda: dataset.started, "the dataset started")
        except BaseException:
            dataset.close()
            raise
        return dataset

    def finish(self, dataset: Dataset) -> int:
        """Stop and remove a run's dataset, and count what it recorded.

        The data logger reports a dataset removed only once its files are
        finished, so they are complete when they're counted. They're deleted
        once counted.

        Args:
            dataset: The run's dataset, from :meth:`start`.

        Raises:
            BenchmarkError: As for :meth:`_wait`.

        Returns:
            How many messages its files hold.
        """
        try:
            dataset.stop()
            self._wait(dataset, lambda: dataset.stopped, "the dataset stopped")
            dataset.remove()
            self._wait(dataset, lambda: dataset.removed, "the dataset removed")
            count = 0
            for saved in dataset.saved:
                path = Path(saved)
                count += count_logged(path)
                path.unlink()
            return count
        finally:
            dataset.close()

    def close(self) -> None:
        """Stop the data logger and delete what it wrote."""
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait()
        shutil.rmtree(self._folder, ignore_errors=True)


def _count(n: int, noun: str) -> str:
    return f"{n} {noun}" if n == 1 else f"{n} {noun}s"


def _percent(value: float | None) -> str:
    return "-" if value is None else f"{value:.1%}"


def _rate(value: float | None) -> str:
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
    logging = any(s.logged is not None for s in summaries)
    lines = [
        f"{_count(settings.num_publishers, 'publisher')}, "
        f"{_count(settings.num_subscribers, 'subscriber')}, "
        f"{_count(settings.total, 'message')} of {settings.msg_size} bytes "
        f"({wire} with the header), {_count(len(summaries), 'run')}"
        + (", with the data logger recording" if logging else ""),
        "",
        f"{'Run':>4}  {'Publisher msg/s':>15}  {'Subscriber msg/s':>16}"
        f"  {'Slowest':>8}  {'MB/s':>7}  {'Received':>8}"
        + (f"  {'Logged':>8}" if logging else ""),
    ]
    for n, s in enumerate(summaries, start=1):
        mbps = (s.subscriber_rate or s.publisher_rate) * wire / 1e6
        line = (
            f"{n:>4}  {_rate(s.publisher_rate):>15}  {_rate(s.subscriber_rate):>16}"
            f"  {_rate(s.slowest_subscriber_rate):>8}  {mbps:>7.1f}"
            f"  {_percent(s.received):>8}"
        )
        if logging:
            line += f"  {_percent(s.logged):>8}"
        lines.append(line)
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


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
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
    parser.add_argument(
        "--logger",
        action="store_true",
        help="Run a data logger that records each run in a QuickLogger dataset, "
        "in a temporary folder, and report how much it recorded.",
    )
    args = parser.parse_args(argv)
    for name in ("num_msgs", "num_publishers", "runs"):
        if getattr(args, name) < 1:
            parser.error(f"{name} must be at least 1")
    if args.num_subscribers < 0:
        parser.error("num_subscribers can't be negative")
    return args


def main(argv: Sequence[str] | None = None) -> int:
    """Run the benchmark and print its report.

    Args:
        argv: The arguments, without the program name; ``sys.argv`` if None.

    Returns:
        The exit status: 0, or 1 if a run failed.
    """
    args = parse_args(argv)
    manager: subprocess.Popen[bytes] | None = None
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
        with contextlib.ExitStack() as stack:
            recording: DataLoggerRecording | None = None
            if args.logger:
                recording = stack.enter_context(
                    DataLoggerRecording(server, args.msg_size)
                )
            for _ in range(args.runs):
                if recording is None:
                    summaries.append(summarize_run(run_once(settings)))
                    continue
                dataset = recording.start()
                try:
                    results = run_once(settings)
                finally:
                    logged = recording.finish(dataset)
                summaries.append(summarize_run(results, logged / settings.total))
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
