import pathlib
import ctypes
import os
import sys
import importlib
import pyrtma
import pyrtma.message
import base64
import json
import warnings

from typing import List, Union, Tuple, Generator, Dict, Any, Optional
from ..message import RTMAJSONEncoder, MessageHeader
from ..message_base import MessageBase, MessageMeta
from ..exceptions import VersionMismatchWarning
from pyrtma.validators import Uint32


def create_unknown(raw: bytes):
    return dict(_unknown=base64.b64encode(raw).decode())


class QLFileHeader(MessageBase, metaclass=MessageMeta):
    format_version: Uint32 = Uint32()
    total_bytes: Uint32 = Uint32()
    num_messages: Uint32 = Uint32()
    message_header_size: Uint32 = Uint32()
    data_block_offset_size: Uint32 = Uint32()
    num_data_bytes: Uint32 = Uint32()


class QLReader:
    def __init__(self) -> None:
        self.file_path: Optional[pathlib.Path] = None
        self.defs_path: Optional[pathlib.Path] = None
        self.file_header = QLFileHeader()
        self.headers: List[Dict[str, Any]] = []
        self.offsets: List[int] = []
        self.data: List[Dict[str, Any]] = []

    def clear(self):
        self.file_path = None
        self.defs_path = None
        self.file_header = QLFileHeader()
        self.headers.clear()
        self.offsets.clear()
        self.data.clear()

    def load(
        self,
        binfile: Union[str, os.PathLike],
        msgdefs: Union[str, os.PathLike],
        skip_unknown: bool = True,
    ):
        self.defs_path = pathlib.Path(msgdefs)
        self.file_path = pathlib.Path(binfile)

        # Import the message definitions
        base = self.defs_path.absolute().parent
        fname = self.defs_path.stem

        # Copy the current message def context before importing
        ctx = pyrtma.message.get_msg_defs()

        sys.path.insert(0, (str(base.absolute())))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", VersionMismatchWarning)
            if fname in sys.modules:
                importlib.reload(sys.modules[fname])
            else:
                importlib.import_module(fname)

        try:
            headers: List[Dict[str, Any]] = []
            data: List[Dict[str, Any]] = []

            with open(self.file_path, "rb") as f:
                # Parse binary file header
                file_header = QLFileHeader.from_buffer_copy(
                    f.read(ctypes.sizeof(QLFileHeader))
                )
                msg_header_size = file_header.message_header_size

                # Extract the message headers
                for _ in range(file_header.num_messages):
                    raw = f.read(msg_header_size)
                    headers.append(MessageHeader.from_buffer_copy(raw).to_dict())

                # Extract the message data offsets for each message
                offset_size = file_header.data_block_offset_size
                offsets = (ctypes.c_uint32 * file_header.num_messages).from_buffer_copy(
                    f.read(offset_size * file_header.num_messages)
                )
                self.offsets = list(map(int, offsets))

                # Read the entire data block remaining
                d_bytes = f.read()

                unknown: List[int] = []
                # Extract the message data for each message
                for n, offset in enumerate(offsets):
                    header = headers[n]
                    msg_cls = pyrtma.get_msg_cls(header["msg_type"])
                    raw_bytes = d_bytes[offset : offset + header["num_data_bytes"]]

                    if msg_cls is None:
                        print(f"Unknown message definition: MT={header['msg_type']}")
                        msg = create_unknown(raw_bytes)
                        unknown.append(n)

                    elif msg_cls.type_size != header["num_data_bytes"]:
                        print(
                            f"Warning: Message header indicates a message data size ({header['num_data_bytes']}) that does not match the expected size of message type {msg_cls.type_name} ({msg_cls.type_size}). Message definitions may be out of sync."
                        )
                        msg = create_unknown(raw_bytes)
                        unknown.append(n)
                    else:
                        msg = msg_cls.from_buffer_copy(raw_bytes).to_dict()

                    data.append(msg)

        finally:
            # Restore the orignal message def context
            pyrtma.message.set_msg_defs(ctx)

        # Store the results in the object
        self.file_header = file_header
        self.headers = []
        self.data = []
        if skip_unknown:
            for n, (h, d) in enumerate(zip(headers, data, strict=True)):
                if n not in unknown:
                    self.headers.append(h)
                    self.data.append(d)

        else:
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
                f.write(json.dumps(header, cls=RTMAJSONEncoder, separators=(",", ":")))

                f.write(",")

                # Data json object
                f.write('"data":')
                f.write(json.dumps(data, cls=RTMAJSONEncoder, separators=(",", ":")))

                # Close json object
                f.write("}\n")

    def iter_by_mt(
        self, msg_type: int
    ) -> Generator[Tuple[Dict[str, Any], Dict[str, Any]], Any, None]:
        for header, data in zip(self.headers, self.data, strict=True):
            if header["msg_type"] == msg_type:
                yield (header, data)

    def iter_by_src(
        self,
        mod_id: int,
    ) -> Generator[Tuple[Dict[str, Any], Dict[str, Any]], Any, None]:
        for header, data in zip(self.headers, self.data, strict=True):
            if header["src_mod_id"] == mod_id:
                yield (header, data)
