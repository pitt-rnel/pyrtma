import re
import json
import copy
from hashlib import sha256
from typing import List, Optional, Any, Dict, Union
from dataclasses import dataclass, field, is_dataclass, asdict


# Native C types that are supported
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
    expanded: str = ""
    value: Optional[Union[str, int, float]] = None


@dataclass
class TypeDef:
    raw: str
    alias: str
    type: str


@dataclass
class StructField:
    raw: str
    name: str
    type_name: str
    length_str: Optional[str] = None
    length: Optional[int] = None


@dataclass
class Struct:
    raw: str
    hash: str
    name: str
    fields: List[StructField] = field(default_factory=list)


Tokens = Union[Include, Define, TypeDef, Struct]

COMMENT_REGEX = r"//(.*)\n"

BLOCK_COMMENT_REGEX = r"/\*(.*?)\*/"

INCLUDE_REGEX = r"#include\s+\"(?P<include_file>[\w/\._:]+)\""

# Simple online macro expressions
MACRO_EXP_REGEX = r"#define[\t ]+(?P<macro_name>\w+)[\t ]+(?P<expression>.*)"

# Macro directive flags with no expression
MACRO_FLAG_REGEX = r"#define[\t ]+(?P<macro_flag>\w+)\s*\n"

# Oneline function like macros (not supported)
MACRO_FUNC_REGEX = (
    r"#define[\t ]+(?P<macro_func>\w+\(.*\))[\t ]+(?P<func_expression>.*)"
)

# Multiline macros (not supported)
MACRO_MULTI_REGEX = r"#define[\t ]+(?P<macro_multi>\w+|\w+\(.*\)).*\\$"

# DEFINE_REGEX = r"#define[\t ]*(?P<macro_name>\w+|(?P<macro_func>\w+\(.*\)))([\t ]+(?P<expression>.*$))|#define[\t ]*(?P<macro_flag>\w+)"

# Combined regex for #define types. Note order matters.
DEFINE_REGEX = (
    rf"{MACRO_MULTI_REGEX}|{MACRO_FUNC_REGEX}|{MACRO_EXP_REGEX}|{MACRO_FLAG_REGEX}"
)

TYPEDEF_REGEX = r"\s*typedef\s+(?P<typedef_qual1>\w+\s+)?\s*(?P<typedef_qual2>\w+\s+)?\s*(?P<typedef_type>\w+)\s+(?P<typedef_alias>\w+)\s*;\s*"

FIELD_REGEX = r"\s*(?P<qual1>\w+\s+)?\s*(?P<qual2>\w+\s+)?\s*(?P<typ>\w+)\s+(?P<name>\w+)\s*(\[(?P<length>.*?)\])?;"

STRUCT_REGEX = (
    r"(?s:(\s*typedef\s+struct\s*\{(?P<struct_def>.*?)\}(?P<struct_name>\s*\w*)\s*;))"
)

# Other patterns
INT_REGEX = r"[-+]?(0[xX][\dA-Fa-f]+|0[0-7]*|\d+)"
HEX_REGEX = r"[-+]?(0[xX])?[\dA-Fa-f]+"
BINARY_REGEX = r"0b[01]+"
FLOAT_REGEX = r"[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?"
STRING_REGEX = r"\"[ \t\w\:]*\""
VARNAME_REGEX = r"[a-zA-Z_]*"
OPERATOR_REGEX = r"[\+\-\*\/]"

token_specification = [
    ("INCLUDE", INCLUDE_REGEX),
    ("DEFINE", DEFINE_REGEX),
    ("TYPEDEF", TYPEDEF_REGEX),
    ("STRUCT", STRUCT_REGEX),
]

token_pattern = "|".join(
    rf"(?P<{name}>{regex})" for (name, regex) in token_specification
)


