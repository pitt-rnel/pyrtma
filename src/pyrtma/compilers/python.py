import re
import ctypes

from pyrtma.parser import Processor, Struct


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
    "MODULE_ID": ctypes.c_short,
    "HOST_ID": ctypes.c_short,
    "MSG_TYPE": ctypes.c_int,
    "MSG_COUNT": ctypes.c_int,
}


class PyDefCompiler:
    def __init__(self, processor: Processor):
        self.processor = processor

    def generate_constant(self, name: str, value: str):
        # Ensure division results in an integer if no decimal
        if "/" in value and "." not in value:
            return f"{name} = int({value})\n"
        else:
            return f"{name} = {value}\n"

    def generate_typedef(self, alias: str, value: str):
        t = ctypes_map.get(value)
        if t:
            ftype = f"{t.__module__}.{t.__name__}"
        else:
            raise ValueError(f"Invalid typedef alias for {alias} to {value}.")

        return f"{alias} = {ftype}"

    def generate_struct(self, s: Struct):
        assert not s.name.startswith("MDF_")
        f = []
        fnum = len(s.fields)
        for i, field in enumerate(s.fields, start=1):
            if field.length and re.search(r"/|\+|\*|-", field.length):
                flen = "int(" + field.length + ")"
            else:
                flen = field.length

            nl = ",\n" if i < fnum else ""

            t = ctypes_map.get(field.type_name)
            if t:
                ftype = f"{t.__module__}.{t.__name__}"
            else:
                ftype = field.type_name

            f.append(
                f"        (\"{field.name}\", {ftype}{' * ' + flen if flen else ''}){nl}"
            )

        fstr = "".join(f)

        template = f"""
class {s.name}(ctypes.Structure):
    _fields_ = [
{fstr}
    ]

"""
        return template

    def generate_msg_def(self, s: Struct):
        assert s.name.startswith("MDF_")
        basename = s.name[4:]
        f = []
        fnum = len(s.fields)
        for i, field in enumerate(s.fields, start=1):
            if field.length and re.search(r"/|\+|\*|-", field.length):
                flen = "int(" + field.length + ")"
            else:
                flen = field.length

            nl = ",\n" if i < fnum else ""

            # Check for a typedef back to native c type
            t = ctypes_map.get(field.type_name)
            if t:
                ftype = f"{t.__module__}.{t.__name__}"
            else:
                ftype = field.type_name

            f.append(
                f"        (\"{field.name}\", {ftype}{' * ' + flen if flen else ''}){nl}"
            )

        fstr = "".join(f)

        msg_id = "MT_" + basename
        template = f"""
@pyrtma.msg_def
class {s.name}(pyrtma.MessageData):
    _fields_ = [
{fstr}
    ]
    type_id = {msg_id}
    type_name = \"{basename}\"

"""
        return template

    def generate_sig_def(self, s: Struct):
        assert s.name.startswith("MDF_")
        basename = s.name[4:]
        msg_id = "MT_" + basename
        template = f"""
# Signal Definition
@pyrtma.msg_def
class {s.name}(pyrtma.MessageData):
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

            for name, expression in self.processor.constants.items():
                f.write(self.generate_constant(name, expression))
            f.write("\n")

            for name, expression in self.processor.MT.items():
                f.write(self.generate_constant(name, expression))
            f.write("\n")

            for name, expression in self.processor.MID.items():
                f.write(self.generate_constant(name, expression))
            f.write("\n")

            for alias, ftype in self.processor.typedefs.items():
                f.write(self.generate_typedef(alias, ftype))
            f.write("\n")

            for name, s in self.processor.structs.items():
                if name.startswith("MDF_"):
                    if len(s.fields) > 0:
                        f.write(self.generate_msg_def(s))
                    else:
                        f.write(self.generate_sig_def(s))
                else:
                    f.write(self.generate_struct(s))
