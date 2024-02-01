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
    Field,
)
from typing import Union
import subprocess
import sys
import os
from pyrtma.__version__ import __version__


# Field type name to ctypes
type_map = {
    "char": "ctypes.c_char",
    "unsigned char": "ctypes.c_ubyte",
    "byte": "ctypes.c_ubyte",
    "float": "ctypes.c_float",
    "double": "ctypes.c_double",
    "uint8": "ctypes.c_uint8",
    "uint16": "ctypes.c_uint16",
    "uint32": "ctypes.c_uint32",
    "uint64": "ctypes.c_uint64",
    "int8": "ctypes.c_int8",
    "int16": "ctypes.c_int16",
    "int32": "ctypes.c_int32",
    "int64": "ctypes.c_int64",
    # following unsized types are deprecated
    "int": "ctypes.c_int32",
    "signed int": "ctypes.c_int32",
    "unsigned int": "ctypes.c_uint32",
    "unsigned": "ctypes.c_uint32",
    "short": "ctypes.c_int16",
    "signed short": "ctypes.c_int16",
    "unsigned short": "ctypes.c_uint16",
    "long": "ctypes.c_int32",
    "signed long": "ctypes.c_int32",
    "unsigned long": "ctypes.c_uint32",
    "long long": "ctypes.c_int64",
    "signed long long": "ctypes.c_int64",
    "unsigned long long": "ctypes.c_uint64",
}

desctype_map = {
    "char": "Char",
    "byte": "Byte",
    "unsigned char": "Byte",
    "float": "Float",
    "double": "Double",
    "uint8": "Uint8",
    "uint16": "Uint16",
    "uint32": "Uint32",
    "uint64": "Uint64",
    "int8": "Int8",
    "int16": "Int16",
    "int32": "Int32",
    "int64": "Int64",
    # following unsized types are deprecated
    "int": "Int32",
    "signed int": "Int32",
    "unsigned int": "Uint32",
    "unsigned": "Uint32",
    "short": "Int16",
    "signed short": "Int16",
    "unsigned short": "Uint16",
    "long": "Int32",
    "signed long": "Int32",
    "unsigned long": "Uint32",
    "long long": "Int64",
    "signed long long": "Int64",
    "unsigned long long": "Uint64",
}
DEFAULT_BLACK_LEN = 88  # preferred line length
TAB = "    "


