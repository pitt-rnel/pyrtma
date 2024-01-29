import pathlib

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
from pyrtma.__version__ import __version__

from typing import Any, Union
from textwrap import dedent

# Field type name to matlab types
type_map = {
    "char": "int8",
    "unsigned char": "uint8",
    "byte": "uint8",
    "int": "int32",
    "signed int": "int32",
    "unsigned int": "uint32",
    "unsigned": "uint32",
    "short": "int16",
    "signed short": "int16",
    "unsigned short": "uint16",
    "long": "int32",
    "signed long": "int32",
    "unsigned long": "uint32",
    "long long": "int64",
    "signed long long": "int64",
    "unsigned long long": "uint64",
    "float": "single",
    "double": "double",
    "uint8": "uint8",
    "uint16": "uint16",
    "uint32": "uint32",
    "uint64": "uint64",
    "int8": "int8",
    "int16": "int16",
    "int32": "int32",
    "int64": "int64",
}


class MatlabDefCompiler:
    def __init__(self, parser: Parser, debug: bool = False):
        self.debug = debug
        self.parser = parser
        self.struct_name = "RTMA"

    def generate_fcn_header(self, fcn_name: str) -> str:
        return f"function {self.struct_name} = {fcn_name}()\n\n"

    def initialize_struct(self) -> str:
        s = f"""\
            {self.struct_name} = struct();
            {self.struct_name}.COMPILED_PYRTMA_VERSION = '{__version__}';
            {self.struct_name}.HID = [];
            {self.struct_name}.MID = [];
            {self.struct_name}.MT = [];
            {self.struct_name}.MDF = [];
            {self.struct_name}.MESSAGE_HEADER = [];
            {self.struct_name}.MTN_by_MT = [];
            {self.struct_name}.MDF_by_MT = [];
            {self.struct_name}.mex_opcode = [];
            {self.struct_name}.defines = [];
            {self.struct_name}.typedefs = [];
            {self.struct_name}.hash = [];
        """

        return dedent(s)

    @staticmethod
    def generate_fcn_close() -> str:
        return "end\n"

    @staticmethod
    def sanitize_name(name: str) -> str:
        # strip leading characters that are invalid to start
        #  a fieldname (only letters allowed)
        name = name.lstrip("_0123456789")

        # matlab fieldnames allow alphanum and _ after starting characters
        for c in name:
            if not c.isalnum() and c != "_":
                name = name.replace(c, "")
        return name

    def generate_field(self, top_field: str, name: str, value: Any) -> str:
        name = name.replace(f"{top_field}_", "", 1)  # strip top_field from fieldname
        name = self.sanitize_name(name)
        return f"{self.struct_name}.{top_field}.{name} = {value};\n"

    def generate_constant(self, c: Union[ConstantExpr, HID, MID, MT]) -> str:
        if isinstance(c, ConstantExpr):
            prefix = ""
        elif isinstance(c, HID):
            prefix = "HID_"
        elif isinstance(c, MID):
            prefix = "MID_"
        elif isinstance(c, MT):
            prefix = "MT_"
        return self.generate_field(
            "defines", f"{prefix}{self.sanitize_name(c.name)}", c.value
        )

    def generate_constant_string(self, c: ConstantString):
        return self.generate_field("defines", self.sanitize_name(c.name), c.value)

    def generate_host_id(self, hid: HID) -> str:
        return self.generate_field("HID", self.sanitize_name(hid.name), hid.value)

    def generate_module_id(self, mid: MID) -> str:
        return self.generate_field("MID", self.sanitize_name(mid.name), mid.value)

    def generate_msg_type_id(self, mt: MT) -> str:
        return self.generate_field("MT", self.sanitize_name(mt.name), mt.value)

    def generate_type_alias(self, td: TypeAlias) -> str:
        name = self.sanitize_name(td.name)
        type_name = self.sanitize_name(td.type_name)
        if td.type_name in type_map.keys():
            s = type_map[td.type_name]
            return f"{self.struct_name}.typedefs.{name} = {s}(0);\n"

        if td.type_name in self.parser.aliases.keys():
            return f"{self.struct_name}.typedefs.{name} = RTMA.typedefs.{type_name};\n"

        if td.type_name in self.parser.struct_defs.keys():
            return f"{self.struct_name}.typedefs.{name} = RTMA.typedefs.{type_name};\n"

        if td.type_name in self.parser.message_defs.keys():
            return f"{self.struct_name}.MDF.{name} = RTMA.MDF.{type_name};\n"

        raise RuntimeError(f"No type found for alias: {name}")

    def generate_struct(
        self, struct: Union[SDF, MDF], top_field: str = "typedefs"
    ) -> str:
        f = []

        name = self.sanitize_name(struct.name)

        if isinstance(struct, MDF) and len(struct.fields) == 0:
            f.append(f"% {name} (Signal)")
        else:
            f.append(f"% {name}")

        f.append(f"{self.struct_name}.{top_field}.{name} = struct();")

        for field in struct.fields:
            if field.type_name in type_map.keys():
                s = type_map[field.type_name]
                ftype = f"{s}(0)"
            elif field.type_name in self.parser.message_defs.keys():
                ftype = f"{self.struct_name}.MDF.{field.type_name}"
            elif field.type_name in self.parser.struct_defs.keys():
                ftype = f"{self.struct_name}.typedefs.{field.type_name}"
            elif field.type_name in self.parser.aliases.keys():
                ftype = f"{self.struct_name}.typedefs.{field.type_name}"
            else:
                raise RuntimeError(f"Unknown field name {field.name} in {name}")

            if field.length is not None:
                f.append(
                    f"{self.struct_name}.{top_field}.{name}.{field.name} = repmat({ftype}, 1, {field.length});"
                )
            else:
                f.append(
                    f"{self.struct_name}.{top_field}.{name}.{field.name} = {ftype};"
                )

        return "\n".join(f)

    def generate_msg_def(self, mdf: MDF) -> str:
        return self.generate_struct(mdf, "MDF")

    def generate_message_header(self) -> str:
        return f"{self.struct_name}.MESSAGE_HEADER = {self.struct_name}.typedefs.RTMA_MSG_HEADER;\n"

    def generate_hash_id(self, mdf: MDF) -> str:
        return f'{self.struct_name}.hash.{self.sanitize_name(mdf.name)} = "{mdf.hash[:8]}";\n'

    def generate_mex_opcodes(self) -> str:
        # these are copied from MatlabRTMA.h
        prefix = f"{self.struct_name}.mex_opcode"
        op = f"""\
        {prefix}.CONNECT_TO_MMM = 1;
        {prefix}.DISCONNECT_FROM_MMM = 2;
        {prefix}.SUBSCRIBE = 3;
        {prefix}.UNSUBSCRIBE = 4;
        {prefix}.SEND_MESSAGE = 5;
        {prefix}.SEND_SIGNAL = 6;
        {prefix}.READ_MESSAGE_HDR = 7;
        {prefix}.READ_MESSAGE_DATA = 8;
        {prefix}.SET_TIMER = 9;
        {prefix}.SEND_MODULE_READY = 10;
        {prefix}.CANCEL_TIMER = 11;
        {prefix}.PAUSE_SUBSCRIPTION = 12;
        {prefix}.RESUME_SUBSCRIPTION = 13;
        {prefix}.READ_MESSAGE_DD = 14;
        {prefix}.SEND_MESSAGE_DD = 15;
        {prefix}.GET_TIME = 16;
        {prefix}.GET_MODULE_ID = 17;
        """
        return dedent(op)

    def generate_by_MT(self) -> str:
        # append matlab code to generate _by_MT cell arrays from other fields
        prefix = self.struct_name
        s = f"""\n
        % add _by_MT arrays
        mtns = fieldnames({prefix}.MT);
        for idx = 1:length(mtns)
            mtn = mtns{{idx}};
            mt = {prefix}.MT.(mtn) + 1;
            mdf = {prefix}.MDF.(mtn);
            {prefix}.MTN_by_MT{{mt, 1}} = mtn;
            {prefix}.MDF_by_MT{{mt, 1}} = mdf;
        end\n
        """
        return dedent(s)

    def generate_vars(self):
        # do nothing (for now)
        return f"{self.struct_name}.vars = [];\n"

    def generate(self, out_filepath: pathlib.Path):
        with open(out_filepath, mode="w") as f:
            # Version comment
            f.write(
                f"% This message def file was auto-generated by pyrtma.compile version {__version__}\n\n"
            )

            # create RTMA config generator .m function
            f.write(self.generate_fcn_header(out_filepath.stem))

            # Top-Level RTMA object
            f.write("% Top-Level RTMA object\n")
            f.write(self.initialize_struct())
            f.write("\n\n")

            # RTMA.constants
            f.write("% Constants\n")
            obj: Union[ConstantExpr, ConstantString, HID, MID, TypeAlias, SDF, MT, MDF]
            for obj in self.parser.constants.values():
                f.write(self.generate_constant(obj))
            for obj in self.parser.host_ids.values():
                f.write(self.generate_constant(obj))
            for obj in self.parser.module_ids.values():
                f.write(self.generate_constant(obj))
            for obj in self.parser.message_ids.values():
                f.write(self.generate_constant(obj))
            f.write("\n")

            f.write("% String Constants\n")
            for obj in self.parser.string_constants.values():
                f.write(self.generate_constant_string(obj))
            f.write("\n")

            # RTMA.typedefs
            f.write("% Type Aliases\n")
            for obj in self.parser.aliases.values():
                f.write(self.generate_type_alias(obj))
            f.write("\n")

            # RTMA.HID
            f.write("% Host IDs\n")
            for obj in self.parser.host_ids.values():
                f.write(self.generate_host_id(obj))
            f.write("\n")

            # RTMA.MID
            f.write("% Module IDs\n")
            for obj in self.parser.module_ids.values():
                f.write(self.generate_module_id(obj))
            f.write("\n")

            # RTMA.MT
            f.write("% Message Type IDs\n")
            for obj in self.parser.message_ids.values():
                f.write(self.generate_msg_type_id(obj))
            f.write("\n")

            # RTMA.typedefs
            f.write("% Struct Definitions\n")
            for obj in self.parser.struct_defs.values():
                f.write(self.generate_struct(obj))
                f.write("\n\n")

            # RTMA.MDF
            f.write("% Message Definitions\n")
            for obj in self.parser.message_defs.values():
                f.write(self.generate_struct(obj, top_field="MDF"))
                f.write("\n\n")

            # include STRING_DATA core defs for backwards compatibility with quicklogger and message manager output
            f.write("% Manual Definitions - obsolete core defs\n")
            f.write(f"RTMA.MT.MM_ERROR = 83;\n")
            f.write(f"RTMA.MDF.MM_ERROR = 'VARIABLE_LENGTH_ARRAY(int8)';\n")
            f.write(f"RTMA.MT.MM_INFO = 84;\n")
            f.write(f"RTMA.MDF.MM_INFO = 'VARIABLE_LENGTH_ARRAY(int8)';\n")
            f.write(f"RTMA.MT.DEBUG_TEXT = 91;\n")
            f.write(f"RTMA.MDF.DEBUG_TEXT = 'VARIABLE_LENGTH_ARRAY(int8)';\n")

            # RTMA.hash
            f.write("% Message Definition Hashes\n")
            for obj in self.parser.message_defs.values():
                f.write(self.generate_hash_id(obj))
            f.write("\n\n")

            # MESSAGE_HEADER
            f.write(self.generate_message_header())
            f.write("\n\n")

            # mex_opcode
            f.write(self.generate_mex_opcodes())
            f.write("\n\n")

            # vars -- empty struct (for now)
            f.write(self.generate_vars())

            # MTN_by_MT and MDF_by_MT
            f.write(self.generate_by_MT())

            # close function
            f.write(self.generate_fcn_close())
