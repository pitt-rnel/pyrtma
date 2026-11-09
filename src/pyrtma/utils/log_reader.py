import pathlib
import ctypes
import logging
import os
import time

from concurrent.futures import ThreadPoolExecutor
from types import ModuleType
from typing import Generator, Any, Iterable

from pyrtma.header import MessageHeader
from pyrtma.message import Message
from pyrtma.exceptions import UnknownMessageType, MessageDefinitionsError
from pyrtma.definitions import MessageDefinitions
from pyrtma.loader import load_message_definitions

_logger = logging.getLogger(__name__)


def _filedialog() -> ModuleType:
    """Import ``tkinter.filedialog`` when a file has to be chosen.

    Importing it at module level broke importing the data logger where
    ``tkinter`` isn't installed, such as on headless Linux.

    Raises:
        RuntimeError: ``tkinter`` isn't available.

    Returns:
        The ``tkinter.filedialog`` module.
    """
    try:
        from tkinter import filedialog
    except ImportError as e:
        raise RuntimeError(
            "tkinter isn't available to choose a file; pass the paths instead."
        ) from e
    return filedialog


def _wanted(
    msg_type: int,
    type_name: str | None,
    include: list[str | int] | None,
    exclude: list[str | int] | None,
) -> bool:
    """Apply the ``include`` and ``exclude`` filters to one message type.

    Args:
        msg_type: The message type.
        type_name: Its name, or None when the definitions don't have it, in
            which case only numbers in the filters can match it.
        include: Types to keep, by number or name; None or empty keeps all.
        exclude: Types to drop, by number or name.

    Returns:
        True if messages of this type are to be loaded.
    """
    names = (msg_type,) if type_name is None else (msg_type, type_name)
    if include and not any(n in include for n in names):
        return False
    if exclude and any(n in exclude for n in names):
        return False
    return True


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

    def add(self, other: list[Message], sort: bool = True):
        """Add messages to the log and sort by receive time"""
        self._log.extend(other)
        if sort:
            self._log.sort(key=lambda x: x.header.recv_time)

    def sort(self):
        """Sort the log by receive time"""
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

        self.log = MessageLog()

    def _load_definitions(
        self, msg_defs: str | pathlib.Path | None = None
    ) -> MessageDefinitions:
        if msg_defs is None:
            msg_defs_file = _filedialog().askopenfilename(
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
            chosen: tuple[str, ...] = tuple(
                _filedialog().askopenfilenames(
                    initialdir=pathlib.Path.home(),
                    title="Select QL Files",
                    filetypes=(("QL files", "*.bin*"), ("All files", "*.*")),
                )
            )

            if len(chosen) <= 0:
                raise RuntimeError("No quicklogger .bin files were selected.")
            binfiles = chosen

        paths = [pathlib.Path(p) for p in binfiles]

        for binfile_path in paths:
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
                for binfile_path in paths
            ]

            for future in futures:
                msgs = future.result()
                self.log.add(msgs, sort=False)

            self.log.sort()

        return self.log

    def _parse_ql_file(
        self,
        binfile: pathlib.Path,
        include: list[str | int] | None = None,
        exclude: list[str | int] | None = None,
        throw: bool = True,
    ):
        """Parse a single QL file and return the messages.

        ``include`` and ``exclude`` are applied before a message is checked
        against the definitions, so a type the definitions don't have, or have
        with another size, can be filtered out to load the rest.

        Args:
            binfile: The file.
            include: Types to keep, by number or name; None keeps all.
            exclude: Types to drop, by number or name.
            throw: Raise on a message that can't be decoded or a truncated
                file. When False, such messages are logged and skipped, and a
                truncated file loads every message that is complete in it.

        Raises:
            UnknownMessageType: With ``throw``, a type has no definition.
            MessageDefinitionsError: With ``throw``, a message's size doesn't
                match its definition.
            ValueError: With ``throw``, the file is truncated.

        Returns:
            The messages, in file order.
        """

        print(f"Parsing QL File: {binfile}")

        start_time = time.perf_counter()

        binfile_path = pathlib.Path(binfile)
        msgs: list[Message] = []
        raw = binfile_path.read_bytes()

        def problem(text: str) -> None:
            if throw:
                raise ValueError(text)
            _logger.warning(text)

        # Parse binary file header
        if len(raw) < ctypes.sizeof(BinFileHeader):
            problem(f"{binfile} is truncated: its file header is incomplete.")
            return msgs
        file_header = BinFileHeader.from_buffer_copy(raw)
        count = file_header.num_messages
        msg_header_size = file_header.message_header_size
        offset_size = file_header.data_block_offset_size

        # The headers, then an offset per message, then the data block. A
        # message can only be read when its header, its offset and all of its
        # data are in the file.
        headers_start = ctypes.sizeof(BinFileHeader)
        offsets_start = headers_start + count * msg_header_size
        data_start = offsets_start + count * offset_size
        if len(raw) < data_start:
            part = "message headers" if len(raw) < offsets_start else "offsets"
            problem(f"{binfile} is truncated in its {part}; no data can be located.")
            return msgs

        offsets = (ctypes.c_uint32 * count).from_buffer_copy(raw, offsets_start)
        data = memoryview(raw)[data_start:]

        # Extract the message data for each message
        for n, offset in enumerate(offsets):
            header = MessageHeader.from_buffer_copy(
                raw, headers_start + n * msg_header_size
            )

            try:
                msg_cls = self.definitions.get_msg_cls(header.msg_type)
            except UnknownMessageType:
                msg_cls = None

            # Filter first, so an excluded type is never checked.
            type_name = None if msg_cls is None else msg_cls.type_name
            if not _wanted(header.msg_type, type_name, include, exclude):
                continue

            if msg_cls is None:
                err_msg = (
                    f"Message type {header.msg_type} not found in message definitions"
                )
                if throw:
                    raise UnknownMessageType(err_msg)
                _logger.warning(err_msg)
                continue

            if msg_cls.type_size != header.num_data_bytes:
                err_msg = f"Message type {header.msg_type} has a data size ({header.num_data_bytes}) that does not match the expected size of {msg_cls.type_size} for {msg_cls.type_name}"
                if throw:
                    raise MessageDefinitionsError(err_msg)
                _logger.warning(err_msg)
                continue

            if offset + header.num_data_bytes > len(data):
                problem(
                    f"{binfile} is truncated: {n} of {count} messages have all "
                    "their data."
                )
                break

            # Decode the message data from the raw bytes using the message class
            msg_data = msg_cls.from_buffer_copy(data, offset)

            # Store the message with its header and data in the list of messages
            msgs.append(Message(header=header, data=msg_data))

        end_time = time.perf_counter()
        print(
            f"Finished parsing {len(msgs)} messages from {binfile} in {end_time - start_time:.4f} seconds"
        )
        return msgs
