import textwrap
import pyrtma
from pyrtma.parser import Processor, Struct

supported_types = [
    "char",
    "unsigned char",
    "byte",
    "int",
    "signed int",
    "unsigned int",
    "unsigned",
    "short",
    "signed short",
    "unsigned short",
    "long",
    "signed long",
    "unsigned long",
    "long long",
    "signed long long",
    "unsigned long long",
    "float",
    "double",
]


class JSDefCompiler:
    def __init__(self, processor: Processor):
        self.processor = processor

    def generate_constant(self, name: str, value: str):
        return f"const {name}= {value};\n"

    def generate_prop(self, name: str, value: str):
        return f"{name}: {value}"

    def generate_fields(self, s: Struct):
        x = {}
        for field in s.fields:
            # Check for a typedef of a supported type
            if self.processor.typedefs.get(field.type_name) is not None:
                field.type_name = self.processor.typedefs[field.type_name]

            if field.type_name in supported_types:
                # regular type
                if field.length is not None:
                    # Array
                    if field.type_name.startswith("char"):
                        x[field.name] = f'{field.name}: ""'
                    else:
                        x[field.name] = f"{field.name}: Array({field.length}).fill(0)"

                else:
                    if field.type_name.startswith("char"):
                        x[field.name] = f'{field.name}: ""'
                    else:
                        x[field.name] = f"{field.name}: 0"

            elif self.processor.structs.get(field.type_name):
                # struct type
                s = self.processor.structs[field.type_name]
                x[field.name] = self.generate_fields(s)
            else:
                raise RuntimeError(
                    f"Unsupported type in message defintion {s.name} : {field.type_name}"
                )
        return x

    def generate_obj(self, x, fname: str = "", indent=1):
        # Open object
        padding = "\t" * indent
        if fname == "":
            s = "{\n"
        else:
            s = f"{padding}{fname}: {{\n"

        # Fill object fields
        for field, value in x.items():
            if isinstance(value, dict):
                obj = self.generate_obj(value, fname=field, indent=indent + 1)
                s += obj
            else:
                s += (indent + 1) * "\t"
                s += value
            s += ",\n"

        # Close object
        s += padding
        s += "}"
        return s

    def generate(self, out_filepath: str):

        with open(out_filepath, mode="w") as f:

            f.write("export { RTMA } ;\n\n")

            # Top-Level Constants
            f.write("// RTMA Constants\n")
            for name, value in self.processor.constants.items():
                f.write(self.generate_constant(name, value))

            f.write("\n")

            # Top-Level RTMA object
            f.write("const RTMA = {\n")

            # RTMA.constants
            indent = 1
            f.write(indent * "\t")
            f.write("constants: {\n")

            indent += 1
            for name, value in self.processor.constants.items():
                f.write(indent * "\t")
                f.write(self.generate_prop(name, value))
                f.write(",\n")
            indent -= 1
            f.write(indent * "\t")
            f.write("},\n")

            f.write("\n")

            # RTMA.MT
            f.write(indent * "\t")
            f.write("MT: {\n")

            indent += 1
            for name, value in self.processor.MT.items():
                f.write(indent * "\t")
                if name.startswith("MT_"):
                    prop_name = name[3:]
                else:
                    prop_name = name

                f.write(self.generate_prop(prop_name, value))
                f.write(",\n")
            indent -= 1
            f.write(indent * "\t")
            f.write("},\n")

            f.write("\n")

            # RTMA.MID
            f.write(indent * "\t")
            f.write("MID: {\n")

            indent += 1
            for name, value in self.processor.MID.items():
                f.write(indent * "\t")
                if name.startswith("MID_"):
                    prop_name = name[4:]
                else:
                    prop_name = name
                f.write(self.generate_prop(prop_name, value))
                f.write(",\n")
            indent -= 1
            f.write(indent * "\t")
            f.write("},\n")

            f.write("\n")

            # RTMA.MDF
            f.write(indent * "\t")
            f.write("MDF : {\n")

            indent += 1
            for name, s in self.processor.structs.items():
                x = self.generate_fields(s)
                f.write(indent * "\t")
                pad = (indent + 1) * "\t"
                if name.startswith("MDF_"):
                    prop_name = name[4:]
                else:
                    prop_name = name

                f.write(f"{prop_name}: () => {{\n{pad}return ")

                f.write(self.generate_obj(x, indent=indent + 1))
                pad = indent * "\t"
                f.write(f"\n{pad}}},\n\n")
            indent -= 1
            f.write(indent * "\t")
            f.write("},\n")

            # Close Top-Level RTMA object
            f.write("};\n")
