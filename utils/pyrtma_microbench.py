"""Per-operation costs on pyrtma's hot paths.

``pyrtma_bench.py`` measures throughput through a real manager, where every
process shares the machine and the slowest one sets the pace. This measures
single operations instead, so a change to one of them shows up on its own:

- Header and message field access, as the client and manager use them.
- ``Client.send_message`` to a stand-in manager that only drains the socket,
  and the ``select()`` and ``send()`` calls a send can be made of.
- ``Client.read_message`` from a stand-in that streams ready-made messages.
- The manager routing one message to five subscribers, with stub
  connections, so the system calls are left out.

The stand-ins run in their own process, accept one client, and answer its
``CONNECT_V2`` with an ACK. Each operation is timed ``-r`` times, ``-n``
operations at a time; the median and the best are reported per operation::

    python utils/pyrtma_microbench.py -n 100000 -r 5
"""

from __future__ import annotations

import argparse
import ctypes
import multiprocessing
import platform
import select
import socket
import statistics
import sys
import threading
import time
import timeit
from pathlib import Path
from typing import Any, Callable, Optional, Sequence

import pyrtma
import pyrtma.core_defs as cd
from pyrtma.validators import disable_message_validation

DEFS_PATH = (
    Path(__file__).resolve().parent.parent / "tests" / "test_msg_defs" / "test_defs.py"
)
HEADER_SIZE = ctypes.sizeof(pyrtma.MessageHeader)
# The size of the messages sent and read; the read and send figures are for it.
WIRE_MSG = "TEST_MSG_128"


def _recv_exact(conn: socket.socket, size: int) -> bytes:
    """Read exactly ``size`` bytes from a blocking socket.

    Args:
        conn: The socket.
        size: How many bytes.

    Raises:
        ConnectionError: The peer closed the connection first.

    Returns:
        The bytes.
    """
    data = bytearray()
    while len(data) < size:
        chunk = conn.recv(size - len(data))
        if not chunk:
            raise ConnectionError("The client closed the connection.")
        data += chunk
    return bytes(data)


def _recv_frame(conn: socket.socket) -> pyrtma.MessageHeader:
    """Read one message and return its header; the payload is discarded.

    Args:
        conn: The socket.

    Returns:
        The message's header.
    """
    header = pyrtma.MessageHeader.from_buffer_copy(_recv_exact(conn, HEADER_SIZE))
    if header.num_data_bytes:
        _recv_exact(conn, header.num_data_bytes)
    return header


def _drain(conn: socket.socket) -> None:
    """Read and discard everything until the peer closes.

    Args:
        conn: The socket.
    """
    try:
        while conn.recv(1 << 16):
            pass
    except OSError:
        pass


