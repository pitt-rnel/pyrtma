import pathlib
import ctypes
import os
import sys
import importlib
import pyrtma
import base64
import json

from typing import List, Union, Optional
from ..message import MessageData, MessageHeader


class UnknownMessageData:
    def __init__(self, raw: bytes):
        self._data = raw

    @property
    def data(self) -> bytes:
        return self._data

    def to_b64(self) -> str:
        return base64.b64encode(self._data).decode()

    def to_json(self, minify=True, **kwargs) -> str:
        d = dict(_raw=self.to_b64())
        if minify:
            return json.dumps(d, separators=(",", ":"))
        else:
            return json.dumps(d, indent=2)


class QLFileHeader(ctypes.Structure):
    _fields_ = [
        ("format_version", ctypes.c_uint32),
        ("total_bytes", ctypes.c_uint32),
        ("num_messages", ctypes.c_uint32),
        ("message_header_size", ctypes.c_uint32),
        ("data_block_offset_size", ctypes.c_uint32),
        ("num_data_bytes", ctypes.c_uint32),
    ]


class QLReader:
    def __init__(self) -> None:
        self.file_path: Optional[pathlib.Path] = None
        self.defs_path: Optional[pathlib.Path] = None
        self.file_header = QLFileHeader()
        self.headers: List[MessageHeader] = []
        self.data: List[Union[MessageData, UnknownMessageData]] = []

    def clear(self):
        self.file_path = None
        self.defs_path = None
        self.file_header = QLFileHeader()
        self.headers.clear()
        self.data.clear()

    def load(self, binfile: Union[str, os.PathLike], msgdefs: Union[str, os.PathLike]):
        self.defs_path = pathlib.Path(msgdefs)
        self.file_path = pathlib.Path(binfile)

        # Import the message definitions
        base = self.defs_path.absolute().parent
        fname = self.defs_path.stem
        sys.path.insert(0, (str(base.absolute())))
        importlib.import_module(fname)

        headers = []
        data: List[Union[MessageData, UnknownMessageData]] = []
        with open(self.file_path, "rb") as f:
            # Parse binary file header
            file_header = QLFileHeader.from_buffer_copy(
                f.read(ctypes.sizeof(QLFileHeader))
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

            # Read the entire data block remaining
            d = f.read()

            # Extract the message data for each message
            for n, offset in enumerate(offsets):
                header = headers[n]
                msg_cls = pyrtma.msg_defs.get(header.msg_type)
                raw_bytes = d[offset : offset + header.num_data_bytes]

                msg: Union[UnknownMessageData, MessageData]
                if msg_cls is None:
                    print(f"Unknown message definition: MT={header.msg_type}")
                    msg = UnknownMessageData(raw_bytes)

                else:
                    if msg_cls.type_size != header.num_data_bytes:
                        print(
                            f"Warning: Message header indicates a message data size ({header.num_data_bytes}) that does not match the expected size of message type {msg_cls.type_name} ({msg_cls.type_size}). Message definitions may be out of sync."
                        )
                        msg = UnknownMessageData(raw_bytes)
                    else:
                        msg = msg_cls.from_buffer_copy(raw_bytes)

                data.append(msg)

        # Store the results in the object
        self.file_header = file_header
        self.headers = headers
        self.data = data

    def export_json(self, file: Union[str, os.PathLike]):
        save_path = pathlib.Path(file)

        if save_path.exists():
            raise FileExistsError(f"File already exists at: {save_path}")

        if self.file_header.num_messages == 0:
            raise RuntimeError("QLReader does not contain any messages")

        # Write each message json object on a separate line
        with open(save_path, "w") as f:
            for header, data in zip(self.headers, self.data, strict=True):
                # Open json object
                f.write("{")

                # Header json object
                f.write('"header":')
                f.write(header.to_json(minify=True))

                f.write(",")

                # Data json object
                f.write('"data":')
                f.write(data.to_json(minify=True))

                # Close json object
                f.write("}\n")
