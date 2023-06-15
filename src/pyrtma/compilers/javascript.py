from typing import Union
from pyrtma.parser import Struct
from textwrap import dedent
from pyrtma.processor import Processor, Constant, TypeAlias, MT, MID, MDF, SDF, HID

# Native C types that are supported
typemap = {
    "char": '""',
    "unsigned char": "0",
    "byte": "0",
    "int": "0",
    "signed int": "0",
    "unsigned int": "0",
    "unsigned": "0",
    "short": "0",
    "signed short": "0",
    "unsigned short": "0",
    "long": "0",
    "signed long": "0",
    "unsigned long": "0",
    "long long": "0",
    "signed long long": "0",
    "unsigned long long": "0",
    "float": "0",
    "double": "0",
}


def pad(indent: int) -> str:
    return indent * "\t"


class JSDefCompiler:
    def __init__(self, processor: Processor, debug: bool = False):
        self.debug = debug
        self.processor = processor

    def generate_constant(self, c: Constant):
        if isinstance(c.value, str):
            return f'RTMA.constants.{c.name} = "{c.value}"\n'

        return f"RTMA.constants.{c.name}= {c.value};\n"

    def generate_prop(self, name: str, value: str):
        return f"{name}: {value}"

    def generate_msg_type_id(self, mt: MT) -> str:
        base_name = mt.name[3:]
        return f"RTMA.MT.{base_name} = {mt.value};\n"

    def generate_host_id(self, hid: HID) -> str:
        return f"RTMA.HID.{hid.name} = {hid.value};\n"

    def generate_module_id(self, mid: MID) -> str:
        base_name = mid.name[4:]
        return f"RTMA.MID.{base_name} = {mid.value};\n"

    def generate_type_alias(self, td: TypeAlias) -> str:
        s = typemap.get(td.type_name)
        if s:
            return f"RTMA.typedefs.{td.name} = {s};\n"

        if td.type_name.startswith("MDF_"):
            if td.name.startswith("MDF_"):
                return f"RTMA.MDF.{td.name[4:]} = RTMA.MDF.{td.type_name[4:]};\n"
            else:
                return f"RTMA.typedefs.{td.name} = RTMA.MDF.{td.type_name[4:]};\n"

        return f"RTMA.typedefs.{td.name} = RTMA.typedefs.{td.type_name};\n"

    def generate_obj(self, struct: Union[SDF, MDF]) -> str:
        if isinstance(struct, MDF):
            prefix = "MDF"
            basename = struct.name[4:]
        elif isinstance(struct, SDF):
            prefix = "typedefs"
            basename = struct.name

        tabs = "\t" * 2
        num_fields = len(struct.fields)

        if num_fields == 0:
            return f"RTMA.{prefix}.{basename} = () => {{ return {{}} }};"

        s = f"RTMA.{prefix}.{basename} = () => {{\n\treturn {{\n"

        for n, field in enumerate(struct.fields, start=1):
            s += tabs
            if field.type_name in typemap.keys():
                if field.length is not None:
                    if field.type_name.startswith("char"):
                        s += f'{field.name}: ""'
                    else:
                        s += f"{field.name}: Array({field.length}).fill(0)"
                else:
                    if field.type_name.startswith("char"):
                        s += f'{field.name}: ""'
                    else:
                        s += f"{field.name}: 0"
            elif field.type_name.startswith("MDF"):
                if field.length is not None:
                    s += f"{field.name}: Array({field.length}).fill(RTMA.MDF.{field.type_name}())"
                else:
                    s += f"{field.name}: RTMA.MDF.{field.type_name}()"
            else:
                if field.length is not None:
                    s += f"{field.name}: Array({field.length}).fill(RTMA.typedefs.{field.type_name}())"
                else:
                    s += f"{field.name}: RTMA.typedefs.{field.type_name}()"

            if n < num_fields:
                s += ",\n"
            else:
                s += "\n"

        s += "\t}\n"
        s += "};"

        return s

    def generate(self, out_filepath: str):

        if self.debug:
            print(out_filepath)

        with open(out_filepath, mode="w") as f:
            # Exports
            f.write("export { RTMA } ;\n\n")

            # Top-Level RTMA object
            f.write("const RTMA = {};\n\n")

            # RTMA.constants
            f.write("RTMA.constants =  {};\n")

            # RTMA.typedefs
            f.write("RTMA.typedefs =  {};\n")

            # RTMA.MT
            f.write("RTMA.MT = {};\n")

            # RTMA.HID
            f.write("RTMA.HID =  {};\n")

            # RTMA.MID
            f.write("RTMA.MID =  {};\n")

            # RTMA.MDF
            f.write("RTMA.MDF = {};\n")

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
                elif type(obj) is HID:
                    s = self.generate_host_id(obj)
                elif type(obj) is TypeAlias:
                    s = self.generate_type_alias(obj)
                elif isinstance(obj, (SDF, MDF)):
                    s = self.generate_obj(obj)
                else:
                    raise RuntimeError(f"Unknown rtma object type of {type(obj)}")

                # Add two lines before obj definition after a define
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
