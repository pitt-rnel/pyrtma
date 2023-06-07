import re
import json
import copy
from hashlib import sha256
from typing import List, Optional, Any, Dict, Union
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
class Include:
    raw: str
    file: str


@dataclass
class Define:
    raw: str
    name: str
    expression: str


@dataclass
class Typedef:
    raw: str
    alias: str
    type: str


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


Tokens = Union[Include, Define, Typedef, Struct]


class Parser:
    COMMENT_REGEX = r"//(.*)\n"

    BLOCK_COMMENT_REGEX = r"/\*(.*?)\*/"

    INCLUDE_REGEX = r"#include\s+\"(?P<include_file>[\w/\._:]+)\""

    DEFINE_REGEX = (
        r"#define\s*(?P<macro_name>\w+)\s+(?P<expression>[\(\)\[\]\w \*/\+\-\.]*?)\s*\n"
    )
    TYPEDEF_REGEX = r"\s*typedef\s+(?P<typedef_qual1>\w+\s+)?\s*(?P<typedef_qual2>\w+\s+)?\s*(?P<typedef_type>\w+)\s+(?P<typedef_alias>\w+)\s*;\s*$"

    FIELD_REGEX = r"\s*(?P<qual1>\w+\s+)?\s*(?P<qual2>\w+\s+)?\s*(?P<typ>\w+)\s+(?P<name>\w+)\s*(\[(?P<length>.*?)\])?;"

    STRUCT_REGEX = (
        r"\s*typedef\s+struct\s*\{(?P<struct_def>.*?)\}(?P<struct_name>\s*\w*)\s*;"
    )

    @staticmethod
    def preprocess(text: str) -> str:
        # Strip Inline Comments
        text = re.sub(r"//(.*)\n", r"\n", text)

        # Strip Block Comments
        text = re.sub(r"/\*(.*?)\*/", r"\n", text, flags=re.DOTALL)

        # Strip Tabs
        text = re.sub(r"\t+", " ", text)

        return text

    @staticmethod
    def parse(
        msgdefs_file: str, included_files: Optional[List[str]] = None
    ) -> List[Tokens]:
        if included_files is None:
            included_files = []

        included_files.append(msgdefs_file)
        print(f"parsing {msgdefs_file}")

        token_specification = [
            ("INCLUDE", Parser.INCLUDE_REGEX),
            ("DEFINE", Parser.DEFINE_REGEX),
            ("TYPEDEF", Parser.TYPEDEF_REGEX),
            ("STRUCT", Parser.STRUCT_REGEX),
        ]

        token_pattern = "|".join(
            f"(?P<{name}>{regex})" for (name, regex) in token_specification
        )

        with open(msgdefs_file, "rt") as f:
            text = Parser.preprocess(f.read())

        tokens = []

        for m in re.finditer(token_pattern, text, flags=re.MULTILINE | re.DOTALL):
            # print(f"{m.lastgroup}: \n{m.group().strip()}\n")

            token_type = m.lastgroup
            raw = m.group()

            if token_type == "INCLUDE":
                fname = m.group("include_file").strip()
                token = Include(raw, fname)
                if fname not in included_files:
                    more_tokens = Parser.parse(fname, included_files)
                    more_tokens.insert(0, token)
                    token = more_tokens
                else:
                    print(f"skipping {fname}")

            elif token_type == "DEFINE":
                name = m.group("macro_name").strip()
                exp = m.group("expression").strip() or "1"
                token = Define(raw, name, exp)
            elif token_type == "TYPEDEF":
                alias = m.group("typedef_alias").strip()
                qual1 = (m.group("typedef_qual1") or "").strip()
                qual2 = (m.group("typedef_qual2") or "").strip()
                base_type = m.group("typedef_type").strip()
                ftype = f"{qual1}"
                ftype += f" {qual2}" if qual2 else ""
                ftype += f" {base_type}"
                token = Typedef(raw, alias, ftype.strip())
            elif token_type == "STRUCT":
                hash = sha256(raw.strip().encode()).hexdigest()
                name = m.group("struct_name").strip()
                token = Struct(raw, hash, name)

                for fmatch in re.finditer(
                    Parser.FIELD_REGEX,
                    m.groupdict()["struct_def"],
                    flags=re.MULTILINE | re.DOTALL,
                ):
                    # print(f"{fmatch.lastgroup}: \n{fmatch.group().strip()}")
                    raw = fmatch.group()
                    fname = fmatch.group("name").strip()
                    qual1 = (fmatch.group("qual1") or "").strip()
                    qual2 = (fmatch.group("qual2") or "").strip()
                    base_type = fmatch.group("typ").strip()
                    ftype = f"{qual1}"
                    ftype += f" {qual2}" if qual2 else ""
                    ftype += f" {base_type}"
                    flen = fmatch.group("length") or None
                    token.fields.append(StructField(raw, fname, ftype.strip(), flen))
            else:
                raise RuntimeError("Unknown token type of {token_type} found.")

            if isinstance(token, list):
                tokens.extend(token)
            else:
                tokens.append(token)

        return tokens

    @staticmethod
    def to_json(msgdef_file):
        tokens = Parser.parse(msgdef_file)
        return json.dumps(tokens, indent=2, cls=CustomEncoder)


class CustomEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if is_dataclass(o):
            return asdict(o)
        return super().default(o)


class Processor:
    def __init__(self, tokens: List[Tokens]):
        self.constants = {}
        self.MT: Dict[str, str] = {}
        self.MID: Dict[str, str] = {}
        self.typedefs: Dict[str, str] = {}
        self.structs: Dict[str, Struct] = {}

        self.eval(tokens)

    def eval_define(self, macro: Define):
        # Store a mapping for each define type
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
        else:
            if self.constants.get(macro.name) is None:
                self.constants[macro.name] = macro.expression
            else:
                raise KeyError(f"Duplicate constant definition found: {macro.name}")

    def eval_typedef(self, typedef: Typedef):
        if self.typedefs.get(typedef.alias) is None:
            self.typedefs[typedef.alias] = typedef.type
        else:
            raise KeyError(f"Duplicate typedef found: {typedef.alias}")

    def eval_struct(self, struct: Struct):
        if self.structs.get(struct.name) is None:
            self.structs[struct.name] = copy.deepcopy(struct)
        else:
            raise KeyError(f"Duplicate struct definition found: {struct.name}")

        if len(struct.fields) == 0:
            raise RuntimeError(f"Struct {struct.name} does not contain any fields.")

    def eval(self, tokens: List[Tokens]):
        for token in tokens:
            if isinstance(token, Define):
                self.eval_define(token)
            elif isinstance(token, Typedef):
                self.eval_typedef(token)
            elif isinstance(token, Struct):
                self.eval_struct(token)
            elif isinstance(token, Include):
                pass

        for msg_type in self.MT.keys():
            # Add an empty struct placeholder for signal definitions
            if msg_type.startswith("MT_"):
                raw = ""
                hash = sha256(b"").hexdigest()
                name = "MDF_" + msg_type[3:]

                if name not in self.structs.keys():
                    s = Struct(raw, hash, name)
                    self.structs[name] = s
