import pathlib

from textwrap import dedent
from pyrtma.parser import (
    GeneratedSourceError,
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
import subprocess
import sys
from pyrtma.__version__ import __version__

# Field type name to ctypes
type_map = {
    "char": "ctypes.c_char",
    "signed char": "ctypes.c_int8",
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
    "signed char": "Int8",
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

    def is_struct_alias(self, td: TypeAlias) -> bool:
        """Whether an alias names a struct rather than a native type.

        Args:
            td: The alias.

        Returns:
            True for an alias of a struct, which has to follow its class.
        """
        return td.type_name not in type_map

    def get_descriptor(self, ftype: str, flen: int) -> str:
        if ftype in type_map.keys():
            dtype = desctype_map[ftype]
            # Scalar Field
            if flen == 0:
                return f":{dtype} = {dtype}()"
            elif flen == 1 and ftype == "char":
                # Note: char[1] will resolve to a scalar char field
                # We only allow char arrays with length greater than 1
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

        msg_src = sdf.src.name
        # repr() gives a literal for any text; Black lays the line out.
        type_def_line = f"type_def: ClassVar[str] = {repr(sdf.raw)}"

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
        msg_src = mdf.src.name
        # repr() gives a literal for any text; Black lays the line out.
        type_def_line = f"type_def: ClassVar[str] = {repr(mdf.raw)}"

        template = f"""\
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

        from pyrtma.__version__ import check_compiled_version
        from pyrtma.definitions import MessageDefinitions, build_message_definitions
        from typing import ClassVar

        from pyrtma.message_base import MessageBase, MessageMeta
        from pyrtma.message_data import MessageData
        from pyrtma.validators import Int8, Int16, Int32, Int64, Uint8, Uint16, Uint32, Uint64, Float, Double, Struct, IntArray, FloatArray, StructArray, Char, String, Byte, ByteArray

        """
        return dedent(s)

    def generate_context(self):
        s = """\
        _MESSAGE_DEFINITIONS: MessageDefinitions = build_message_definitions(__name__)


        def get_message_definitions() -> MessageDefinitions:
            return _MESSAGE_DEFINITIONS
        """
        return dedent(s)

    def generate_source(self) -> str:
        """Generate the definitions module's source, before formatting.

        Returns:
            The source.
        """
        parts: list[str] = []
        parts.append(self.generate_docstr())
        parts.append(self.generate_imports())
        parts.append("\n")

        # Version
        parts.append(f'COMPILED_PYRTMA_VERSION: str = "{__version__}"\n')
        parts.append("check_compiled_version(COMPILED_PYRTMA_VERSION)\n\n")

        parts.append("# Constants\n")
        obj: ConstantExpr | ConstantString | HID | MID | TypeAlias | SDF | MT | MDF
        for obj in self.parser.constants.values():
            parts.append(self.generate_constant(obj))
        parts.append("\n")

        parts.append("# String Constants\n")
        for obj in self.parser.string_constants.values():
            parts.append(self.generate_string_constant(obj))
        parts.append("\n")

        parts.append("# Type Aliases\n")
        for obj in self.parser.aliases.values():
            if not self.is_struct_alias(obj):
                parts.append(self.generate_type_alias(obj))
        parts.append("\n")

        parts.append("# Host IDs\n")
        for obj in self.parser.host_ids.values():
            parts.append(self.generate_host_id(obj))
        parts.append("\n")

        parts.append("# Module IDs\n")
        for obj in self.parser.module_ids.values():
            parts.append(self.generate_module_id(obj))
        parts.append("\n")

        parts.append("# Message Type IDs\n")
        for obj in self.parser.message_ids.values():
            parts.append(self.generate_msg_type_id(obj))
        parts.append("\n\n")

        parts.append("# Struct Definitions\n")
        for obj in self.parser.struct_defs.values():
            parts.append(self.generate_struct(obj))
            parts.append("\n\n")

        # Aliases of structs name their classes, so they follow them. Fields
        # use the struct's own name, so nothing before here needs them.
        struct_aliases = [
            a for a in self.parser.aliases.values() if self.is_struct_alias(a)
        ]
        if struct_aliases:
            parts.append("# Struct Aliases\n")
            for obj in struct_aliases:
                parts.append(self.generate_type_alias(obj))
            parts.append("\n\n")

        parts.append("# Message Definitions\n")
        for obj in self.parser.message_defs.values():
            parts.append(self.generate_msg_def(obj))
            parts.append("\n\n")

        parts.append("# User Context\n")
        parts.append(self.generate_context())
        return "".join(parts)

    def generate(self, out_filepath: pathlib.Path):
        """Write the definitions module and format it with Black.

        Args:
            out_filepath: The file to write.

        Raises:
            GeneratedSourceError: The generated source isn't valid Python.
                Nothing is written.
        """
        source = self.generate_source()
        try:
            compile(source, str(out_filepath), "exec")
        except SyntaxError as e:
            raise GeneratedSourceError(
                f"The Python generated for {out_filepath} is invalid, at line {e.lineno}: {(e.text or '').strip()} ({e.msg})"
            ) from e

        with open(out_filepath, mode="w", encoding="utf-8") as f:
            f.write(source)

        # The file is valid without formatting, so a failure here only warns.
        result = subprocess.run(
            [sys.executable, "-m", "black", "-q", str(out_filepath)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()
            self.parser.warning(
                f"Black couldn't format {out_filepath}; it is valid but unformatted: {detail}"
            )
