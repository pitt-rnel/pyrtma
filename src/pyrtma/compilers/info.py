import pathlib

from textwrap import dedent
from pyrtma.parser import (
    Parser,
    ConstantExpr,
    ConstantString,
    TypeAlias,
    MT,
    MID,
    HID,
    MDF,
    SDF,
)


class InfoCompiler:
    def __init__(self, parser: Parser, filename: str, debug: bool = False):
        self.filename = filename
        self.debug = debug
        self.parser = parser

    def generate(self, out_filepath: pathlib.Path):
        with open(out_filepath, mode="w") as f:
            f.write(f"# {out_filepath}\n")
            f.write("# DO NOT EDIT BY HAND. FILE IS AUTO-GENERATED.\n\n")
            f.write(
                "# File contains a list of message and module ids currently in use.\n\n"
            )
            mids = list(self.parser.module_ids.values())
            mids.sort(key=lambda x: x.value)
            f.write("module_ids\n")
            for obj in mids:
                src = "/".join(obj.src.parts[-2:])
                f.write(f"{obj.value:4d}: {obj.name:<32} # {src}\n")
            f.write("\n\n")

            msg_ids = list(self.parser.message_ids.values())
            msg_ids.sort(key=lambda x: x.value)
            f.write("message_ids\n")
            for obj in msg_ids:
                src = "/".join(obj.src.parts[-2:])
                f.write(f"{obj.value:4d}: {obj.name:<32} # {src}\n")
            f.write("\n\n")
