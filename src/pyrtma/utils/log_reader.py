import pathlib
import ctypes
import os
import shutil
import tempfile
import datetime
import stat

import multiprocessing
import queue
import subprocess
import json

from multiprocessing.synchronize import Event
from dataclasses import dataclass, field
from typing import Generator, Any

from tkinter import filedialog


class BinFileHeader(ctypes.Structure):
    _fields_ = (
        ("format_version", ctypes.c_uint32),
        ("total_bytes", ctypes.c_uint32),
        ("num_messages", ctypes.c_uint32),
        ("message_header_size", ctypes.c_uint32),
        ("data_block_offset_size", ctypes.c_uint32),
        ("num_data_bytes", ctypes.c_uint32),
    )


@dataclass
class MessageLog:
    filename: str
    _log: list[dict] = field(default_factory=list)

    @property
    def metadata(self) -> list[dict]:
        return [item["metadata"] for item in self._log]

    @property
    def names(self) -> list[dict]:
        return [item["metadata"]["type_name"] for item in self._log]

    @property
    def headers(self) -> list[dict]:
        return [item["header"] for item in self._log]

    @property
    def data(self) -> list[dict]:
        return [item["data"] for item in self._log]

    def append(self, item: dict):
        self._log.append(item)

    def export_json(self, save_file: str | os.PathLike):
        save_path = pathlib.Path(save_file)

        if save_path.exists():
            raise FileExistsError(f"File already exists at: {save_path}")

        if len(self._log) == 0:
            raise RuntimeError("MessageLog does not contain any messages")

        # Write each message json object on a separate line
        with open(save_path, "w") as f:
            for msg in self._log:
                f.write(json.dumps(msg, separators=(",", ":")))
                f.write("\n")

    def iter_by_mt(self, msg_type: int | str) -> Generator[dict, Any, None]:
        if isinstance(msg_type, str):
            for msg in self._log:
                if msg["metadata"]["type_name"] == msg_type:
                    yield (msg)
        elif isinstance(msg_type, int):
            for msg in self._log:
                if msg["header"]["msg_type"] == msg_type:
                    yield (msg)

    def iter_by_src(
        self,
        src_id: int,
    ) -> Generator[dict, Any, None]:
        for msg in self._log:
            if msg["header"]["src_mod_id"] == src_id:
                yield msg


class LogReader:

    @staticmethod
    def browse() -> MessageLog:
        msg_defs_file = filedialog.askopenfilename(
            initialdir=pathlib.Path.home(),
            title="Select the Message Definition File",
            filetypes=(("python files", "*.py*"), ("All files", "*.*")),
        )

        msgdefs_path = pathlib.Path(msg_defs_file)

        binfile = filedialog.askopenfilename(
            initialdir=msgdefs_path.parent.parent,
            title="Select QL File",
            filetypes=(("QL file", "*.bin*"), ("All files", "*.*")),
        )

        return LogReader.load(msgdefs_path, binfile)

    @staticmethod
    def load(
        msg_defs: str | pathlib.Path,
        binfile: str | pathlib.Path,
        include: list[str | int] | None = None,
        exclude: list[str | int] | None = None,
        include_unknown: bool = False,
    ) -> MessageLog:
        # Get message defs compiled version
        msgdefs_path = pathlib.Path(msg_defs)
        with open(msgdefs_path) as f:
            for line in f.readlines():
                if line.startswith("COMPILED_PYRTMA_VERSION"):
                    version = "v" + line.split("=")[1].strip().strip('"')
                    print(version)
                    break

        # User message data
        # Note: We don't copy the data file
        binfile_path = pathlib.Path(binfile)

        # Get the pyrtma repo location
        pyrtma_env = os.getenv("PYRTMA")

        if pyrtma_env is None:
            raise RuntimeError(
                "Unable to find pyrtma repo location on your system. No PYRTMA env var set."
            )

        pyrtma_path = pathlib.Path(pyrtma_env)

        if not pyrtma_path.exists():
            raise FileNotFoundError(f"No pyrtma repo found at {pyrtma_path}")

        # Create a temp copy of the pyrtma repo
        date = datetime.datetime.now()
        timestamp = date.strftime("%Y%m%d_%H%M%S")
        temp_path = pathlib.Path(tempfile.gettempdir()) / f"ql_reader_{timestamp}"
        temp_path.mkdir(exist_ok=False)
        pyrtma_copy = temp_path / "pyrtma"
        shutil.copytree(pyrtma_path, pyrtma_copy)

        # Create a temp copy of the users message defs file
        msgdefs_copy = temp_path / "message_defs.py"
        shutil.copy(msgdefs_path, msgdefs_copy)

        # Checkout the repo at the version tag
        proc = subprocess.run(
            f"git checkout {version}", cwd=str(pyrtma_copy), capture_output=True
        )
        if proc.returncode > 0:
            raise RuntimeError(
                f"Failed to checkout version tag {version} in pyrtma repo."
            )

        proc = subprocess.run(
            "git rev-parse HEAD", cwd=str(pyrtma_copy), capture_output=True
        )
        print(f"pyrtma commit = {proc.stdout.decode()[:8]}")

        log = _start_process(
            pyrtma_copy, msgdefs_copy, binfile_path, include, exclude, include_unknown
        )

        _cleanup_temp(temp_path)
        return log


