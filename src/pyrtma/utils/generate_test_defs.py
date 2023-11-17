import pathlib
import random
from ruamel.yaml import YAML
from typing import Dict, Any, Optional

# Field type name to ctypes
type_map = (
    "char",
    "unsigned char",
    "byte",
    "int",
    "signed int",
    "unsigned int",
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
    "uint8",
    "uint16",
    "uint32",
    "uint64",
    "int8",
    "int16",
    "int32",
    "int64",
)


class TestDefGenerator:
    def __init__(self):
        self._id = 1000
        self.constants = {}
        self.struct_defs = {}
        self.message_defs = {}

    @property
    def id(self) -> int:
        self._id += 1
        return self._id

    def random_nfields(self) -> int:
        return random.randint(0, 7)

    def random_flen(self) -> int:
        if random.random() > 0.5:
            return 0
        return self.random_expression()

    def random_value(self) -> int:
        return random.randint(1, 9)

    def random_op(self) -> str:
        return random.choice(["", "+", "*"])

    def random_constant(self) -> str:
        if len(self.constants):
            return random.choice(list(self.constants.keys()))
        else:
            return self.random_value()

    def random_expression(self) -> str:
        if random.random() > 0.66:
            c = self.random_constant()
        else:
            c = self.random_value()

        if type(c) is str:
            op = self.random_op()
            if op:
                c2 = self.random_constant()
                return f"{c} {op} {c2}"

        return c

    def random_ftype(self, nested: bool = False) -> int:
        if not nested:
            return random.choice(type_map)

        v = random.random()
        if v < 0.75:
            return random.choice(type_map)

        if random.random() > 0.5:
            return random.choice(list(self.struct_defs.keys()) or type_map)
        else:
            return random.choice(list(self.message_defs.keys()) or type_map)

    def random_fieldname(self, ftype: str) -> str:
        if ftype in ("unsigned char", "byte"):
            return "uint8"
        elif ftype == "char":
            return "char"
        elif ftype == "unsigned short":
            return "uint16"
        elif ftype == "short":
            return "int16"
        elif ftype in ("signed int", "int", "long"):
            return "int32"
        elif ftype in ("unsigned int", "unsigned long"):
            return "uint32"
        elif ftype in ("signed long long", "long long"):
            return "int64"
        elif ftype == "unsigned long long":
            return "uint64"
        else:
            return ftype

    def generate_constants(self, n: int):
        for i in range(1, n):
            name = f"C_{i:02d}"
            self.constants[name] = self.random_expression()

    def generate_structs(self, n: int):
        for i in range(1, n):
            name = f"SRCT_{i:02d}"
            fields = {}
            nfields = self.random_nfields() or 1
            for k in range(1, nfields + 1):
                ftype = self.random_ftype()
                fname = f"{self.random_fieldname(ftype)}_{k}"
                flen = self.random_flen()
                if flen == 0:
                    fields[fname] = f"{ftype}"
                else:
                    fields[fname] = f"{ftype}[{flen}]"

            self.struct_defs[name] = dict(fields=fields)

    def generate_message_defs(self, n: int):
        for i in range(1, n):
            name = f"MSG_{i:03d}"
            fields = {}
            nfields = self.random_nfields()
            for k in range(1, nfields + 1):
                ftype = self.random_ftype(nested=True)
                fname = f"{self.random_fieldname(ftype)}_{k}"
                flen = self.random_flen()
                if flen == 0:
                    fields[fname] = f"{ftype}"
                else:
                    fields[fname] = f"{ftype}[{flen}]"

            self.message_defs[name] = dict(id=self.id, fields=fields)

    def generate(self, out_filepath: pathlib.Path):
        self.generate_constants(24)
        self.generate_structs(10)
        self.generate_message_defs(128)

        d: Dict[str, Any] = dict(
            constants=self.constants,
            struct_defs=self.struct_defs,
            message_defs=self.message_defs,
        )

        class NullRepresenter:
            def __init__(self):
                self.count = 0

            def __call__(self, repr, data):
                return repr.represent_scalar("tag:yaml.org,2002:null", "null")

        yaml = YAML()
        yaml.default_flow_style = False
        my_represent_none = NullRepresenter()
        yaml.representer.add_representer(type(None), my_represent_none)
        yaml.dump(d, out_filepath)


if __name__ == "__main__":
    g = TestDefGenerator()
    d = g.generate(pathlib.Path("./test_defs.yaml"))
