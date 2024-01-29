import pathlib
import ctypes
import os
import sys
import importlib
import pyrtma
import pyrtma.message
import json
import warnings

from typing import List, Union, Tuple, Generator, Dict, Any, Optional, Type
from ..validators import ByteArray
from ..message import RTMAJSONEncoder, Message, MessageHeader, MessageData
from ..message_base import MessageBase, MessageMeta
from ..exceptions import VersionMismatchWarning
from pyrtma.validators import Uint32, String


_unknown: Dict[int, Type[MessageData]] = {}


def legacy_variable_len_msg(msg_type: int) -> bool:
    var_msgs = set([31, 33, 34, 35, 37, 38, 46, 47, 64, 66, 67, 68, 77, 91, 93])
    return msg_type in var_msgs


def create_unknown(hdr: MessageHeader, raw: bytes) -> MessageData:
    if legacy_variable_len_msg(hdr.msg_type):
        name = f"LegacyMessageDef_{hdr.msg_type:04d}"
        cls = _unknown.get(hdr.msg_type)
        if cls is None:
            cls = type(
                name,
                (MessageData,),
                dict(
                    metaclass=MessageMeta,
                    type_name=name,
                    type_id=hdr.msg_type,
                    type_size=max(hdr.num_data_bytes, len(raw)),
                    var_length_text=String(256),
                ),
            )

        obj = cls()
        obj.var_length_text = raw[: min(256, len(raw))].decode()

    else:
        if len(raw) == hdr.num_data_bytes:
            name = f"UnknownMessageDef_{hdr.msg_type:04d}"
        else:
            name = f"InvalidMessageDef_{hdr.msg_type:04d}"

        cls = _unknown.get(hdr.msg_type)
        if cls is None:
            cls = type(
                name,
                (MessageData,),
                dict(
                    metaclass=MessageMeta,
                    type_name=name,
                    type_id=hdr.msg_type,
                    type_size=max(hdr.num_data_bytes, len(raw)),
                    raw=ByteArray(max(hdr.num_data_bytes, len(raw))),
                ),
            )

        obj = cls()
        obj.raw[:] = raw

    _unknown[hdr.msg_type] = cls

    return obj


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
        self.headers: List[MessageHeader] = []
        self.offsets: List[int] = []
        self.data: List[MessageData] = []
        self.messages: List[Message] = []
        self.context: Dict[str, Any] = {}
        self.skipped = 0

    def clear(self):
        self.file_path = None
        self.defs_path = None
        self.file_header = QLFileHeader()
        self.headers.clear()
        self.offsets.clear()
        self.data.clear()
        self.context.clear()
        self.messages.clear()
        self.skipped = 0

    def load(
        self,
        binfile: Union[str, os.PathLike],
        msgdefs: Union[str, os.PathLike],
        skip_unknown: bool = True,
    ):
        self.clear()
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
                mod = importlib.reload(sys.modules[fname])
            else:
                mod = importlib.import_module(fname)

        # Cache all the user defined objects associated with the data
        self.context = mod.get_context()

        try:
            messages = []
            headers = []
            data = []

            mt_to_mdf = {v.type_id: v for v in self.context["mdf"].values()}

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
                self.offsets = list(map(int, offsets))

                # Read the entire data block remaining
                d_bytes = f.read()

                unknown: List[int] = []
                # Extract the message data for each message
                for n, offset in enumerate(offsets):
                    header = headers[n]
                    msg_cls = mt_to_mdf.get(header.msg_type)
                    raw_bytes = d_bytes[offset : offset + header.num_data_bytes]

                    if msg_cls is None:
                        print(f"Unknown message definition: MT={header.msg_type}")
                        msg_data = create_unknown(header, raw_bytes)
                        unknown.append(n)

                    elif msg_cls.type_size != header.num_data_bytes:
                        print(
                            f"Warning: Message header indicates a message data size ({header.num_data_bytes}) that does not match the expected size of message type {msg_cls.type_name} ({msg_cls.type_size}). Message definitions may be out of sync."
                        )
                        msg_data = create_unknown(header, raw_bytes)
                        unknown.append(n)
                    else:
                        msg_data = msg_cls.from_buffer_copy(raw_bytes)

                    data.append(msg_data)
                    messages.append(Message(header, msg_data))

        finally:
            # Restore the orignal message def context
            pyrtma.message.set_msg_defs(ctx)

        # Store the results in the object
        self.file_header = file_header
        self.headers = []
        self.data = []
        self.messages = []
        if skip_unknown:
            self.skipped = len(unknown)
            for n, (h, d, m) in enumerate(zip(headers, data, messages, strict=True)):
                if n not in unknown:
                    self.headers.append(h)
                    self.data.append(d)
                    self.messages.append(m)

        else:
            self.headers.extend(headers)
            self.data.extend(data)
            self.messages.extend(messages)

    def export_json(self, file: Union[str, os.PathLike]):
        save_path = pathlib.Path(file)

        if save_path.exists():
            raise FileExistsError(f"File already exists at: {save_path}")

        if self.file_header.num_messages == 0:
            raise RuntimeError("QLReader does not contain any messages")

        # Write each message json object on a separate line
        with open(save_path, "w") as f:
            for msg in self.messages:
                # Open json object
                f.write("{")

                # Header json object
                f.write(msg.to_json(minify=True))

                # Close json object
                f.write("}\n")

    def iter_by_mt(self, msg_type: int) -> Generator[Message, Any, None]:
        for msg in self.messages:
            if msg.type_id == msg_type:
                yield (msg)

    def iter_by_src(
        self,
        mod_id: int,
    ) -> Generator[Message, Any, None]:
        for msg in self.messages:
            if msg.header.src_mod_id == mod_id:
                yield msg
