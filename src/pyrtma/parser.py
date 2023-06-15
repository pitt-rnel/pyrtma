import re
import json
import pathlib
import os

from hashlib import sha256
from typing import List, Optional, Any, Union
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
    name: str


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
    name: str
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


Token = Union[Include, Define, TypeDef, Struct]

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

# Combined regex for #define types. Note order matters.
DEFINE_REGEX = (
    rf"{MACRO_MULTI_REGEX}|{MACRO_FUNC_REGEX}|{MACRO_EXP_REGEX}|{MACRO_FLAG_REGEX}"
)

TYPEDEF_REGEX = r"\s*typedef\s+(?P<typedef_qual1>\w+\s+)?\s*(?P<typedef_qual2>\w+\s+)?\s*(?P<typedef_type>\w+\s*)(?P<ptr>(\*\s+)|\s+)(?P<typedef_alias>\*?\w*)\s*;\s*"

FIELD_REGEX = r"\s*(?P<qual1>\w+\s+)?\s*(?P<qual2>\w+\s+)?\s*(?P<typ>\w+\s*)(?P<ptr>(\*\s*)|\s+)(?P<name>\w+)\s*(\[(?P<length>.*?)\])?;"

STRUCT_REGEX = r"(?s:(\s*struct\s+(?P<struct_name>\w*)\s*\{(?P<struct_def>.*?)\}\s*;))"

TYPEDEF_STRUCT_REGEX = r"(?s:(\s*typedef\s+struct\s*\{(?P<td_struct_def>.*?)\}(?P<td_struct_name>\s*\w*)\s*;))"

# Other patterns
INT_REGEX = r"[-+]?(0[xX][\dA-Fa-f]+|0[0-7]*|\d+)"
HEX_REGEX = r"[-+]?(0[xX])?[\dA-Fa-f]+"
BINARY_REGEX = r"0b[01]+"
FLOAT_REGEX = r"[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?"
STRING_REGEX = r"\"(?P<text>[ \t\w\:]*)\""
VARNAME_REGEX = r"[a-zA-Z_]*"
OPERATOR_REGEX = r"[\+\-\*\/]"

token_specification = [
    ("INCLUDE", INCLUDE_REGEX),
    ("DEFINE", DEFINE_REGEX),
    ("TYPEDEF", TYPEDEF_REGEX),
    ("TYPEDEF_STRUCT", TYPEDEF_STRUCT_REGEX),
    ("STRUCT", STRUCT_REGEX),
]

token_pattern = "|".join(
    rf"(?P<{name}>{regex})" for (name, regex) in token_specification
)