class Parser:
    def __init__(self):
        self.tokens = []
        self.included_files = []

    def clear(self):
        self.tokens = []
        self.included_files = []

    @property
    def defines(self):
        return {t.name: t.value for t in self.tokens if isinstance(t, Define)}

    @property
    def typedefs(self):
        return {t.alias: t.type for t in self.tokens if isinstance(t, TypeDef)}

    @property
    def structs(self):
        d = {}
        for t in self.tokens:
            if not isinstance(t, Struct):
                continue
            d[t.name] = []
            for f in t.fields:
                d[t.name].append((f.name, f.type_name, f.length))

        return d

    def preprocess(self, text: str) -> str:
        # Strip Inline Comments
        text = re.sub(r"//(.*)\n", r"\n", text)

        # Strip Block Comments
        text = re.sub(r"/\*(.*?)\*/", r"\n", text, flags=re.DOTALL)

        # Strip Tabs
        text = re.sub(r"\t+", " ", text)

        return text

    def expand_macro(self, d: Define):
        # Get the current set of defined macros
        defines = {t.name: t for t in self.tokens if isinstance(t, Define)}

        s = d.expression
        rdepth_limit = 10
        n = 0
        symbol_regex = r"\b(?P<symbol>[a-zA-Z_]+\w*)\b"
        m = re.search(symbol_regex, s)
        while m:
            symbol = m.group()
            n += 1
            try:
                macro = defines[symbol]
            except KeyError:
                raise RuntimeError(
                    f"Unable to expand macro {d.name} -> {symbol} not defined."
                )

            assert (
                re.search(rf"\b{d.name}\b", macro.expression) is None
            ), "Circular reference in macro {d.name}."

            assert (
                macro.value is not None
            ), f"{macro.name} has not been evaluated to a value."

            s = re.sub(rf"\b{macro.name}\b", str(macro.value), s)

            if n > rdepth_limit:
                raise RuntimeError(
                    f"Recursion limit reached expanding macro: {macro.name}"
                )

            # Try to match another macro symbol
            m = re.search(symbol_regex, s)

        # Add the expanded form and evaluated value
        d.expanded = s
        d.value = eval(s)

    def handle_include(self, m: re.Match):
        raw = m.group()
        fname = m.group("include_file").strip()
        token = Include(raw, fname)
        self.tokens.append(token)
        self.parse(fname)

    def handle_define(self, m: re.Match):
        raw = m.group()
        if m.group("macro_name") is not None:
            name = m.group("macro_name").strip()
            exp = m.group("expression").strip()
            if re.match(STRING_REGEX, exp):
                # Const char literal
                token = Define(raw, name, expression=exp, expanded=exp, value=exp)
            else:
                # Expand numerical expression now
                token = Define(raw, name, expression=exp)
                self.expand_macro(token)
        elif m.group("macro_flag") is not None:
            name = m.group("macro_flag").strip()
            value = 1
            token = Define(raw, name, expression="", value=value)
        elif m.group("macro_func") is not None:
            raise SyntaxError(f"Macro functions are not supported: {raw}")
        elif m.group("macro_multi") is not None:
            raise SyntaxError(f"Multiline macros are not supported: {raw}")
        else:
            raise SyntaxError(f"Failed to correctly parse macro: {raw}")

        self.tokens.append(token)

    def handle_typedef(self, m: re.Match):
        raw = m.group()
        alias = m.group("typedef_alias").strip()
        qual1 = (m.group("typedef_qual1") or "").strip()
        qual2 = (m.group("typedef_qual2") or "").strip()
        base_type = m.group("typedef_type").strip()
        ftype = f"{qual1}"
        ftype += f" {qual2}" if qual2 else ""
        ftype += f" {base_type}"
        ftype = ftype.strip()

        struct_types = [t for t in self.tokens if isinstance(t, Struct)]
        typedefs_types = [t for t in self.tokens if isinstance(t, TypeDef)]

        # Find the base type ultimately represented by the typedef alias
        n = 0
        while n < 10:
            if ftype in supported_types:
                self.tokens.append(TypeDef(raw, alias, ftype))
                return

            # Check if ftype points back to another typedef
            for t in typedefs_types:
                if ftype == t.alias:
                    n += 1
                    ftype = t.type

            # Check if ftype points back to a user defined struct
            for s in struct_types:
                if ftype == s.name:
                    ftype = s.name
                    self.tokens.append(TypeDef(raw, alias, ftype))
                    return

            n += 1

        raise RuntimeError(f"Recursion limit exceeded for typedef: {alias}")

    def handle_struct(self, m: re.Match):
        raw = m.group()
        hash = sha256(raw.strip().encode()).hexdigest()
        name = m.group("struct_name").strip()
        token = Struct(raw, hash, name)

        for fmatch in re.finditer(
            FIELD_REGEX,
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
            ftype = ftype.strip()
            len_str = fmatch.group("length") or None
            flen = None

            # Expand the length string if needed
            if len_str is not None:
                defines = {
                    t.name: t.value for t in self.tokens if isinstance(t, Define)
                }
                s = len_str
                symbol_regex = r"\b(?P<symbol>[a-zA-Z_]+\w*)\b"
                mo = re.search(symbol_regex, s)
                while mo:
                    symbol = mo.group()
                    try:
                        value = defines[symbol]
                    except KeyError:
                        raise RuntimeError(
                            f"Unable to expand length expression for struct {name}: field {fname} -> {symbol} not defined."
                        )

                    assert isinstance(value, (int, float))
                    s = re.sub(rf"\b{symbol}\b", str(value), s)

                    # Try to match another macro symbol
                    mo = re.search(symbol_regex, s)

                # Evaluate the length expression
                flen = eval(s)

            token.fields.append(StructField(raw, fname, ftype, len_str, flen))

        self.tokens.append(token)

    def parse(self, msgdefs_file: str):
        if msgdefs_file in self.included_files:
            print(f"{msgdefs_file} already parsed...skipping")
            return

        print(f"Parsing {msgdefs_file}")
        self.included_files.append(msgdefs_file)

        with open(msgdefs_file, "rt") as f:
            text = self.preprocess(f.read())

        with open("test.txt", "wt") as f:
            f.write(text)

        for m in re.finditer(token_pattern, text, flags=re.MULTILINE):
            token_type = m.lastgroup
            print(m.group())
            if token_type == "INCLUDE":
                self.handle_include(m)
            elif token_type == "DEFINE":
                self.handle_define(m)
            elif token_type == "TYPEDEF":
                self.handle_typedef(m)
            elif token_type == "STRUCT":
                self.handle_struct(m)
            else:
                raise RuntimeError("Unknown token type of {token_type} found.")

    def to_json(self):
        return json.dumps(self.tokens, indent=2, cls=CustomEncoder)


class CustomEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if is_dataclass(o):
            return asdict(o)
        return super().default(o)


@dataclass
class Constant:
    name: str
    value: Union[int, str, float]


@dataclass
class MT:
    name: str
    value: int


@dataclass
class MID:
    name: str
    value: int


@dataclass
class TypeAlias:
    alias: str
    type_name: str


@dataclass
class Field:
    name: str
    type_name: str
    length: Optional[int] = None


@dataclass
class MDF:
    hash: str
    name: str
    type_id: MT
    fields: List[Field] = field(default_factory=list)


@dataclass
class SDF:
    hash: str
    name: str
    type_id: MT
    fields: List[Field] = field(default_factory=list)


RTMAObjects = Union[Constant, MT, MID, TypeAlias, MDF, SDF, Field]


class Processor:
    def __init__(self, tokens: List[Tokens]):
        self.constants = {}
        self.MT: Dict[str, str] = {}
        self.MID: Dict[str, str] = {}
        self.typedefs: Dict[str, str] = {}
        self.structs: Dict[str, Struct] = {}

        self.objs: List[RTMAObjects]

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

    def eval_typedef(self, typedef: TypeDef):
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
            elif isinstance(token, TypeDef):
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
