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


# Field type name to ctypes
type_map = {
    "char": "ctypes.c_char",
    "unsigned char": "ctypes.c_ubyte",
    "byte": "ctypes.c_ubyte",
    "int": "ctypes.c_int",
    "signed int": "ctypes.c_int",
    "unsigned int": "ctypes.c_uint",
    "unsigned": "ctypes.c_uint",
    "short": "ctypes.c_short",
    "signed short": "ctypes.c_short",
    "unsigned short": "ctypes.c_ushort",
    "long": "ctypes.c_int32",
    "signed long": "ctypes.c_int32",
    "unsigned long": "ctypes.c_uint32",
    "long long": "ctypes.c_longlong",
    "signed long long": "ctypes.c_longlong",
    "unsigned long long": "ctypes.c_ulonglong",
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
}


class PyDefCompiler:
    def __init__(self, parser: Parser, debug: bool = False):
        self.debug = debug
        self.parser = parser

    def generate_constant(self, c: ConstantExpr):
        return f"{c.name} = {c.value}\n"

    def generate_string_constant(self, c: ConstantString):
        return f"{c.name} = {c.value}\n"

    def generate_msg_type_id(self, mt: MT):
        return f"MT_{mt.name} = {mt.value}\n"

    def generate_module_id(self, mid: MID):
        return f"MID_{mid.name} = {mid.value}\n"

    def generate_host_id(self, hid: HID):
        return f"{hid.name} = {hid.value}\n"

    def generate_type_alias(self, td: TypeAlias):
        ftype = type_map.get(td.type_name)
        if ftype:
            return f"{td.name} = {ftype}\n"
        else:
            return f"{td.name} = {td.type_name}\n"

    def generate_struct(self, sdf: SDF):
        f = []
        fnum = len(sdf.fields)
        fstr = "["
        if fnum == 0:
            fstr += "]"
        else:
            tab = "    "
            fstr += "\n"
            for i, field in enumerate(sdf.fields, start=1):
                flen = field.length
                nl = ",\n" if i < fnum else ""

                if field.type_name in type_map.keys():
                    ftype = type_map[field.type_name]
                elif field.type_name in self.parser.message_defs.keys():
                    ftype = f"MDF_{field.type_name}"
                elif field.type_name in self.parser.struct_defs.keys():
                    ftype = f"{field.type_name}"
                elif field.type_name in self.parser.aliases.keys():
                    ftype = f"{field.type_name}"
                else:
                    raise RuntimeError(f"Unknown field name {field.name} in {sdf.name}")

                f.append(
                    f"{tab *4}(\"{field.name}\", {ftype}{' * ' + str(flen) if flen else ''}){nl}"
                )

            fstr += "".join(f)
            fstr += f"\n{tab * 3}]"

        template = f"""\
        class {sdf.name}(ctypes.Structure):
            _fields_ = {fstr}
        """
        return dedent(template)

    def generate_msg_def(self, mdf: MDF):
        f = []
        fnum = len(mdf.fields)
        fstr = "["
        if fnum == 0:
            fstr += "]"
        else:
            tab = "    "
            fstr += "\n"
            for i, field in enumerate(mdf.fields, start=1):
                flen = field.length
                nl = ",\n" if i < fnum else ""

                if field.type_name in type_map.keys():
                    ftype = type_map[field.type_name]
                elif field.type_name in self.parser.message_defs.keys():
                    ftype = f"MDF_{field.type_name}"
                elif field.type_name in self.parser.struct_defs.keys():
                    ftype = f"{field.type_name}"
                elif field.type_name in self.parser.aliases.keys():
                    ftype = f"{field.type_name}"
                else:
                    raise RuntimeError(f"Unknown field name {field.name} in {mdf.name}")

                f.append(
                    f"{tab *4}(\"{field.name}\", {ftype}{' * ' + str(flen) if flen else ''}){nl}"
                )

            fstr += "".join(f)
            fstr += f"\n{tab * 3}]"

        msg_id = mdf.type_id
        msg_src = str(mdf.src.absolute()).replace("\\", "\\\\")
        template = f"""\
        @pyrtma.message_def
        class MDF_{mdf.name}(pyrtma.MessageData):
            _fields_ = {fstr}
            type_id = {msg_id}
            type_name = \"{mdf.name}\"
            type_hash = 0x{mdf.hash[:8]}
            type_source = \"{msg_src}\"
            type_def = \"{repr(mdf.raw)}\"
        """
        return dedent(template)

    def generate_imports(self):
        s = """\
        import ctypes
        import pyrtma
        """
        return dedent(s)

    def generate_type_info(self) -> str:
        s = "# Collect all info into one object\n"
        s += "class _constants:\n"
        for obj in self.parser.constants.values():
            s += f"    {obj.name} = {obj.value}\n"
        for obj in self.parser.string_constants.values():
            s += f"    {obj.name} = {obj.value}\n"
        s += "\n" * 2

        s += "class _HID:\n"
        for obj in self.parser.host_ids.values():
            s += f"    {obj.name} = {obj.value}\n"
        s += "\n" * 2

        s += "class _MID:\n"
        for obj in self.parser.module_ids.values():
            s += f"    {obj.name} = {obj.value}\n"
        s += "\n" * 2

        s += "class _aliases:\n"
        for obj in self.parser.aliases.values():
            s += f"    {obj.name} = {obj.name}\n"
        s += "\n" * 2

        s += "class _SDF:\n"
        for obj in self.parser.struct_defs.values():
            s += f"    {obj.name} = {obj.name}\n"
        s += "\n" * 2

        s += "class _MT:\n"
        for obj in self.parser.message_ids.values():
            s += f"    {obj.name} = {obj.value}\n"
        s += "\n" * 2

        s += "class _MDF:\n"
        for obj in self.parser.message_defs.values():
            s += f"    {obj.name} = MDF_{obj.name}\n"
        s += "\n" * 2

        s += "class _RTMA:\n"
        s += "    constants = _constants\n"
        s += "    HID = _HID\n"
        s += "    MID = _MID\n"
        s += "    aliases = _aliases\n"
        s += "    MT = _MT\n"
        s += "    MDF = _MDF\n"
        s += "    SDF = _SDF\n"
        s += "\n" * 2

        s += "RTMA = _RTMA()"

        return dedent(s)

    def generate(self, out_filepath: pathlib.Path):
        with open(out_filepath, mode="w") as f:
            f.write(self.generate_imports())
            f.write("\n")

            f.write("# Constants\n")
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
                f.write("\n\n")
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

            f.write(self.generate_type_info())