class PyDefCompiler:
    def __init__(self, parser: Parser, debug: bool = False):
        self.debug = debug
        self.parser = parser

    def generate_constant(self, c: ConstantExpr) -> str:
        return f"{c.name}: {type(c.value).__qualname__} = {c.value}\n"

    def generate_string_constant(self, c: ConstantString) -> str:
        return f"{c.name}: str = {c.value}\n"

    def generate_msg_type_id(self, mt: MT) -> str:
        return f"MT_{mt.name}: int = {mt.value}\n"

    def generate_module_id(self, mid: MID) -> str:
        return f"MID_{mid.name}: int = {mid.value}\n"

    def generate_host_id(self, hid: HID) -> str:
        return f"{hid.name}: int = {hid.value}\n"

    def generate_type_alias(self, td: TypeAlias) -> str:
        ftype = type_map.get(td.type_name)
        if ftype:
            return f"{td.name} = {ftype}\n"
        else:
            return f"{td.name} = {td.type_name}\n"

    def get_descriptor(self, ftype: str, flen: int) -> str:
        if ftype in type_map.keys():
            dtype = desctype_map[ftype]
            # Scalar Field
            if flen <= 1:
                return f":{dtype} = {dtype}()"

            # Array Field
            if dtype.startswith("Int") or dtype.startswith("Uint"):
                return f":IntArray[{dtype}] = IntArray({dtype}, {flen})"
            elif dtype.startswith("Float") or dtype.startswith("Double"):
                return f":FloatArray[{dtype}] = FloatArray({dtype}, {flen})"
            elif dtype.startswith("Char"):
                return f":String = String({flen})"
            elif dtype.startswith("Byte"):
                return f":ByteArray = ByteArray({flen})"
            else:
                raise RuntimeError(f"Unknown field descriptor {dtype}")

        # Message Def (Struct) Field
        elif ftype in self.parser.message_defs.keys():
            ftype = f"MDF_{ftype}"
            return (
                f":Struct[{ftype}] = Struct({ftype})"
                if flen == 0
                else f":StructArray[{ftype}] = StructArray({ftype}, {flen})"
            )

        # Struct Field
        elif ftype in self.parser.struct_defs.keys():
            ftype = f"{ftype}"
            return (
                f":Struct[{ftype}] = Struct({ftype})"
                if flen == 0
                else f":StructArray[{ftype}] = StructArray({ftype}, {flen})"
            )

        # Alias Field
        elif ftype in self.parser.aliases.keys():
            ftype = self.parser.aliases[ftype].type_name
            return self.get_descriptor(ftype, flen)

        else:
            raise RuntimeError(f"Unknown field name {ftype}")

    def generate_struct(self, sdf: SDF) -> str:
        dstr = "\n"
        for field in sdf.fields:
            desc = self.get_descriptor(field.type_name, field.length or 0)
            dstr += f"{'    ' * 3}{field.name}{desc}\n"

        msg_src = sdf.src.as_posix()
        type_def_str = repr(sdf.raw)
        type_def_rhs = 'type_def: ClassVar[str] = "'
        type_def_end = '"'
        type_def_line = f"{type_def_rhs}{type_def_str}{type_def_end}"
        type_def_line_len = len(TAB) + len(type_def_line)
        if type_def_line_len > DEFAULT_BLACK_LEN:
            type_def_rhs = f'type_def: ClassVar[\n{TAB *4}str\n{TAB *3}] = "'
            type_def_line = f"{type_def_rhs}{type_def_str}{type_def_end}"

        template = f"""\
        class {sdf.name}(MessageBase, metaclass=MessageMeta):
            type_name: ClassVar[str] = \"{sdf.name}\"
            type_hash: ClassVar[int] = 0x{sdf.hash[:8].upper()}
            type_size: ClassVar[int] = {sdf.size}
            type_source: ClassVar[str] = \"{msg_src}\"
            {type_def_line}

            {dstr}
        """
        return dedent(template)

    def generate_msg_def(self, mdf: MDF) -> str:
        dstr = "\n"
        for field in mdf.fields:
            desc = self.get_descriptor(field.type_name, field.length or 0)
            dstr += f"{'    ' * 3}{field.name}{desc}\n"

        msg_id = mdf.type_id
        msg_src = mdf.src.as_posix()
        type_def_str = repr(mdf.raw)
        type_def_rhs = 'type_def: ClassVar[str] = "'
        type_def_end = '"'
        type_def_line = f"{type_def_rhs}{type_def_str}{type_def_end}"
        type_def_line_len = len(TAB) + len(type_def_line)
        if type_def_line_len > DEFAULT_BLACK_LEN:
            type_def_rhs = f'type_def: ClassVar[\n{TAB *4}str\n{TAB *3}] = "'
            type_def_line = f"{type_def_rhs}{type_def_str}{type_def_end}"

        template = f"""\
        @pyrtma.message_def
        class MDF_{mdf.name}(MessageData, metaclass=MessageMeta):
            type_id: ClassVar[int] = {msg_id}
            type_name: ClassVar[str] = \"{mdf.name}\"
            type_hash: ClassVar[int] = 0x{mdf.hash[:8].upper()}
            type_size: ClassVar[int] = {mdf.size}
            type_source: ClassVar[str] = \"{msg_src}\"
            {type_def_line}

            {dstr}
        """
        return dedent(template)

    def generate_docstr(self) -> str:
        s = f"""\"\"\"This message def file was auto-generated by pyrtma.compile version {__version__}\"\"\"\n"""
        return s

    def generate_imports(self) -> str:
        s = """\
        import ctypes

        import pyrtma
        from pyrtma.__version__ import check_compiled_version
        from typing import ClassVar, Dict, Any

        from pyrtma.message_base import MessageBase, MessageMeta
        from pyrtma.message_data import MessageData
        from pyrtma.validators import Int8, Int16, Int32, Int64, Uint8, Uint16, Uint32, Uint64, Float, Double, Struct, IntArray, FloatArray, StructArray, Char, String, Byte, ByteArray
        
        """
        return dedent(s)

    def generate_context(self):
        s = """\
        def _create_context() -> Dict[str, Dict[str, Any]]:
            import sys

            ctx: Dict[str, Dict[str, Any]] = dict(constants={}, typedefs={}, mid={}, sdf={}, mt={}, mdf={})
            mod = sys.modules[__name__]
            for k, v in mod.__dict__.items():
                if k.startswith("_"):
                    continue

                if k.startswith("MT_"):
                    ctx["mt"][k[3:]] = v
                elif k.startswith("MID_"):
                    ctx["mid"][k[4:]] = v
                elif k.startswith("MDF_"):
                    ctx["mdf"][k[4:]] = v
                elif k.isupper():
                    if isinstance(v, (int, float, str)):
                        ctx["constants"][k] = v
                    elif v.__name__ is not k:
                        ctx["typedefs"][k] = v
                    elif issubclass(v, MessageBase):
                        ctx["sdf"][k] = v
                    else:
                        raise ValueError(f"Unknown object in {__name__}: {k}:{v}")
                else:
                    pass

            return ctx


        _ctx = _create_context()


        def get_context() -> Dict[str, Dict[str, Any]]:
            import copy

            return copy.deepcopy(_ctx)
        """
        return dedent(s)

    def generate(self, out_filepath: pathlib.Path):
        with open(out_filepath, mode="w") as f:
            f.write(self.generate_docstr())
            f.write(self.generate_imports())
            f.write("\n")

            # Version
            f.write(f'COMPILED_PYRTMA_VERSION: str = "{__version__}"\n')
            f.write("check_compiled_version(COMPILED_PYRTMA_VERSION)\n\n")

            f.write("# Constants\n")
            obj: Union[ConstantExpr, ConstantString, HID, MID, TypeAlias, SDF, MT, MDF]
            for obj in self.parser.constants.values():
                f.write(self.generate_constant(obj))
            f.write("\n")

            f.write("# String Constants\n")
            for obj in self.parser.string_constants.values():
                f.write(self.generate_string_constant(obj))
            f.write("\n")

            f.write("# Type Aliases\n")
            for obj in self.parser.aliases.values():
                f.write(self.generate_type_alias(obj))
            f.write("\n")

            f.write("# Host IDs\n")
            for obj in self.parser.host_ids.values():
                f.write(self.generate_host_id(obj))
            f.write("\n")

            f.write("# Module IDs\n")
            for obj in self.parser.module_ids.values():
                f.write(self.generate_module_id(obj))
            f.write("\n")

            f.write("# Message Type IDs\n")
            for obj in self.parser.message_ids.values():
                f.write(self.generate_msg_type_id(obj))
            f.write("\n\n")

            f.write("# Struct Definitions\n")
            for obj in self.parser.struct_defs.values():
                f.write(self.generate_struct(obj))
                f.write("\n\n")

            f.write("# Message Definitions\n")
            for obj in self.parser.message_defs.values():
                f.write(self.generate_msg_def(obj))
                f.write("\n\n")

            f.write("# User Context\n")
            f.write(self.generate_context())

        # run black formatter
        subprocess.run([sys.executable, "-m", "black", out_filepath], cwd=os.getcwd())
