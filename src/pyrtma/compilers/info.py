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
            f.write("# {out_filepath}")
            f.write("# DO NOT EDIT BY HAND. FILE IS AUTO-GENERATED.\n\n")
            mids = list(self.parser.module_ids.values())
            mids.sort(key=lambda x: x.value)
            f.write(f"# {self.filename} info\n\n")
            f.write("module_ids\n")
            for obj in mids:
                f.write(f"{obj.value:4d}: {obj.name}\n")
            f.write("\n\n")

            msg_ids = list(self.parser.message_ids.values())
            msg_ids.sort(key=lambda x: x.value)
            f.write("message_ids\n")
            for obj in msg_ids:
                f.write(f"{obj.value:4d}: {obj.name}\n")
            f.write("\n\n")