def _cleanup_temp(temp_path: pathlib.Path):
    def on_exc(func, path, exc_info):
        # Note: Some files in .git directory on windows are read-only
        # We need to change the permissions for removal to succeed
        if ".git" in pathlib.Path(path).parts:
            if type(exc_info) is PermissionError:
                # Read-Only Permission issue
                if "WinError 5" in str(exc_info):
                    os.chmod(path, stat.S_IWRITE)
                    os.unlink(path)
                    return
                else:
                    raise

    shutil.rmtree(temp_path, onexc=on_exc)


def _parse_ql_file(
    done: Event,
    result: multiprocessing.Queue,
    pyrtma_repo: str,
    msgdefs: str,
    binfile: str,
    include: list[str | int] | None = None,
    exclude: list[str | int] | None = None,
    include_unknown: bool = False,
):
    """Separate process target function for importing and loading ql file"""
    import time
    import pathlib
    import sys
    import importlib
    import base64

    # Import pyrtma from the temp directory location
    base = pathlib.Path(pyrtma_repo) / "src"
    print(base)
    sys.path.insert(0, (str(base.absolute())))
    pyrtma = importlib.import_module("pyrtma")
    pyrtma_header = importlib.import_module("pyrtma", package="header")
    pyrtma_message = importlib.import_module("pyrtma", package="message")

    # Import pyrtma from the temp directory location
    msg_base = pathlib.Path(msgdefs).parent
    sys.path.insert(0, (str(msg_base.absolute())))
    md = importlib.import_module("message_defs")

    print(f"Parsing QL File: {binfile}")
    print(f"pyrtma version = {pyrtma.__file__}")
    print(f"pyrtma version = {pyrtma.__version__}")

    start_time = time.perf_counter()

    headers: list = []
    offsets: list[int] = []

    binfile_path = pathlib.Path(binfile)

    with open(binfile_path, "rb") as f:
        # Parse binary file header
        file_header = BinFileHeader.from_buffer_copy(
            f.read(ctypes.sizeof(BinFileHeader))
        )
        msg_header_size = file_header.message_header_size

        # Extract the message headers
        for _ in range(file_header.num_messages):
            raw = f.read(msg_header_size)
            headers.append(pyrtma_header.MessageHeader.from_buffer_copy(raw))

        # Extract the message data offsets for each message
        offset_size = file_header.data_block_offset_size
        offsets = (ctypes.c_uint32 * file_header.num_messages).from_buffer_copy(
            f.read(offset_size * file_header.num_messages)
        )
        offsets = list(map(int, offsets))

        # Read the entire data block remaining
        d_bytes = f.read()

        # Extract the message data for each message
        for n, offset in enumerate(offsets):
            header = headers[n]

            msg_cls = pyrtma_message.get_msg_cls(header.msg_type)
            raw_bytes = d_bytes[offset : offset + header.num_data_bytes]

            if msg_cls is None:
                if include_unknown:
                    metadata = dict(type_name="UNKNOWN", type_hash="")
                    msg_data = dict(_unknown=base64.b64encode(raw_bytes).decode())
                else:
                    continue
            elif msg_cls.type_size != header.num_data_bytes:
                if include_unknown:
                    print(
                        f"Warning: Message header indicates a message data size ({header.num_data_bytes}) that does not match the expected size of {msg_cls.type_size} for {msg_cls.type_name}"
                    )
                    print("Message definitions may be out of sync.")
                    metadata = dict(type_name="UNKNOWN", type_hash="")
                    msg_data = dict(_unknown=base64.b64encode(raw_bytes).decode())
                else:
                    continue
            else:
                if include and (
                    header.msg_type not in include and msg_cls.type_name not in include
                ):
                    continue

                if exclude and (
                    header.msg_type in exclude or msg_cls.type_name in exclude
                ):
                    continue

                metadata = dict(
                    type_name=msg_cls.type_name, type_hash=msg_cls.type_hash
                )
                msg_data = msg_cls.from_buffer_copy(raw_bytes).to_dict()

            # Pass the decoded data back to the main process via the result queue
            result.put_nowait(
                dict(metadata=metadata, header=header.to_dict(), data=msg_data)
            )

    end_time = time.perf_counter()
    print(f"Total Time: {end_time - start_time:0.1f} s")
    print("DONE")

    # Send sentinel
    result.put_nowait(None)

    # Close the queue and flush
    result.close()

    # Signal Process done event
    done.set()


def _start_process(
    pyrtma_copy: pathlib.Path,
    msgdefs_copy: pathlib.Path,
    binfile_path: pathlib.Path,
    include: list[str | int] | None = None,
    exclude: list[str | int] | None = None,
    include_unknown: bool = False,
):
    # Create a queue for the loading process to put its results
    result = multiprocessing.Queue()

    # Create an event to notify loading process has ended
    done = multiprocessing.Event()

    # Load the ql data from a separate process
    process = multiprocessing.Process(
        target=_parse_ql_file,
        args=(
            done,
            result,
            str(pyrtma_copy.absolute()),
            str(msgdefs_copy.absolute()),
            str(binfile_path.absolute()),
        ),
        kwargs=dict(include=include, exclude=exclude, include_unknown=include_unknown),
    )
    process.start()

    # Store the result in MessageLog
    log = MessageLog(filename=str(binfile_path.absolute()))

    while not done.is_set():
        try:
            item = result.get(timeout=0.050)
            if item is None:
                break

            log.append(item)
        except queue.Empty:
            pass

    # Read until empty
    while True:
        try:
            item = result.get(timeout=0.050)
            if item is None:
                break

            log.append(item)
        except queue.Empty:
            break

    process.join()

    return log