class Parser:
    def __init__(self, debug: bool = False):
        self.tokens = []
        self.included_files = []
        self.debug = debug

    def clear(self):
        self.tokens = []
        self.included_files = []

    @property
    def defines(self):
        return {t.name: t.value for t in self.tokens if isinstance(t, Define)}

    @property
    def typedefs(self):
        return {t.name: t.type for t in self.tokens if isinstance(t, TypeDef)}

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
        # exclude rtma_types.h and rtma.h from original rtma
        exclude_dirs = [
            "/rtma/include",
            "\\rtma\\include",
            "/rtma\\include",
            "\\rtma/include",
        ]
        for ed in exclude_dirs:
            if ed in fname.lower():
                return
        self.parse(fname)

    def handle_define(self, m: re.Match):
        raw = m.group()
        if m.group("macro_name") is not None:
            name = m.group("macro_name").strip()
            exp = m.group("expression").strip()
            ms = re.match(STRING_REGEX, exp)
            if ms is not None:
                # Const char literal
                token = Define(
                    raw,
                    name,
                    expression=exp,
                    expanded=exp,
                    value=ms.groupdict()["text"],
                )
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
            raise SyntaxError(f"Multi-line macros are not supported: {raw}")
        else:
            raise SyntaxError(f"Failed to correctly parse macro: {raw}")

        self.tokens.append(token)

    def handle_typedef(self, m: re.Match):
        raw = m.group()

        if "*" in m.group("ptr"):
            raise SyntaxError(f"Typedefs can not reference pointer types: {raw}")

        alias = m.group("typedef_alias").strip()
        if "*" in alias:
            raise SyntaxError(f"Typedefs alias can not be a pointer: {raw}")

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
        prev = ftype
        while n < 10:
            if ftype in supported_types:
                self.tokens.append(TypeDef(raw, alias, ftype))
                return

            # Check if ftype points back to another typedef
            for t in typedefs_types:
                if ftype == t.name:
                    n += 1
                    ftype = t.type

            # Check if ftype points back to a user defined struct
            for s in struct_types:
                if ftype == s.name:
                    ftype = s.name
                    self.tokens.append(TypeDef(raw, alias, ftype))
                    return

            n += 1
            if ftype == prev:
                raise RuntimeError(f"Unable to resolve typedef: {raw}")
            else:
                prev = ftype

        raise RuntimeError(f"Recursion limit exceeded for typedef: {alias}")

    def handle_typedef_struct(self, m: re.Match):
        raw = m.group()
        hash = sha256(raw.strip().encode()).hexdigest()
        name = m.group("td_struct_name").strip()

        if name == "":
            raise SyntaxError(f"Structs must have a name: {raw}")

        token = Struct(raw, hash, name)

        if "struct" in m.groupdict()["td_struct_def"]:
            raise SyntaxError("Anonymous structs are not supported: {name}:{raw}")

        if "union" in m.groupdict()["td_struct_def"]:
            raise SyntaxError("Anonymous unions are not supported: {name}:{raw}")

        for fmatch in re.finditer(
            FIELD_REGEX,
            m.groupdict()["td_struct_def"],
            flags=re.MULTILINE | re.DOTALL,
        ):
            self.print(f"{fmatch.lastgroup}: \n{fmatch.group().strip()}")
            raw = fmatch.group()

            if "*" in fmatch.group("ptr"):
                raise SyntaxError(
                    f"Struct fields can not reference pointer types: {name}:{raw}"
                )

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

                # Cast expression result to an int
                flen = int(flen)

            token.fields.append(StructField(raw, fname, ftype, len_str, flen))

        if len(token.fields) == 0:
            raise SyntaxError(f"Unable to parse field values: {name} -> {raw}")

        self.tokens.append(token)

    def parse_text(self, text: str):
        """Parse the given text for token objects."""
        for m in re.finditer(token_pattern, text, flags=re.MULTILINE):
            token_type = m.lastgroup
            self.print(m.group())
            if token_type == "INCLUDE":
                self.handle_include(m)
            elif token_type == "DEFINE":
                self.handle_define(m)
            elif token_type == "TYPEDEF":
                self.handle_typedef(m)
            elif token_type == "TYPEDEF_STRUCT":
                self.handle_typedef_struct(m)
            elif token_type == "STRUCT":
                raise SyntaxError(f"Only typedef structs are supported: {m.group()}")
            else:
                raise RuntimeError("Unknown token type of {token_type} found.")

    def parse(self, msgdefs_file: str):
        # Get the current pwd
        cwd = pathlib.Path.cwd()

        # Set the pwd to the directory containing the msgdef file
        defs_path = pathlib.Path(msgdefs_file)
        def_dir = pathlib.Path(msgdefs_file).parent
        os.chdir(str(def_dir.absolute()))

        if msgdefs_file in self.included_files:
            self.print(f"{msgdefs_file} already parsed...skipping")
            return

        self.print(f"Parsing {msgdefs_file}")
        self.included_files.append(msgdefs_file)

        with open(defs_path.name, "rt") as f:
            text = self.preprocess(f.read())

        self.parse_text(text)

        # Set pwd back to starting point
        os.chdir(cwd.absolute())

    def to_json(self):
        return json.dumps(self.tokens, indent=2, cls=CustomEncoder)

    def print(self, text):
        if self.debug:
            print(text)


class CustomEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if is_dataclass(o):
            return asdict(o)
        return super().default(o)
