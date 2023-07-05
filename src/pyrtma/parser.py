import re
import json
import pathlib
import os
import textwrap
import yaml

from copy import copy
from hashlib import sha256
from typing import List, Optional, Any, Union, Tuple, Dict
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
    "uint8",
    "uint16",
    "uint32",
    "uint64",
    "int8",
    "int16",
    "int32",
    "int64",
]


@dataclass
class Import:
    file: pathlib.Path
    src: pathlib.Path


@dataclass
class ConstantExpr:
    name: str
    expression: str
    expanded: Optional[str]
    value: Union[str, int, float]
    src: pathlib.Path


@dataclass
class ConstantString:
    name: str
    value: str
    src: pathlib.Path


@dataclass
class MT:
    name: str
    value: int
    src: pathlib.Path


@dataclass
class MID:
    name: str
    value: int
    src: pathlib.Path


@dataclass
class HID:
    name: str
    value: int
    src: pathlib.Path


@dataclass
class TypeAlias:
    name: str
    type_name: str
    src: pathlib.Path


@dataclass
class Field:
    name: str
    type_name: str
    length_expression: Optional[str] = None
    length_expanded: Optional[str] = None
    length: Optional[int] = None


@dataclass
class MDF:
    raw: str
    hash: str
    name: str
    type_id: int
    src: pathlib.Path
    fields: List[Field] = field(default_factory=list)

    @property
    def signal(self) -> bool:
        return len(self.fields) > 0


@dataclass
class SDF:
    raw: str
    hash: str
    name: str
    src: pathlib.Path
    fields: List[Field] = field(default_factory=list)


RTMAObjects = Union[ConstantExpr, ConstantString, HID, MID, TypeAlias, MDF, SDF, Field]