def stand_in(mode: str, count: int, ports: Any) -> None:
    """Act as a manager for one client, in its own process.

    Args:
        mode: ``"drain"`` to discard what the client sends, or ``"stream"``
            to send it ``count`` ``WIRE_MSG`` messages once it subscribes.
        count: Messages to stream.
        ports: A ``multiprocessing`` queue the listening port is put on.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        ports.put(listener.getsockname()[1])
        conn, _ = listener.accept()
    with conn:
        conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        _recv_frame(conn)  # CONNECT_V2
        ack = pyrtma.MessageHeader()
        ack.msg_type = cd.MT_ACKNOWLEDGE
        ack.src_mod_id = cd.MID_MESSAGE_MANAGER
        ack.dest_mod_id = cd.DYN_MOD_ID_START
        conn.sendall(bytes(ack))
        if mode == "drain":
            _drain(conn)
            return

        while _recv_frame(conn).msg_type != cd.MT_SUBSCRIBE:
            pass
        drainer = threading.Thread(target=_drain, args=(conn,), daemon=True)
        drainer.start()
        defs = pyrtma.load_message_definitions(DEFS_PATH)
        data = defs.MDF[WIRE_MSG].from_random()
        header = pyrtma.MessageHeader()
        header.msg_type = data.type_id
        header.num_data_bytes = data.type_size
        header.version = data.type_hash
        wire = bytes(header) + bytes(data)
        block = 1000
        for start in range(0, count, block):
            conn.sendall(wire * min(block, count - start))
        drainer.join()


def _connect_to_stand_in(mode: str, count: int) -> tuple[pyrtma.Client, Any]:
    """Start a stand-in and connect a client to it.

    Args:
        mode: As for :func:`stand_in`.
        count: As for :func:`stand_in`.

    Returns:
        The connected client and the stand-in's process.
    """
    ctx = multiprocessing.get_context("spawn")
    ports: Any = ctx.Queue()
    process = ctx.Process(target=stand_in, args=(mode, count, ports), daemon=True)
    process.start()
    port = ports.get(timeout=30)
    client = pyrtma.Client(definitions=pyrtma.load_message_definitions(DEFS_PATH))
    client.connect(server_name=f"127.0.0.1:{port}")
    return client, process


def time_statement(
    stmt: str, namespace: dict[str, Any], number: int, repeat: int
) -> list[float]:
    """Time a statement, as seconds per execution for each repeat.

    Args:
        stmt: The statement.
        namespace: The names it uses.
        number: Executions per repeat.
        repeat: Repeats.

    Returns:
        Seconds per execution, one value per repeat.
    """
    totals = timeit.repeat(stmt, globals=namespace, number=number, repeat=repeat)
    return [total / number for total in totals]


def time_loop(action: Callable[[], Any], number: int, repeat: int) -> list[float]:
    """Time a callable, as seconds per call for each repeat.

    Args:
        action: The call to time.
        number: Calls per repeat.
        repeat: Repeats.

    Returns:
        Seconds per call, one value per repeat.
    """
    times = []
    for _ in range(repeat):
        tic = time.perf_counter()
        for _ in range(number):
            action()
        times.append((time.perf_counter() - tic) / number)
    return times


def field_operations(number: int, repeat: int) -> list[tuple[str, list[float]]]:
    """Time header and message field access.

    Args:
        number: Operations per repeat.
        repeat: Repeats.

    Returns:
        ``(name, seconds per operation for each repeat)`` per operation.
    """
    defs = pyrtma.load_message_definitions(DEFS_PATH)
    namespace = {
        "h": pyrtma.MessageHeader(),
        "H": pyrtma.MessageHeader,
        "start": defs.MDF["TEST_START"](),
        "blob": defs.MDF[WIRE_MSG]().blob,
        "time": time,
    }
    # What send_message does, with validation off as it has it.
    fill = (
        "hh = H(); hh.msg_type = 5002; hh.msg_count = 1; "
        "hh.send_time = time.perf_counter(); hh.recv_time = 0.0; "
        "hh.src_host_id = 0; hh.src_mod_id = 10000; hh.dest_host_id = 0; "
        "hh.dest_mod_id = 0; hh.num_data_bytes = 128; hh.remaining_bytes = 0; "
        "hh.reserved = 0; hh.version = 77"
    )
    results = [
        ("header field read", time_statement("h.msg_type", namespace, number, repeat)),
        (
            "header field write, validated",
            time_statement("h.recv_time = 1.5", namespace, number, repeat),
        ),
    ]
    with disable_message_validation():
        results.append(
            ("header fill, as sent", time_statement(fill, namespace, number, repeat))
        )
    results += [
        (
            "message int32 field write",
            time_statement("start.id = 7", namespace, number, repeat),
        ),
        (
            "array element write",
            time_statement("blob[0] = 7", namespace, number, repeat),
        ),
    ]
    return results


def send_operations(number: int, repeat: int) -> list[tuple[str, list[float]]]:
    """Time sends of a ``WIRE_MSG`` to a stand-in that drains.

    After ``send_message``, the two socket calls a send can be made of are
    timed on their own, on the same connection: a ``select()`` for
    writability, and a ``send()`` of a whole message's bytes. They show how
    much of a send the operating system takes.

    Args:
        number: Operations per repeat.
        repeat: Repeats.

    Returns:
        ``(name, seconds per operation for each repeat)`` per operation.
    """
    client, process = _connect_to_stand_in("drain", 0)
    try:
        data = client.definitions.MDF[WIRE_MSG].from_random()
        sock = client.sock
        wire = bytes(HEADER_SIZE) + bytes(data)

        def raw_send() -> None:
            # The stand-in reads bytes without framing them, so a partial
            # send does no harm here.
            try:
                sock.send(wire)
            except BlockingIOError:
                select.select([], [sock], [])

        size = WIRE_MSG.rsplit("_", 1)[1]
        return [
            (
                f"send_message, {size} B",
                time_loop(lambda: client.send_message(data), number, repeat),
            ),
            (
                "select() for writability",
                time_loop(lambda: select.select([], [sock], [], 0), number, repeat),
            ),
            (f"socket send(), {len(wire)} B", time_loop(raw_send, number, repeat)),
        ]
    finally:
        client.disconnect()
        process.join(timeout=10)


def read_operation(number: int, repeat: int) -> list[float]:
    """Time ``read_message`` of ``WIRE_MSG`` messages that have arrived.

    Args:
        number: Reads per repeat.
        repeat: Repeats.

    Returns:
        Seconds per read, one value per repeat.
    """
    client, process = _connect_to_stand_in("stream", number * repeat)
    try:
        client.subscribe([client.definitions.MT[WIRE_MSG]])
        return time_loop(lambda: client.read_message(timeout=-1), number, repeat)
    finally:
        client.disconnect()
        process.join(timeout=10)


class _StubConnection:
    """Stands in for a client socket that always has room."""

    def send(self, data: Any) -> int:
        return len(data)

    def close(self) -> None:
        pass


def manager_operation(
    number: int, repeat: int, subscribers: int = 5
) -> tuple[str, list[float]]:
    """Time the manager routing a ``WIRE_MSG``, with stub connections.

    The manager is constructed but not run. Its modules have stub
    connections whose ``send()`` takes everything at once, so this is the
    manager's own work per message, without the system calls.

    Args:
        number: Messages per repeat.
        repeat: Repeats.
        subscribers: Modules subscribed to the message.

    Returns:
        ``(name, seconds per message for each repeat)``.
    """
    import logging

    from pyrtma.manager import MessageManager, Module

    manager = MessageManager(ip_address="127.0.0.1", port=0, log_level=logging.ERROR)
    try:
        defs = pyrtma.load_message_definitions(DEFS_PATH)
        data = defs.MDF[WIRE_MSG].from_random()
        modules = []
        for n in range(subscribers + 1):
            conn: Any = _StubConnection()
            module = Module(
                conn,
                ("127.0.0.1", 20000 + n),
                manager.header_cls,
                name=f"stub{n}",
                mod_id=100 + n,
                connected=True,
            )
            manager.modules[conn] = module
            if n:
                manager.subscriptions[data.type_id].add(module)
                module.subs.add(data.type_id)
            modules.append(module)

        header = pyrtma.MessageHeader()
        header.msg_type = data.type_id
        header.src_mod_id = modules[0].mod_id
        header.num_data_bytes = data.type_size
        manager.data_view[: data.type_size] = bytes(data)

        def route() -> None:
            manager.process_message(modules[0], header)

        name = f"manager routing to {subscribers}, stub sockets"
        return name, time_loop(route, number, repeat)
    finally:
        manager.listen_socket.close()


def _duration(seconds: float) -> str:
    if seconds < 1e-6:
        return f"{seconds * 1e9:,.0f} ns"
    return f"{seconds * 1e6:,.2f} us"


def report(results: Sequence[tuple[str, list[float]]]) -> str:
    """Format the median and best time of each operation.

    Args:
        results: ``(name, seconds per operation for each repeat)``.

    Returns:
        The report's lines.
    """
    width = max(len(name) for name, _ in results)
    lines = [
        f"{'Operation':<{width}}  {'Median':>10}  {'Best':>10}  {'Per second':>12}"
    ]
    for name, times in results:
        median = statistics.median(times)
        lines.append(
            f"{name:<{width}}  {_duration(median):>10}  {_duration(min(times)):>10}"
            f"  {1 / median:>12,.0f}"
        )
    return "\n".join(lines)


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse the command line.

    Args:
        argv: The arguments, without the program name; ``sys.argv`` if None.

    Returns:
        The parsed arguments.
    """
    parser = argparse.ArgumentParser(description="pyrtma per-operation benchmark")
    parser.add_argument(
        "-n",
        dest="number",
        type=int,
        default=100000,
        help="Operations per repeat. Default: 100000.",
    )
    parser.add_argument(
        "-r", dest="repeat", type=int, default=5, help="Repeats. Default: 5."
    )
    args = parser.parse_args(argv)
    if args.number < 1 or args.repeat < 1:
        parser.error("-n and -r must be at least 1")
    return args


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Time every operation and print the report.

    Args:
        argv: The arguments, without the program name; ``sys.argv`` if None.

    Returns:
        The exit status, 0.
    """
    args = parse_args(argv)
    print(
        f"pyrtma {pyrtma.__version__}, Python {platform.python_version()}, "
        f"{platform.system()}; {args.number} operations, {args.repeat} repeats"
    )
    results = field_operations(args.number, args.repeat)
    results += send_operations(args.number, args.repeat)
    results.append(manager_operation(args.number, args.repeat))
    size = WIRE_MSG.rsplit("_", 1)[1]
    results.append(
        (f"read_message, {size} B", read_operation(args.number, args.repeat))
    )
    print(report(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
