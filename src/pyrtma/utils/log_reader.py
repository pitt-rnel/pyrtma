import pathlib
import ctypes
import os

import time

from pyrtma.header import MessageHeader
from pyrtma.message import Message
from pyrtma.exceptions import UnknownMessageType, MessageDefinitionsError

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Generator, Any, Iterable

from tkinter import filedialog

from pyrtma.definitions import MessageDefinitions
from pyrtma.loader import load_message_definitions


class BinFileHeader(ctypes.Structure):
    _fields_ = (
        ("format_version", ctypes.c_uint32),
        ("total_bytes", ctypes.c_uint32),
        ("num_messages", ctypes.c_uint32),
        ("message_header_size", ctypes.c_uint32),
        ("data_block_offset_size", ctypes.c_uint32),
        ("num_data_bytes", ctypes.c_uint32),
    )


class MessageLog:
    def __init__(self):
        self._log: list[Message] = []

    @property
    def names(self) -> set[str]:
        """Returns the unique message names in the log"""
        return set([item.name for item in self._log])

    @property
    def headers(self) -> list[MessageHeader]:
        """Returns the message headers in the log"""
        return [item.header for item in self._log]

    def add(self, other: list[Message]):
        """Add messages to the log and sort by receive time"""
        self._log.extend(other)
        self._log.sort(key=lambda x: x.header.recv_time)

    def export_json(self, save_file: str | os.PathLike):
        save_path = pathlib.Path(save_file)

        if save_path.exists():
            raise FileExistsError(f"File already exists at: {save_path}")

        if len(self._log) == 0:
            raise RuntimeError("MessageLog does not contain any messages")

        # Write each message json object on a separate line
        assert save_path.suffix in (
            ".jsonl",
            ".json",
        ), f"File extension must be .jsonl or .json, got {save_path.suffix}"

        with open(save_path, "w") as f:
            for msg in self._log:
                f.write(msg.to_json(minify=True))
                f.write("\n")

    def iter_by_mt(self, msg_type: int | str) -> Generator[Message, Any, None]:
        """Iterate over messages by message type."""
        if isinstance(msg_type, str):
            for msg in self._log:
                if msg.name == msg_type:
                    yield (msg)
        elif isinstance(msg_type, int):
            for msg in self._log:
                if msg.type_id == msg_type:
                    yield (msg)

    def iter_by_src(
        self,
        src_id: int,
    ) -> Generator[Message, Any, None]:
        """Iterate over messages by source module ID."""
        for msg in self._log:
            if msg.header.src_mod_id == src_id:
                yield msg


class LogReader:
    def __init__(self, definitions: str | pathlib.Path | MessageDefinitions | None):
        if isinstance(definitions, MessageDefinitions):
            self.definitions = definitions
        else:
            self.definitions = self._load_definitions(definitions)

    def _load_definitions(
        self, msg_defs: str | pathlib.Path | None = None
    ) -> MessageDefinitions:
        if msg_defs is None:
            msg_defs_file = filedialog.askopenfilename(
                initialdir=pathlib.Path.home(),
                title="Select the Message Definition File",
                filetypes=(("python files", "*.py*"), ("All files", "*.*")),
            )

            if msg_defs_file == "":
                raise RuntimeError("No message definition file was selected.")

            msg_defs = pathlib.Path(msg_defs_file)
        return load_message_definitions(msg_defs)

    def load(
        self,
        binfiles: Iterable[str | pathlib.Path] | None = None,
        include: list[str | int] | None = None,
        exclude: list[str | int] | None = None,
        throw: bool = True,
    ) -> MessageLog:
        if binfiles is None:
            binfiles = filedialog.askopenfilenames(
                initialdir=pathlib.Path.home(),
                title="Select QL Files",
                filetypes=(("QL files", "*.bin*"), ("All files", "*.*")),
            )

            if len(binfiles) <= 0:
                raise RuntimeError("No quicklogger .bin files were selected.")

        binfiles = [pathlib.Path(p) for p in binfiles]

        log = MessageLog()
        for binfile_path in binfiles:
            if not binfile_path.exists():
                raise FileNotFoundError(f"{binfile_path.absolute()}")

        with ThreadPoolExecutor() as executor:
            # Submit all file parses concurrently, then collect in input order.
            futures = [
                executor.submit(
                    self._parse_ql_file,
                    binfile_path,
                    include=include,
                    exclude=exclude,
                    throw=throw,
                )
                for binfile_path in binfiles
            ]

            for future in futures:
                msgs = future.result()
                log.add(msgs)

        return log

    def _parse_ql_file(
        self,
        binfile: pathlib.Path,
        include: list[str | int] | None = None,
        exclude: list[str | int] | None = None,
        throw: bool = True,
    ):
        """Parse a single QL file and return the messages."""

        print(f"Parsing QL File: {binfile}")

        start_time = time.perf_counter()

        headers: list[MessageHeader] = []
        offsets: list[int] = []

        binfile_path = pathlib.Path(binfile)
        msgs = []

        with open(binfile_path, "rb") as f:
            # Parse binary file header
            file_header = BinFileHeader.from_buffer_copy(
                f.read(ctypes.sizeof(BinFileHeader))
            )
            msg_header_size = file_header.message_header_size

            # Extract the message headers
            for _ in range(file_header.num_messages):
                raw = f.read(msg_header_size)
                headers.append(MessageHeader.from_buffer_copy(raw))

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

                try:
                    msg_cls = self.definitions.get_msg_cls(header.msg_type)
                except:
                    err_msg = f"Message type {header.msg_type} not found in message definitions"
                    if throw:
                        raise UnknownMessageType(err_msg)
                    else:
                        print(err_msg)
                        continue

                raw_bytes = d_bytes[offset : offset + header.num_data_bytes]

                if msg_cls.type_size != header.num_data_bytes:
                    err_msg = f"Message type {header.msg_type} has a data size ({header.num_data_bytes}) that does not match the expected size of {msg_cls.type_size} for {msg_cls.type_name}"
                    if throw:
                        raise MessageDefinitionsError(err_msg)
                    else:
                        print(err_msg)
                        continue

                # Check if message type is in the include or exclude lists, if provided
                if include and (
                    header.msg_type not in include and msg_cls.type_name not in include
                ):
                    continue

                if exclude and (
                    header.msg_type in exclude or msg_cls.type_name in exclude
                ):
                    continue

                # Decode the message data from the raw bytes using the message class
                msg_data = msg_cls.from_buffer_copy(raw_bytes)

                # Store the message with its header and data in the list of messages
                msgs.append(Message(header=header, data=msg_data))

        end_time = time.perf_counter()
        print(
            f"Finished parsing {len(msgs)} messages from {binfile} in {end_time - start_time:.4f} seconds"
        )
        return msgs
