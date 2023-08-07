import pathlib

from textwrap import dedent
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

tab = "    "

# Native C types that are supported
type_map = {
    "char": "char",
    "unsigned char": "unsigned char",
    "byte": "uint8_t",
    "int": "int32_t",
    "signed int": "int32_t",
    "unsigned int": "uint32_t",
    "unsigned": "uint32_t",
    "short": "int16_t",
    "signed short": "int16_t",
    "unsigned short": "uint16_t",
    "long": "int32_t",
    "signed long": "int32_t",
    "unsigned long": "uint32_t",
    "long long": "int64_t",
    "signed long long": "int64_t",
    "unsigned long long": "uint64_t",
    "float": "float",
    "double": "double",
    "uint8": "uint8_t",
    "uint16": "uint16_t",
    "uint32": "uint32_t",
    "uint64": "uint64_t",
    "int8": "int8_t",
    "int16": "int16_t",
    "int32": "int32_t",
    "int64": "int64_t",
}


def pad(indent: int) -> str:
    return indent * "\t"


class CDefCompiler:
    def __init__(self, parser: Parser, filename: str, debug: bool = False):
        self.debug = debug
        self.parser = parser
        self.filename = filename

    def generate_constant(self, c: ConstantExpr):
        return f"#define {c.name:<48}{c.value}\n"

    def generate_string_constant(self, c: ConstantString):
        return f"#define {c.name:<48}{c.value}\n"

    def generate_msg_type_id(self, mt: MT) -> str:
        return f"#define MT_{mt.name:<48}{mt.value}\n"

    def generate_host_id(self, hid: HID) -> str:
        return f"#define HID_{hid.name:<48}{hid.value}\n"

    def generate_module_id(self, mid: MID) -> str:
        return f"#define MID_{mid.name:<48}{mid.value}\n"

    def generate_hash_id(self, mdf: Union[MDF, SDF]) -> str:
        return f'#define HASH_{mdf.name:<48}"{mdf.hash[:8]}"\n'

    def generate_type_alias(self, td: TypeAlias) -> str:
        if td.type_name in type_map.keys():
            return f"typedef {td.type_name} {td.name};\n"

        if td.type_name in self.parser.aliases.keys():
            return f"typedef {td.type_name} {td.name};\n"

        if td.type_name in self.parser.struct_defs.keys():
            return f"typedef {td.type_name} {td.name};\n"

        if td.type_name in self.parser.message_defs.keys():
            return f"typedef MDF_{td.type_name} MDF_{td.name};\n"

        raise RuntimeError(f"No type found for alias: {td.name}")

    def generate_struct(self, struct: Union[SDF, MDF]) -> str:
        if isinstance(struct, MDF):
            prefix = "MDF_"
        elif isinstance(struct, SDF):
            prefix = ""

        if len(struct.fields) == 0:
            return f"// {struct.name} -> Signal"

        f = ["typedef struct {"]
        tabs = f"{tab}" * 1
        for field in struct.fields:
            if field.type_name in type_map.keys():
                ftype = f"{field.type_name}"
            elif field.type_name in self.parser.message_defs.keys():
                ftype = f"MDF_{field.type_name}"
            elif field.type_name in self.parser.struct_defs.keys():
                ftype = f"{field.type_name}"
            elif field.type_name in self.parser.aliases.keys():
                ftype = f"{field.type_name}"
            else:
                raise RuntimeError(f"Unknown field name {field.name} in {struct.name}")

            if field.length is None:
                f.append(f"{tabs}{ftype} {field.name};")
            else:
                f.append(f"{tabs}{ftype} {field.name}[{field.length}];")

        f.append(f"}} {prefix}{struct.name};\n")

        return "\n".join(f)

    def generate_includes(self) -> str:
        filename = self.filename.replace(" ", "_").upper()
        s = f"""\
            #ifndef _{filename}_
            #define _{filename}_

            // Sized integer types
            #include <stdint.h>

            // Including for historical reasons for now.
            #ifndef _RTMA_TYPES_H_
            #include "../../rtma/include/RTMA_types.h"
            #endif //_RTMA_TYPES_H_

            """

        return dedent(s)

    def generate_type_info(self) -> str:
        s = ""

        s += "typedef struct {\n"
        for obj in self.parser.constants.values():
            if type(obj.value) is float:
                ftype = "double"
            else:
                ftype = "int"

            s += f'#pragma push_macro("{obj.name}")\n'
            s += f"#undef {obj.name}\n"
            s += f"    {ftype} {obj.name};\n"
            s += f'#pragma pop_macro("{obj.name}")\n'
            s += "\n"

        for obj in self.parser.string_constants.values():
            s += f'#pragma push_macro("{obj.name}")\n'
            s += f"#undef {obj.name}\n"
            s += f"    const char* {obj.name};\n"
            s += f'#pragma pop_macro("{obj.name}")\n'
            s += "\n"

        s += "} ConstantInfo;\n"
        s += "\n" * 2

        s += "typedef struct {\n"
        for obj in self.parser.host_ids.values():
            s += f"    HOST_ID {obj.name};\n"
        s += "} HostIdInfo;\n"

        s += "\n" * 2

        s += "typedef struct {\n"
        for obj in self.parser.module_ids.values():
            s += f"    MODULE_ID {obj.name};\n"
        s += "} ModuleIdInfo;\n"

        s += "\n" * 2

        s += "typedef struct {\n"
        for obj in self.parser.message_ids.values():
            s += f"    MSG_TYPE {obj.name};\n"
        s += "} MsgIdInfo;\n"

        s += "\n" * 2

        s += "typedef struct {\n"
        for obj in self.parser.message_defs.values():
            s += f"    int {obj.name};\n"
        s += "} MsgHashInfo;\n"

        s += "\n" * 2

        s += "typedef struct {\n"
        s += "    ConstantInfo constants;\n"
        s += "    HostIdInfo HID;\n"
        s += "    ModuleIdInfo MID;\n"
        s += "    MsgIdInfo MT;\n"
        s += "    MsgHashInfo HASH;\n"
        s += "} RTMAInfo;\n"

        s += "\n" * 2

        return dedent(s)

    def generate_rtma_info_getter(self) -> str:
        s = "const RTMAInfo get_rtma_info() {\n"
        s += "    static RTMAInfo RTMA;\n"

        for obj in self.parser.constants.values():
            s += f'#pragma push_macro("{obj.name}")\n'
            s += f"#undef {obj.name}\n"
            s += f"{tab}RTMA.constants.{obj.name} = {obj.value};\n"
            s += f'#pragma pop_macro("{obj.name}")\n'
            s += "\n"

        for obj in self.parser.string_constants.values():
            s += f'#pragma push_macro("{obj.name}")\n'
            s += f"#undef {obj.name}\n"
            s += f"{tab}RTMA.constants.{obj.name} = {obj.value};\n"
            s += f'#pragma pop_macro("{obj.name}")\n'
            s += "\n"

        for obj in self.parser.host_ids.values():
            s += f"{tab}RTMA.HID.{obj.name} = {obj.value};\n"

        s += "\n" * 2

        for obj in self.parser.module_ids.values():
            s += f"{tab}RTMA.MID.{obj.name} = {obj.value};\n"

        s += "\n" * 2

        for obj in self.parser.message_ids.values():
            s += f"{tab}RTMA.MT.{obj.name} = {obj.value};\n"

        s += "\n" * 2

        for obj in self.parser.message_defs.values():
            s += f"{tab}RTMA.HASH.{obj.name} = 0x{obj.hash[:8]};\n"

        s += "\n"
        s += "    return RTMA;\n"
        s += "};\n"

        return s

    def generate_close_guard(self) -> str:
        filename = self.filename.replace(" ", "_").upper()
        return f"#endif // _{filename}_"

    def generate(self, out_filepath: pathlib.Path):
        with open(out_filepath, mode="w") as f:
            # Includes
            f.write(self.generate_includes())

            # Constants
            f.write("// Constants\n")
            for obj in self.parser.constants.values():
                f.write(self.generate_constant(obj))
            f.write("\n")

            # String Constants
            f.write("// String Constants\n")
            for obj in self.parser.string_constants.values():
                f.write(self.generate_string_constant(obj))
            f.write("\n")

            # Type Aliases
            f.write("// Type Aliases\n")
            for obj in self.parser.aliases.values():
                f.write(self.generate_type_alias(obj))
            f.write("\n")

            # Host IDs
            f.write("// Host IDs\n")
            for obj in self.parser.host_ids.values():
                f.write(self.generate_host_id(obj))
            f.write("\n")

            # Module IDs
            f.write("// Module IDs\n")
            for obj in self.parser.module_ids.values():
                f.write(self.generate_module_id(obj))
            f.write("\n")

            # Message Type IDs
            f.write("// Message Type IDs\n")
            for obj in self.parser.message_ids.values():
                f.write(self.generate_msg_type_id(obj))
            f.write("\n")

            # Structure Types
            f.write("// Struct Definitions\n")
            for obj in self.parser.struct_defs.values():
                f.write(self.generate_struct(obj))
                f.write("\n\n")

            # Message Definitions
            f.write("// Message Definitions\n")
            for obj in self.parser.message_defs.values():
                f.write(self.generate_struct(obj))
                f.write("\n\n")

            # Message Definition Hashes
            f.write("// Message Definition Hashes\n")
            for obj in self.parser.message_defs.values():
                f.write(self.generate_hash_id(obj))
            f.write("\n")

            # Message Definition Type Info (Future Use)
            f.write("// Type Information\n")
            f.write(self.generate_type_info())
            f.write("\n")

            f.write(self.generate_rtma_info_getter())
            f.write("\n")

            # Close header guard
            f.write(self.generate_close_guard())
