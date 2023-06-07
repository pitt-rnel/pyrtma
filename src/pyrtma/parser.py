import re
import json
import copy
from hashlib import sha256
from typing import List, Optional, Any, Dict
from dataclasses import dataclass, field, is_dataclass, asdict


def camelcase(name):
    name = re.sub(r"_", " ", name)
    pieces = [s.title() for s in name.split(sep=" ")]
    return "".join(pieces)


# Field type name to ctypes
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


@dataclass
class Define:
    raw: str
    name: str
    expression: str


@dataclass
class Typedef:
    raw: str
    alias: str
    native_type: str


@dataclass
class StructField:
    raw: str
    name: str
    type_name: str
    length: Optional[str]


@dataclass
class Struct:
    raw: str
    hash: str
    name: str
    fields: List[StructField] = field(default_factory=list)


class Parser:
    DEFINE_REGEX = r"#define\s*(?P<name>\w+)\s+(?P<expression>[\(\)\[\]\w \*/\+-\.]+)\n"

    TYPEDEF_REGEX = r"\s*typedef\s+(?P<qual1>\w+\s+)?\s*(?P<qual2>\w+\s+)?\s*(?P<typ>\w+)\s+(?P<name>\w+)\s*;\s*$"

    STRUCT_REGEX = r"\s*typedef\s+struct\s*\{(?P<def>.*?)\}(?P<name>\s*\w*)\s*;"

    FIELD_REGEX = r"(?P<qual1>\w+\s+)?\s*(?P<qual2>\w+\s+)?\s*(?P<typ>\w+)\s+(?P<name>\w+)\s*(\[(?P<length>.*)\])?$"

    def __init__(self):
        self.defines = []
        self.typedefs = []
        self.structs = []
        self.files = []

    def preprocess(self, text: str) -> str:
        # Strip Inline Comments
        text = re.sub(r"//(.*)\n", r"\n", text)

        # Strip Block Comments
        text = re.sub(r"/\*(.*?)\*/", r"\n", text, flags=re.DOTALL)

        # Strip Tabs
        text = re.sub(r"\t+", " ", text)

        return text

    def parse_defines(self, text: str):
        # Get Defines (Only simple one line constants here)
        macros = re.finditer(self.DEFINE_REGEX, text)

        for m in macros:
            raw = m.group()
            name = m.group("name").strip()
            exp = m.group("expression").strip()
            macro = Define(raw, name, exp)
            self.defines.append(macro)

    def parse_typedefs(self, text: str):
        # Get simple typedefs
        c_typedefs = re.finditer(
            self.TYPEDEF_REGEX,
            text,
            flags=re.MULTILINE,
        )

        for m in c_typedefs:
            raw = m.group()
            alias = m.group("name").strip()
            if alias.startswith("MDF_"):
                # TODO:Non struct message defintion. Maybe drop support?
                pass
            else:
                # Field type
                qual1 = m.group("qual1")
                qual2 = m.group("qual2")
                typ = m.group("typ")

                ftype = ""
                if qual1:
                    ftype += qual1.strip()
                    ftype += " "

                if qual2:
                    ftype += qual2.strip()
                    ftype += " "

                ftype += typ.strip()

                # Must be a natively supported field type
                assert (
                    ftype in supported_types
                ), f"Alias {alias} to type {ftype} is not supported."

                self.typedefs.append(Typedef(raw, alias, ftype))

    def parse_structs(self, text: str):
        # Strip Newlines
        text = re.sub(r"\n", "", text)

        # Get Struct Raw Definitions
        c_msg_defs = re.finditer(self.STRUCT_REGEX, text)

        for m in c_msg_defs:
            raw = m.group()
            hash = sha256(raw.strip().encode()).hexdigest()
            name = m.group("name").strip()
            s = Struct(raw, hash, name)

            fields = m.group("def").split(sep=";")
            fields = [f.strip() for f in fields if f.strip() != ""]

            for field in fields:
                fmatch = re.match(self.FIELD_REGEX, field)

                if fmatch is None:
                    print(field)
                    raise RuntimeError("Error parsing field definition.")

                # Field name
                raw = fmatch.group()
                fname = fmatch.group("name").strip()
                qual1 = fmatch.group("qual1")
                qual2 = fmatch.group("qual2")
                typ = fmatch.group("typ")

                ftype = ""
                if qual1:
                    ftype += qual1.strip()
                    ftype += " "

                if qual2:
                    ftype += qual2.strip()
                    ftype += " "

                ftype += typ.strip()

                flen = fmatch.group("length") or None
                s.fields.append(StructField(raw, fname, ftype, flen))

            self.structs.append(s)

    def to_json(self):
        d = dict(defines=self.defines, typedefs=self.typedefs, structs=self.structs)
        return json.dumps(d, indent=2, cls=CustomEncoder)

    def parse_file(self, filename):
        """Parse a C header file for message definitions.
        Notes:
            * Does not follow other #includes (TODO)
            * Parsing order: #defines, typedefs, typedef struct
        """

        self.files.append(filename)

        with open(filename, "r") as f:
            raw = f.read()

        text = self.preprocess(raw)
        self.parse_defines(text)
        self.parse_typedefs(text)
        self.parse_structs(text)

    def parse(self, files):
        for file in files:
            self.parse_file(file)


class CustomEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if is_dataclass(o):
            return asdict(o)
        return super().default(o)


class Processor:
    def __init__(self, parser: Parser):
        self.constants = {}
        self.MT: Dict[str, str] = {}
        self.MID: Dict[str, str] = {}
        self.HID: Dict[str, str] = {}
        self.typedefs: Dict[str, str] = {}
        self.structs: Dict[str, Struct] = {}
        self.eval(parser)

    def eval_defines(self, defines: List[Define]):
        # Store a mapping for each define type
        for macro in defines:
            if macro.name.startswith("MT_"):
                if self.MT.get(macro.name) is None:
                    self.MT[macro.name] = macro.expression
                else:
                    raise KeyError(f"Duplicate MT definition found: {macro.name}")
            elif macro.name.startswith("MID_"):
                if self.MID.get(macro.name) is None:
                    self.MID[macro.name] = macro.expression
                else:
                    raise KeyError(f"Duplicate MID definition found: {macro.name}")
            elif macro.name.startswith("HID_"):
                if self.HID.get(macro.name) is None:
                    self.HID[macro.name] = macro.expression
                else:
                    raise KeyError(f"Duplicate HID definition found: {macro.name}")
            else:
                if self.constants.get(macro.name) is None:
                    self.constants[macro.name] = macro.expression
                else:
                    raise KeyError(f"Duplicate constant definition found: {macro.name}")

    def eval_typedefs(self, typedefs: List[Typedef]):
        for typedef in typedefs:
            if self.typedefs.get(typedef.alias) is None:
                self.typedefs[typedef.alias] = typedef.native_type
            else:
                raise KeyError(f"Duplicate typedef found: {typedef.alias}")

    def eval_structs(self, structs: List[Struct]):
        for struct in structs:
            if self.structs.get(struct.name) is None:
                self.structs[struct.name] = copy.deepcopy(struct)
            else:
                raise KeyError(f"Duplicate struct definition found: {struct.name}")

        for msg_type in self.MT.keys():
            # Add an empty struct placeholder for signal definitions
            if msg_type.startswith("MT_"):
                raw = ""
                hash = sha256(b"").hexdigest()
                name = "MDF_" + msg_type[3:]

                if name not in self.structs.keys():
                    s = Struct(raw, hash, name)
                    self.structs[name] = s

    def eval(self, parser: Parser):
        self.eval_defines(parser.defines)
        self.eval_typedefs(parser.typedefs)
        self.eval_structs(parser.structs)
