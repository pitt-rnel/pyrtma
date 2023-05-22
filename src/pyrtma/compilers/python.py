import re
import ctypes

from pyrtma.parser import Parser


# Field type name to ctypes
ctypes_map = {
    "char": ctypes.c_char,
    "unsigned char": ctypes.c_ubyte,
    "byte": ctypes.c_ubyte,
    "int": ctypes.c_int,
    "signed int": ctypes.c_uint,
    "unsigned int": ctypes.c_uint,
    "unsigned": ctypes.c_uint,
    "short": ctypes.c_short,
    "signed short": ctypes.c_short,
    "unsigned short": ctypes.c_ushort,
    "long": ctypes.c_long,
    "signed long": ctypes.c_long,
    "unsigned long": ctypes.c_ulong,
    "long long": ctypes.c_longlong,
    "signed long long": ctypes.c_longlong,
    "unsigned long long": ctypes.c_ulonglong,
    "float": ctypes.c_float,
    "double": ctypes.c_double,
    "int8_t": ctypes.c_int8,
    "int16_t": ctypes.c_int16,
    "int32_t": ctypes.c_int32,
    "int64_t": ctypes.c_int64,
    "uint8_t": ctypes.c_uint8,
    "uint16_t": ctypes.c_uint16,
    "uint32_t": ctypes.c_uint32,
    "uint64_t": ctypes.c_uint64,
    "MODULE_ID": ctypes.c_short,
    "HOST_ID": ctypes.c_short,
    "MSG_TYPE": ctypes.c_int,
    "MSG_COUNT": ctypes.c_int,
}


class PyDefCompiler:
    def __init__(self, parser: Parser):
        self.parser = parser

    def generate_constant(self, name, value):
        # Ensure division results in an integer if no decimal
        if "/" in value and "." not in value:
            return f"{name} = int({value})\n"
        else:
            return f"{name} = {value}\n"

    def generate_typedef(self, alias, value):
        t = ctypes_map.get(value)
        if t:
            ftype = f"{t.__module__}.{t.__name__}"
        else:
            raise ValueError("Invalid typedef alias for {alias} to {value}.")

        return f"{alias} = {ftype}"

    def generate_struct(self, name: str, fields):
        assert not name.startswith("MDF_")
        f = []
        fnum = len(fields)
        for i, (fname, ftype, flen) in enumerate(fields, start=1):
            if flen and re.search(r"/|\+|\*|-", flen):
                flen = "int(" + flen + ")"

            nl = ",\n" if i < fnum else ""

            t = ctypes_map.get(ftype)
            if t:
                ftype = f"{t.__module__}.{t.__name__}"

            f.append(
                f"        (\"{fname}\", {ftype}{' * ' + flen if flen else ''}){nl}"
            )

        fstr = "".join(f)

        template = f"""
class {name}(ctypes.Structure):
    _fields_ = [
{fstr}
    ]

"""
        return template

    def generate_msg_def(self, name: str, fields):
        assert name.startswith("MDF_")

        basename = name[4:]
        f = []
        fnum = len(fields)
        for i, (fname, ftype, flen) in enumerate(fields, start=1):
            if flen and re.search(r"/|\+|\*|-", flen):
                flen = "int(" + flen + ")"

            nl = ",\n" if i < fnum else ""

            t = ctypes_map.get(ftype)
            if t:
                ftype = f"{t.__module__}.{t.__name__}"

            f.append(
                f"        (\"{fname}\", {ftype}{' * ' + flen if flen else ''}){nl}"
            )

        fstr = "".join(f)

        msg_id = "MT_" + basename
        template = f"""
@pyrtma.msg_def
class {name}(pyrtma.MessageData):
    _fields_ = [
{fstr}
    ]
    type_id = {msg_id}
    type_name = \"{basename}\"

"""
        return template

    def generate_sig_def(self, name: str):
        assert name.startswith("MDF_")
        basename = name[4:]
        msg_id = "MT_" + basename
        template = f"""
# Signal Definition
@pyrtma.msg_def
class {name}(pyrtma.MessageData):
    _fields_ = []
    type_id = {msg_id}
    type_name = \"{basename}\"

"""
        return template

    def generate_imports(self):
        return """
import ctypes
import pyrtma
from pyrtma.constants import *

"""

    def generate(self, out_filepath: str):

        with open(out_filepath, mode="w") as f:
            f.write(self.generate_imports())

            for name, value in self.parser.constants.items():
                f.write(self.generate_constant(name, value))
            f.write("\n")

            for name, value in self.parser.MT.items():
                f.write(self.generate_constant(name, value))
            f.write("\n")

            for name, value in self.parser.MID.items():
                f.write(self.generate_constant(name, value))
            f.write("\n")

            for name, value in self.parser.typedefs.items():
                f.write(self.generate_typedef(name, value))
            f.write("\n")

            for name, fields in self.parser.structs.items():
                if name.startswith("MDF_"):
                    if fields is not None:
                        f.write(self.generate_msg_def(name, fields))
                    else:
                        f.write(self.generate_sig_def(name))
                else:
                    f.write(self.generate_struct(name, fields))
