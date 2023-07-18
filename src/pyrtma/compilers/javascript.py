import pathlib

from typing import Union
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

# Native C types that are supported
type_map = {
    "char": '""',
    "unsigned char": 0,
    "byte": 0,
    "int": 0,
    "signed int": 0,
    "unsigned int": 0,
    "unsigned": 0,
    "short": 0,
    "signed short": 0,
    "unsigned short": 0,
    "long": 0,
    "signed long": 0,
    "unsigned long": 0,
    "long long": 0,
    "signed long long": 0,
    "unsigned long long": 0,
    "float": 0,
    "double": 0,
    "uint8": 0,
    "uint16": 0,
    "uint32": 0,
    "uint64": 0,
    "int8": 0,
    "int16": 0,
    "int32": 0,
    "int64": 0,
}


def pad(indent: int) -> str:
    return indent * "\t"


class JSDefCompiler:
    def __init__(self, parser: Parser, debug: bool = False):
        self.debug = debug
        self.parser = parser

    def generate_constant(self, c: ConstantExpr):
        return f"RTMA.constants.{c.name} = {c.value};\n"

    def generate_string_constant(self, c: ConstantString):
        return f"RTMA.constants.{c.name} = {c.value};\n"

    def generate_prop(self, name: str, value: str):
        return f"{name}: {value}"

    def generate_msg_type_id(self, mt: MT) -> str:
        return f"RTMA.MT.{mt.name} = {mt.value};\n"

    def generate_host_id(self, hid: HID) -> str:
        return f"RTMA.HID.{hid.name} = {hid.value};\n"

    def generate_module_id(self, mid: MID) -> str:
        return f"RTMA.MID.{mid.name} = {mid.value};\n"

    def generate_hash_id(self, mdf: Union[MDF, SDF]) -> str:
        return f'RTMA.HASH.{mdf.name} = "{mdf.hash[:8]}";\n'

    def generate_type_alias(self, td: TypeAlias) -> str:
        if td.type_name in type_map.keys():
            clean_name = td.type_name.replace(" ", "_")
            return f"RTMA.aliases.{td.name} = type_map.{clean_name}();\n"

        if td.type_name in self.parser.aliases.keys():
            return f"RTMA.aliases.{td.name} = RTMA.aliases.{td.type_name};\n"

        if td.type_name in self.parser.struct_defs.keys():
            return f"RTMA.SDF.{td.name} = RTMA.SDF.{td.type_name};\n"

        if td.type_name in self.parser.message_defs.keys():
            return f"RTMA.MDF.{td.name} = RTMA.MDF.{td.type_name};\n"

        raise RuntimeError(f"No type found for alias: {td.name}")

    def generate_obj(self, struct: Union[SDF, MDF]) -> str:
        if isinstance(struct, MDF):
            top_field = "MDF"
        elif isinstance(struct, SDF):
            top_field = "SDF"

        tabs = "\t" * 2
        num_fields = len(struct.fields)

        if num_fields == 0:
            return f"RTMA.{top_field}.{struct.name} = () => {{ return {{}} }};"

        s = f"RTMA.{top_field}.{struct.name} = () => {{\n\treturn {{\n"

        for n, field in enumerate(struct.fields, start=1):
            s += tabs
            if field.type_name in type_map.keys():
                clean_name = field.type_name.replace(" ", "_")
                ftype = f"type_map.{clean_name}"
            elif field.type_name in self.parser.message_defs.keys():
                ftype = f"RTMA.MDF.{field.type_name}"
            elif field.type_name in self.parser.struct_defs.keys():
                ftype = f"RTMA.SDF.{field.type_name}"
            elif field.type_name in self.parser.aliases.keys():
                ftype = f"RTMA.aliases.{field.type_name}"
            else:
                raise RuntimeError(f"Unknown field name {field.name} in {struct.name}")

            if field.length is not None:
                s += f"{field.name}: Array({field.length}).fill({ftype}())"
            else:
                s += f"{field.name}: {ftype}()"

            if n < num_fields:
                s += ",\n"
            else:
                s += "\n"

        s += "\t}\n"
        s += "};"

        return s

    def generate(self, out_filepath: pathlib.Path):
        with open(out_filepath, mode="w") as f:
            # Exports
            f.write("export { RTMA } ;\n\n")

            # Generate Type Map Helper
            f.write("// Type Map Default Values\n")
            f.write("const type_map = {};\n")
            for name, value in type_map.items():
                name = name.replace(" ", "_")
                f.write(f"type_map.{name} = () => {value};\n")
            f.write("\n")

            # Top-Level RTMA object
            f.write("// Top-Level RTMA object\n")
            f.write("const RTMA = {};\n\n")

            # RTMA.constants
            f.write("// Constants\n")
            f.write("RTMA.constants =  {};\n")
            for obj in self.parser.constants.values():
                f.write(self.generate_constant(obj))
            f.write("\n")

            f.write("// String Constants\n")
            for obj in self.parser.string_constants.values():
                f.write(self.generate_string_constant(obj))
            f.write("\n")

            # RTMA.typedefs
            f.write("// Type Aliases\n")
            f.write("RTMA.aliases =  {};\n\n")
            for obj in self.parser.aliases.values():
                f.write(self.generate_type_alias(obj))
            f.write("\n")

            # RTMA.HID
            f.write("// Host IDs\n")
            f.write("RTMA.HID =  {};\n\n")
            for obj in self.parser.host_ids.values():
                f.write(self.generate_host_id(obj))
            f.write("\n")

            # RTMA.MID
            f.write("// Module IDs\n")
            f.write("RTMA.MID =  {};\n\n")
            for obj in self.parser.module_ids.values():
                f.write(self.generate_module_id(obj))
            f.write("\n")

            # RTMA.MT
            f.write("// Message Type IDs\n")
            f.write("RTMA.MT = {};\n\n")
            for obj in self.parser.message_ids.values():
                f.write(self.generate_msg_type_id(obj))
            f.write("\n")

            # RTMA.SDF
            f.write("// Struct Definitions\n")
            f.write("RTMA.SDF = {};\n\n")
            for obj in self.parser.struct_defs.values():
                f.write(self.generate_obj(obj))
                f.write("\n\n")

            # RTMA.MDF
            f.write("// Message Definitions\n")
            f.write("RTMA.MDF = {};\n\n")
            for obj in self.parser.message_defs.values():
                f.write(self.generate_obj(obj))
                f.write("\n\n")

            # RTMA.MDF
            f.write("// Message Definition Hashes\n")
            f.write("RTMA.HASH = {};\n\n")
            for obj in self.parser.message_defs.values():
                f.write(self.generate_hash_id(obj))