class Parser:
    def __init__(self, debug: bool = False):
        self.included_files = []
        self.current_file = pathlib.Path()
        self.debug = debug

        self.imports: List[Import] = []
        self.constants: Dict[str, ConstantExpr] = {}
        self.string_constants: Dict[str, ConstantString] = {}
        self.aliases: Dict[str, TypeAlias] = {}
        self.host_ids: Dict[str, HID] = {}
        self.module_ids: Dict[str, MID] = {}
        self.struct_defs: Dict[str, SDF] = {}
        self.message_ids: Dict[str, MT] = {}
        self.message_defs: Dict[str, MDF] = {}

    def clear(self):
        self.current_file = pathlib.Path()
        self.included_files = []
        self.imports = []
        self.constants = {}
        self.string_constants: Dict[str, ConstantString] = {}
        self.aliases = {}
        self.host_ids = {}
        self.module_ids = {}
        self.struct_defs = {}
        self.message_ids = {}
        self.message_defs = {}

    def expand_expression(self, name: str, expr: str) -> Tuple[str, int]:
        rdepth_limit = 10
        n = 0
        symbol_regex = r"\b(?P<symbol>[a-zA-Z_]+\w*)\b"
        m = re.search(symbol_regex, expr)
        while m:
            symbol = m.group()
            n += 1
            try:
                c = self.constants[symbol]
            except KeyError:
                raise RuntimeError(
                    f"Unable to expand expression {name} -> {symbol} not defined: {self.current_file.absolute()}"
                )

            assert (
                re.search(rf"\b{name}\b", c.expression) is None
            ), "Circular reference in macro {d.name}."

            assert c.value is not None, f"{c.name} has not been evaluated to a value."

            expr = re.sub(rf"\b{c.name}\b", str(c.value), expr)

            if n > rdepth_limit:
                raise RuntimeError(
                    f"Recursion limit reached expanding constant expression {name} in {self.current_file.absolute()}"
                )

            # Try to match another macro symbol
            m = re.search(symbol_regex, expr)

        # Add the expanded form and evaluated value
        expanded = expr

        # TODO: check that only numbers and operators are left in expression
        value = eval(expr)

        return expanded, value

    def handle_import(self, fname: str):
        imp = Import(pathlib.Path(fname), src=self.current_file)
        self.imports.append(imp)
        self.parse_file(imp.file.absolute())

    def handle_expression(self, name: str, expression: Union[int, float, str]):
        for c in self.constants.values():
            if name == c.name:
                raise SyntaxError(
                    f"Duplicate constant conflict found for {name} in \n1: {c.src.absolute()}\n2: {self.current_file.absolute()}\n"
                )

        # Expand numerical expression now
        if isinstance(expression, (int, float)):
            self.constants[name] = ConstantExpr(
                name,
                expression=str(expression),
                expanded=str(expression),
                value=expression,
                src=self.current_file,
            )
        elif isinstance(expression, str):
            expanded, value = self.expand_expression(name, expression)
            self.constants[name] = ConstantExpr(
                name,
                expression=expression,
                expanded=expanded,
                value=value,
                src=self.current_file,
            )

    def handle_string(self, name: str, value: str):
        for c in self.string_constants.values():
            raise SyntaxError(
                f"Duplicate string_constant conflict found for {name} in \n1: {c.src.absolute()}\n2: {self.current_file.absolute()}\n"
            )

        if not isinstance(value, str):
            raise SyntaxError(
                f"Values in 'string_constants' section must evaluate to string type not {type(value)}. {name}: {value} -> {self.current_file.absolute()}"
            )

        self.string_constants[name] = ConstantString(
            name, value=f'"{value}"', src=self.current_file
        )

    def handle_alias(self, alias: str, ftype: str):
        for a in self.aliases.values():
            if alias == a.name:
                raise SyntaxError(
                    f"Duplicate type_alias conflict found for {alias} in: \n1: {a.src.absolute()}\n2: {self.current_file.absolute()}\n"
                )

        # Find the base type ultimately represented by the typedef alias
        n = 0
        prev = ftype
        while n < 10:
            if ftype in supported_types:
                self.aliases[alias] = TypeAlias(alias, ftype, self.current_file)
                return

            # Check if ftype points back to a user defined struct
            for sdf in self.struct_defs.values():
                if ftype == sdf.name:
                    ftype = sdf.name
                    self.aliases[alias] = TypeAlias(alias, ftype, src=self.current_file)
                    return

            # Check if ftype points back to another typedef
            for a in self.aliases.values():
                if ftype == a.name:
                    n += 1
                    ftype = a.type_name

            if ftype == prev:
                raise RuntimeError(f"Unable to resolve alias: {ftype}")
            else:
                prev = ftype

        raise RuntimeError(f"Recursion limit exceeded for typedef: {alias}")

    def handle_host_id(self, name: str, value: int):
        if not isinstance(value, int):
            raise SyntaxError(
                f"Values in 'host_ids' section must evaluate to int type not {type(value)}. {name}: {value}"
            )

        if value < 10 or value > 32767:
            if self.current_file.name != "core_defs.yaml":
                raise SyntaxError(
                    f"Value outside of valid range [0 - 32767] for host_id: {name}: {value}"
                )

        for hid in self.host_ids.values():
            if value == hid.value:
                raise SyntaxError(
                    f"Duplicate host id conflict found for {name} and {hid.name} -> {value}\n1: {hid.src.absolute()}\n2: {self.current_file.absolute()}\n"
                )
        self.host_ids[name] = HID(name, int(value), src=self.current_file)

    def handle_module_id(self, name: str, value: int):
        if not isinstance(value, int):
            raise SyntaxError(
                f"Values in 'module_ids' section must evaluate to int type not {type(value)}. {name}: {value} -> {self.current_file.absolute()}"
            )

        if value < 10 or value > 99:
            if self.current_file.name != "core_defs.yaml":
                raise SyntaxError(
                    f"Value outside of valid range [100 - 200] for module_id: {name}: {value} -> {self.current_file.absolute()}"
                )

        for mid in self.module_ids.values():
            if value == mid.value:
                raise SyntaxError(
                    f"Duplicate host id conflict found for {name} and {mid.name} -> {value}\n1: {mid.src.absolute()}\n2: {self.current_file.absolute()}\n"
                )

        self.module_ids[name] = MID(name, int(value), src=self.current_file)

    def handle_def(self, def_type: str, name: str, mdf: Dict[str, Any]):
        is_signal_def = mdf["fields"] is None
        is_struct_def = False

        # Check the schema
        if def_type == "msg_def":
            valid_sections = ("id", "fields")
        elif def_type == "struct_def":
            valid_sections = ("fields",)
            is_struct_def = True
        else:
            raise RuntimeError(f"Unknown struct type section {def_type}.")

        for section in mdf.keys():
            if section not in valid_sections:
                raise SyntaxError(
                    f"Invalid top-level section '{section}' in message or struct definition of {name} -> {self.current_file.absolute()}."
                )

        # Create a string representation of the defintion to hash
        if is_signal_def:
            raw = f"{name}:\n  id: {mdf['id']}\n  fields: null"
        elif is_struct_def:
            f = [f"    {fname}: {ftype}" for fname, ftype in mdf["fields"].items()]
            f = "\n".join(f)
            raw = f"{name}:\n  fields:\n{f}"
        else:
            f = [f"    {fname}: {ftype}" for fname, ftype in mdf["fields"].items()]
            f = "\n".join(f)
            raw = f"{name}:\n  id: {mdf['id']}\n  fields:\n{f}"

        raw = textwrap.dedent(raw)
        hash = sha256(raw.encode()).hexdigest()

        if is_struct_def:
            obj = SDF(raw, hash, name, src=self.current_file)
        else:
            obj = MDF(raw, hash, name, type_id=mdf["id"], src=self.current_file)
            if is_signal_def:
                self.message_defs[name] = obj
                return

        # Check and validate message id
        if not is_struct_def:
            msg_id = mdf["id"]
            if not isinstance(msg_id, int):
                raise SyntaxError(
                    f"Message definition id must evaluate to int type not {msg_id}. {name}: {msg_id}"
                )

            if msg_id < 0 or msg_id > 10000:
                raise SyntaxError(
                    "Value outside of valid range [0 - 10000] for module_id: {name}: {value}"
                )

            for mt in self.message_ids.values():
                if msg_id == mt.value:
                    raise SyntaxError(
                        f"Duplicate message ids conflict found for {mt.name} and {name}: {msg_id} ->\n1: {mt.src.absolute()}\n2: {self.current_file.absolute()}\n"
                    )

            self.message_ids[name] = MT(name, msg_id, src=self.current_file)

        # Pattern to parse field specs
        FIELD_REGEX = r"\s*(?P<ftype>[\s\w]*)(\[(?P<len_str>.*)\])?"

        # Copy fields from another definition
        if isinstance(mdf["fields"], str):
            type_name = mdf["fields"]
            df = self.message_defs.get(type_name) or self.struct_defs.get(type_name)
            if df is None:
                raise SyntaxError(
                    f"Unable to find definition for {type_name} in {name} -> {self.current_file.absolute()}"
                )

            for field in df.fields:
                obj.fields.append(copy(field))

        # Parse field specs into Field objects
        reserved_field_names = ("type_id", "type_name", "type_hash")

        for fname, fstr in mdf["fields"].items():
            if fname in reserved_field_names:
                raise SyntaxError(f"{fname} is a reserved field name for internal use.")

            if not isinstance(fstr, str):
                raise SyntaxError(
                    f"Field types must be a string not type not {type(fstr)}: {name}=> {fname}: {fstr} -> {self.current_file.absolute()}"
                )

            m = re.match(FIELD_REGEX, fstr)
            if m is None:
                raise SyntaxError(
                    f"Invalid syntax for field type specification: {name}=> {fname}: {fstr} -> {self.current_file.absolute()}"
                )

            ftype = m.groupdict()["ftype"].strip()
            len_str = (m.groupdict()["len_str"] or "").strip()

            if ftype is None:
                raise SyntaxError(
                    f"Invalid syntax for field type specification: {name}=> {fname}: {fstr} -> {self.current_file.absolute()}"
                )

            if len_str == "" and "[" in fstr:
                raise SyntaxError(
                    f"Invalid syntax for array field length: {name}=> {fname}: {fstr} -> {self.current_file.absolute()}"
                )

            # Check for a valid type
            if ftype not in supported_types:
                if ftype not in self.aliases.keys():
                    if ftype not in self.struct_defs.keys():
                        if ftype not in self.message_defs.keys():
                            raise SyntaxError(
                                f"Unknown type specified ({ftype}): {name}=> {fname}: {fstr} -> {self.current_file.absolute()}"
                            )

            # Expand the length string if needed
            if len_str:
                expanded, flen = self.expand_expression(f"{name}->{fname}", len_str)
                obj.fields.append(Field(fname, ftype, len_str, expanded, int(flen)))
            else:
                obj.fields.append(Field(fname, ftype))

        if isinstance(obj, SDF):
            self.struct_defs[name] = obj
        else:
            self.message_defs[name] = obj

    def parse_text(self, text: str):
        # Parse the yaml file
        data = yaml.load(text, Loader=yaml.Loader)

        valid_sections = (
            "imports",
            "constants",
            "string_constants",
            "aliases",
            "host_ids",
            "module_ids",
            "struct_defs",
            "message_defs",
        )

        # Check file format
        for section in valid_sections:
            if section not in data.keys():
                raise SyntaxError(
                    f"Missing top-level section '{section}' in message defs file -> {self.current_file.absolute()}."
                )

        if data["imports"] is not None:
            for imp in data["imports"]:
                self.handle_import(imp)

        if data["constants"] is not None:
            for name, expr in data["constants"].items():
                self.handle_expression(name, expr)

        if data["string_constants"] is not None:
            for name, str_const in data["string_constants"].items():
                self.handle_string(name, str_const)

        if data["aliases"] is not None:
            for alias, ftype in data["aliases"].items():
                self.handle_alias(alias, ftype)

        if data["host_ids"] is not None:
            for name, value in data["host_ids"].items():
                self.handle_host_id(name, value)

        if data["module_ids"] is not None:
            for name, value in data["module_ids"].items():
                self.handle_module_id(name, value)

        if data["struct_defs"] is not None:
            for name, sdf in data["struct_defs"].items():
                self.handle_def("struct_def", name, sdf)

        if data["message_defs"] is not None:
            for name, mdf in data["message_defs"].items():
                self.handle_def("msg_def", name, mdf)

    def parse(self, msgdefs_file: os.PathLike):
        try:
            # Always start by parsing the core_defs.yaml file
            pkg_dir = pathlib.Path(os.path.realpath(__file__)).parent
            core_defs = pkg_dir / "core_defs/core_defs.yaml"
            self.parse_file(core_defs.absolute())

            defs_path = pathlib.Path(msgdefs_file)
            self.parse_file(defs_path.absolute())

        except Exception as e:
            self.clear()
            raise

    def parse_file(self, msgdefs_file: pathlib.Path):

        # check previously included files
        if msgdefs_file in self.included_files:
            print(f"{msgdefs_file} already parsed...skipping")
            return

        print(f"Parsing {msgdefs_file}")
        prev_file = self.current_file
        self.current_file = msgdefs_file
        self.included_files.append(msgdefs_file)

        with open(msgdefs_file, "rt") as f:
            text = f.read()

        self.parse_text(text)
        self.current_file = prev_file

    def to_json(self):
        d = dict(
            imports=self.imports,
            constants=self.constants,
            string_constants=self.string_constants,
            host_ids=self.host_ids,
            module_ids=self.module_ids,
            aliases=self.aliases,
            struct_defs=self.struct_defs,
            message_defs=self.message_defs,
        )
        return json.dumps(d, indent=2, cls=CustomEncoder)

    def print(self, text):
        if self.debug:
            print(text)


class CustomEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if is_dataclass(o):
            return asdict(o)
        if isinstance(o, pathlib.Path):
            return str(o.absolute())
        return super().default(o)
