import re
import ctypes

from textwrap import dedent
from pyrtma.processor import Processor, Constant, TypeAlias, MT, MID, MDF, SDF


# Field type name to ctypes
type_map = {
    "char": "ctypes.c_char",
    "unsigned char": "ctypes.c_ubyte",
    "byte": "ctypes.c_ubyte",
    "int": "ctypes.c_int",
    "signed int": "ctypes.c_uint",
    "unsigned int": "ctypes.c_uint",
    "unsigned": "ctypes.c_uint",
    "short": "ctypes.c_short",
    "signed short": "ctypes.c_short",
    "unsigned short": "ctypes.c_ushort",
    "long": "ctypes.c_long",
    "signed long": "ctypes.c_long",
    "unsigned long": "ctypes.c_ulong",
    "long long": "ctypes.c_longlong",
    "signed long long": "ctypes.c_longlong",
    "unsigned long long": "ctypes.c_ulonglong",
    "float": "ctypes.c_float",
    "double": "ctypes.c_double",
    "MODULE_ID": "ctypes.c_short",
    "HOST_ID": "ctypes.c_short",
    "MSG_TYPE": "ctypes.c_int",
    "MSG_COUNT": "ctypes.c_int",
}


class PyDefCompiler:
    def __init__(self, processor: Processor, debug: bool = False):
        self.debug = debug
        self.processor = processor

    def generate_constant(self, c: Constant):
        if isinstance(c.value, str):
            return f'{c.name} = "{c.value}"\n'

        return f"{c.name} = {c.value}\n"

    def generate_msg_type_id(self, mt: MT):
        return f"{mt.name} = {mt.value}\n"

    def generate_module_id(self, mid: MID):
        return f"{mid.name} = {mid.value}\n"

    def generate_type_alias(self, td: TypeAlias):
        ftype = type_map.get(td.type_name)
        if ftype:
            return f"{td.name} = {ftype}\n"
        else:
            return f"{td.name} = {td.type_name}\n"

    def generate_struct(self, sdf: SDF):
        assert not sdf.name.startswith("MDF_")
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
                ftype = type_map.get(field.type_name)

                if ftype is None:
                    ftype = field.type_name

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
        assert mdf.name.startswith("MDF_")
        basename = mdf.name[4:]
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
                ftype = type_map.get(field.type_name)

                if ftype is None:
                    ftype = field.type_name

                f.append(
                    f"{tab *4}(\"{field.name}\", {ftype}{' * ' + str(flen) if flen else ''}){nl}"
                )

            fstr += "".join(f)
            fstr += f"\n{tab * 3}]"

        msg_id = mdf.type_id.name
        comment = "# Signal Definition\n" if fnum == 0 else ""
        template = f"""\
        @pyrtma.msg_def
        class {mdf.name}(pyrtma.MessageData):
            _fields_ = {fstr}
            type_id = {msg_id}
            type_name = \"{basename}\"
            type_hash = \"{mdf.hash[:8]}\"
            """
        return dedent(template)

    def generate_imports(self):
        s = """\
        import ctypes
        import pyrtma
        from pyrtma.constants import *
        """
        return dedent(s)

    def generate(self, out_filepath: str):

        if self.debug:
            print(out_filepath)

        with open(out_filepath, mode="w") as f:
            f.write(self.generate_imports())
            f.write("\n")
            prev_obj = None
            for obj in self.processor.objs:
                s = ""
                if type(obj) is Constant:
                    s = self.generate_constant(obj)
                elif type(obj) is MT:
                    s = self.generate_msg_type_id(obj)
                elif type(obj) is MID:
                    s = self.generate_module_id(obj)
                elif type(obj) is MDF:
                    s = self.generate_msg_def(obj)
                elif type(obj) is SDF:
                    s = self.generate_struct(obj)
                elif type(obj) is TypeAlias:
                    s = self.generate_type_alias(obj)
                else:
                    raise RuntimeError(f"Unknown rtma object type of {type(obj)}")

                # Add two lines before class definition after a define
                if type(prev_obj) in (Constant, MT, MID):
                    if type(obj) in (TypeAlias, MDF, SDF):
                        f.write("\n\n")

                # Write the generated code
                f.write(s)

                # Add two lines after a class definition
                if type(obj) in (TypeAlias, MDF, SDF):
                    f.write("\n\n")

                # Store the previous object generated
                prev_obj = obj

                if self.debug:
                    print(s, end="")
