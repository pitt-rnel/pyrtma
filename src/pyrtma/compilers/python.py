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
from typing import Union


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

# Field type name to ctypes (in python file)
pytype_map = {
    "char": "str",
    "unsigned char": "int",
    "byte": "int",
    "int": "int",
    "signed int": "int",
    "unsigned int": "int",
    "unsigned": "int",
    "short": "int",
    "signed short": "int",
    "unsigned short": "int",
    "long": "int",
    "signed long": "int",
    "unsigned long": "int",
    "long long": "int",
    "signed long long": "int",
    "unsigned long long": "int",
    "float": "float",
    "double": "float",
    "uint8": "int",
    "uint16": "int",
    "uint32": "int",
    "uint64": "int",
    "int8": "int",
    "int16": "int",
    "int32": "int",
    "int64": "int",
}

DEFAULT_BLACK_LEN = 88  # preferred line length


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

    def generate_struct(self, sdf: SDF) -> str:
        f = []
        fnum = len(sdf.fields)
        fstr = "["
        if fnum == 0:
            fstr += "]"
        else:
            if fnum > 2:
                tab = "    "
                fstr += "\n"
            else:
                tab = ""
            for i, field in enumerate(sdf.fields, start=1):
                flen = field.length
                nl = ",\n" if fnum > 2 else ", " if i < fnum else ""

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
            if fnum > 2:
                fstr += f"{tab * 3}]"
            else:
                fstr += "]"

        template = f"""\
        class {sdf.name}(ctypes.Structure):
            _fields_ = {fstr}
        """
        return dedent(template)

    def generate_struct_stub(self, sdf: SDF) -> str:
        f = []
        fnum = len(sdf.fields)
        fstr = ""
        # if fnum == 0:
        #    fstr += "]"
        # else:
        tab = "    "
        fstr += "\n"
        for i, field in enumerate(sdf.fields, start=1):
            flen = field.length
            nl = "\n"
            if field.type_name in type_map.keys():
                if flen and field.type_name != "char":
                    ftype = f"ctypes.Array[{type_map[field.type_name]}]"
                else:
                    ftype = pytype_map[field.type_name]
            elif field.type_name in self.parser.message_defs.keys():
                ftype = f"MDF_{field.type_name}"
            elif field.type_name in self.parser.struct_defs.keys():
                ftype = f"{field.type_name}"
            elif field.type_name in self.parser.aliases.keys():
                type_name = self.parser.aliases[field.type_name].type_name
                if type_name in type_map.keys():
                    if flen and type_name != "char":
                        ftype = f"ctypes.Array[{type_map[type_name]}]"
                    else:
                        ftype = pytype_map[type_name]
                else:
                    ftype = f"{field.type_name}"
            else:
                raise RuntimeError(f"Unknown field name {field.name} in {sdf.name}")
            comment = f" # length: {flen}" if flen else ""
            f.append(f"{tab *3}{field.name}: {ftype}{comment}{nl}")
        fstr += "".join(f)
        # fstr += f"\n{tab * 3}]"
        if not fstr:
            fstr = " ..."

        template = f"""\
        class {sdf.name}(ctypes.Structure):{fstr}
        """
        return dedent(template)

    def generate_msg_def(self, mdf: MDF) -> str:
        f = []
        fnum = len(mdf.fields)
        fstr = "["
        if fnum == 0:
            fstr += "]"
        else:
            if fnum > 2:
                tab = "    "
                fstr += "\n"
            else:
                tab = ""
            for i, field in enumerate(mdf.fields, start=1):
                flen = field.length
                nl = ",\n" if fnum > 2 else ", " if i < fnum else ""

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
            if fnum > 2:
                fstr += f"{tab * 3}]"
            else:
                fstr += "]"

        msg_id = mdf.type_id
        msg_src = mdf.src.as_posix()
        type_def_str = repr(mdf.raw)
        tab = "    "
        type_def_rhs = 'type_def: ClassVar[str] = "'
        type_def_end = '"'
        type_def_line = f"{type_def_rhs}{type_def_str}{type_def_end}"
        type_def_line_len = len(tab) + len(type_def_line)
        if type_def_line_len > DEFAULT_BLACK_LEN:
            type_def_rhs = f'type_def: ClassVar[\n{tab *4}str\n{tab *3}] = "'
            type_def_line = f"{type_def_rhs}{type_def_str}{type_def_end}"

        template = f"""\
        @pyrtma.message_def
        class MDF_{mdf.name}(pyrtma.MessageData):
            _fields_ = {fstr}
            type_id: ClassVar[int] = {msg_id}
            type_name: ClassVar[str] = \"{mdf.name}\"
            type_hash: ClassVar[int] = 0x{mdf.hash[:8].upper()}
            type_source: ClassVar[str] = \"{msg_src}\"
            {type_def_line}
        """
        return dedent(template)

    def generate_msg_stub(self, mdf: MDF) -> str:
        f = []
        fnum = len(mdf.fields)
        fstr = ""
        # if fnum == 0:
        #    fstr += "]"
        # else:
        tab = "    "
        if fnum:
            fstr += "\n"
        for i, field in enumerate(mdf.fields, start=1):
            flen = field.length
            nl = "\n"
            if field.type_name in type_map.keys():
                if flen and field.type_name != "char":
                    ftype = f"ctypes.Array[{type_map[field.type_name]}]"
                else:
                    ftype = pytype_map[field.type_name]
            elif field.type_name in self.parser.message_defs.keys():
                ftype = f"MDF_{field.type_name}"
            elif field.type_name in self.parser.struct_defs.keys():
                ftype = f"{field.type_name}"
            elif field.type_name in self.parser.aliases.keys():
                type_name = self.parser.aliases[field.type_name].type_name
                if type_name in type_map.keys():
                    if flen and type_name != "char":
                        ftype = f"ctypes.Array[{type_map[type_name]}]"
                    else:
                        ftype = pytype_map[type_name]
                else:
                    ftype = f"{field.type_name}"
            else:
                raise RuntimeError(f"Unknown field name {field.name} in {mdf.name}")
            comment = f"  # length: {flen}" if flen else ""
            f.append(f"{tab *3}{field.name}: {ftype}{comment}{nl}")
        fstr += "".join(f)
        # fstr += f"\n{tab * 3}]"
        if not fstr:
            fstr = " ..."

        template = f"""\
        class MDF_{mdf.name}(pyrtma.MessageData):{fstr}
        """
        return dedent(template)

    def generate_imports(self) -> str:
        s = """\
        import ctypes
        import pyrtma
        from typing import ClassVar
        """
        return dedent(s)

    def generate_type_info(self) -> str:
        tab = "    "
        s = "# Collect all info into one object\n"
        s += "class _constants:\n"
        obj: Union[ConstantExpr, ConstantString, HID, MID, TypeAlias, SDF, MT, MDF]
        for obj in self.parser.constants.values():
            s += f"    {obj.name} = {obj.value}\n"
        for obj in self.parser.string_constants.values():
            s += f"    {obj.name} = {obj.value}\n"
        s += "\n" * 2

        s += "class _HID:\n"
        for obj in self.parser.host_ids.values():
            s += f"{tab}{obj.name} = {obj.value}\n"
        s += "\n" * 2

        s += "class _MID:\n"
        for obj in self.parser.module_ids.values():
            s += f"{tab}{obj.name} = {obj.value}\n"
        s += "\n" * 2

        s += "class _aliases:\n"
        for obj in self.parser.aliases.values():
            s += f"{tab}{obj.name} = {obj.name}\n"
        s += "\n" * 2

        s += "class _SDF:\n"
        for obj in self.parser.struct_defs.values():
            s += f"{tab}{obj.name} = {obj.name}\n"
        s += "\n" * 2

        s += "class _MT:\n"
        for obj in self.parser.message_ids.values():
            s += f"{tab}{obj.name} = {obj.value}\n"
        s += "\n" * 2

        s += "class _MDF:\n"
        for obj in self.parser.message_defs.values():
            mdf_txt = f"{tab}{obj.name} = MDF_{obj.name}\n"
            if len(mdf_txt) > DEFAULT_BLACK_LEN:
                mdf_txt = f"{tab}{obj.name} = (\n{tab*2}MDF_{obj.name}\n{tab})\n"
            s += mdf_txt
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

        s += "RTMA: _RTMA = _RTMA()"

        return dedent(s)

    def generate(self, out_filepath: pathlib.Path):
        with open(out_filepath, mode="w") as f:
            f.write(self.generate_imports())
            f.write("\n")

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

            f.write(self.generate_type_info())
            f.write("\n")

    def generate_stub(self, out_filepath: pathlib.Path):
        with open(out_filepath, mode="w") as f:
            f.write(self.generate_imports())
            f.write("\n")

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
            f.write("\n")

            f.write("# Struct Definitions\n")
            new_line_flag = False
            for obj in self.parser.struct_defs.values():
                struct_txt = self.generate_struct_stub(obj)
                if struct_txt[-4:] != "...\n" and new_line_flag:
                    f.write("\n")
                f.write(struct_txt)
                new_line_flag = (
                    struct_txt[-4:] == "...\n"
                )  # if new line may be needed for next class

            f.write("# Message Definitions\n")
            for obj in self.parser.message_defs.values():
                mdf_text = self.generate_msg_stub(obj)
                if mdf_text[-4:] != "...\n" and new_line_flag:
                    f.write("\n")
                f.write(mdf_text)
                new_line_flag = (
                    mdf_text[-4:] == "...\n"
                )  # if new line may be needed for next class
