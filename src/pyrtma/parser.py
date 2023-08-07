import re
import json
import pathlib
import os
import textwrap
import struct
import logging
import string

# import yaml
from ruamel.yaml import YAML

from copy import copy
from hashlib import sha256
from typing import List, Optional, Any, Union, Tuple, Dict
from dataclasses import dataclass, field, is_dataclass, asdict


@dataclass
class NativeType:
    name: str
    size: int
    format: str


# Native C types and sizes that are supported
supported_types = {
    "char": NativeType(name="char", size=1, format="c"),
    "signed char": NativeType(name="signed_char", size=1, format="b"),
    "unsigned char": NativeType(name="unsigned char", size=1, format="B"),
    "byte": NativeType(name="byte", size=1, format="B"),
    "int": NativeType(name="int", size=4, format="i"),
    "signed int": NativeType(name="signed int", size=4, format="i"),
    "unsigned int": NativeType(name="unsigned int", size=4, format="I"),
    "unsigned": NativeType(name="unsigned", size=4, format="I"),
    "short": NativeType(name="short", size=2, format="h"),
    "signed short": NativeType(name="signed short", size=2, format="h"),
    "unsigned short": NativeType(name="unsigned short", size=2, format="H"),
    "long": NativeType(name="long", size=4, format="i"),
    "signed long": NativeType(name="signed long", size=4, format="i"),
    "unsigned long": NativeType(name="unsigned long", size=4, format="I"),
    "long long": NativeType(name="long long", size=8, format="q"),
    "signed long long": NativeType(name="signed long long", size=8, format="q"),
    "unsigned long long": NativeType(name="unsigned long long", size=8, format="Q"),
    "float": NativeType(name="float", size=4, format="f"),
    "double": NativeType(name="double", size=8, format="d"),
    "uint8": NativeType(name="uint8", size=1, format="B"),
    "uint16": NativeType(name="uint16", size=2, format="H"),
    "uint32": NativeType(name="uint32", size=4, format="I"),
    "uint64": NativeType(name="uint64", size=8, format="Q"),
    "int8": NativeType(name="int8", size=1, format="b"),
    "int16": NativeType(name="int16", size=2, format="h"),
    "int32": NativeType(name="int32", size=4, format="i"),
    "int64": NativeType(name="int64", size=8, format="q"),
}


class ParserError(Exception):
    """Base class for all parser exceptions"""

    pass


class YAMLSyntaxError(ParserError):
    """Raised when the parser encounters invalid YAML"""

    pass


class RTMASyntaxError(ParserError):
    """Raised when the parser encounters invalid RTMA syntax"""

    pass


class HostIDError(ParserError):
    """Raised when the a host id is already in use"""

    pass


class ModuleIDError(ParserError):
    """Raised when the a module id is already in use"""

    pass


class DuplicateNameError(ParserError):
    """Raised when the a name is already in use"""

    pass


class MessageIDError(ParserError):
    """Raised when the a message id is already in use"""

    pass


class CircularRefError(ParserError):
    """Raised when an expression contains a circular reference"""

    pass


class ExpressionExpansionError(ParserError):
    """Raised when an expression can not be expanded."""

    pass


class RecurisionError(ParserError):
    """Raised when recursion limit is exceeded evaluating aliases and expressions."""

    pass


class InvalidTypeError(ParserError):
    """Raised when a field contains the wrong type of data"""

    pass


class FileFormatError(ParserError):
    """Raised when the wrong file extension is referenced."""

    pass


class AlignmentError(ParserError):
    """Raised when a struct is not 64-bit aligned"""

    pass


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
    type_obj: Union[NativeType, "SDF"]
    src: pathlib.Path

    @property
    def size(self) -> int:
        return self.type_obj.size

    @property
    def boundary(self) -> int:
        if isinstance(self.type_obj, NativeType):
            return self.type_obj.size
        else:
            return self.type_obj.boundary

    @property
    def format(self) -> str:
        return self.type_obj.format


@dataclass
class Field:
    name: str
    type_name: str
    type_obj: Union[NativeType, TypeAlias, "MDF", "SDF"]
    length_expression: Optional[str] = None
    length_expanded: Optional[str] = None
    length: Optional[int] = None

    @property
    def base_size(self) -> int:
        return self.type_obj.size

    @property
    def size(self):
        return self.type_obj.size * (self.length or 1)

    @property
    def boundary(self) -> int:
        if isinstance(self.type_obj, NativeType):
            return self.type_obj.size
        else:
            return self.type_obj.boundary

    @property
    def format(self) -> str:
        if self.length:
            return self.length * self.type_obj.format
        else:
            return self.type_obj.format


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

    @property
    def size(self) -> int:
        return sum([f.size for f in self.fields])

    @property
    def boundary(self) -> int:
        f0 = self.fields[0]
        if isinstance(f0.type_obj, NativeType):
            return f0.type_obj.size
        else:
            return f0.type_obj.boundary

    @property
    def format(self) -> str:
        s = ""
        for field in self.fields:
            s += field.format

        return s


@dataclass
class SDF:
    raw: str
    hash: str
    name: str
    src: pathlib.Path
    fields: List[Field] = field(default_factory=list)

    @property
    def size(self) -> int:
        return sum([f.size for f in self.fields])

    @property
    def boundary(self) -> int:
        f0 = self.fields[0]
        if isinstance(f0.type_obj, NativeType):
            return f0.type_obj.size
        else:
            return f0.type_obj.boundary

    @property
    def format(self) -> str:
        s = ""
        for field in self.fields:
            s += field.format

        return s


RTMAObject = Union[ConstantExpr, ConstantString, HID, MID, TypeAlias, MDF, SDF, Field]


class Parser:
    def __init__(self, debug: bool = False):
        self.included_files = []
        self.current_file = pathlib.Path()
        self.debug = debug

        self.yaml_dict = dict(
            imports={},
            constants={},
            string_constants={},
            host_ids={},
            module_ids={},
            aliases={},
            struct_defs={},
            message_defs={},
        )

        self.imports: List[Import] = []
        self.constants: Dict[str, ConstantExpr] = {}
        self.string_constants: Dict[str, ConstantString] = {}
        self.aliases: Dict[str, TypeAlias] = {}
        self.host_ids: Dict[str, HID] = {}
        self.module_ids: Dict[str, MID] = {}
        self.struct_defs: Dict[str, SDF] = {}
        self.message_ids: Dict[str, MT] = {}
        self.message_defs: Dict[str, MDF] = {}

        self.logger = logging.getLogger("pyrtma.parser")
        self.logger.propagate = False
        if self.debug:
            self.logger.setLevel(logging.DEBUG)
        else:
            self.logger.setLevel(logging.INFO)

        fmt = "{levelname:<6} - {message}"
        formatter = logging.Formatter(fmt, style="{")
        console = logging.StreamHandler()
        console.setLevel(logging.DEBUG)
        console.setFormatter(formatter)
        self.logger.addHandler(console)

    def warning(self, msg: str):
        self.logger.warning(msg)
        input("Hit enter to continue...")

    def clear(self):
        self.current_file = pathlib.Path()
        self.yaml_dict = dict(
            imports={},
            constants={},
            string_constants={},
            host_ids={},
            module_ids={},
            aliases={},
            struct_defs={},
            message_defs={},
        )
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

    def check_duplicate_name(
        self, section: str, name: str, namespaces: Tuple[str, ...]
    ):
        """Check namespaces for conflicting names."""
        for namespace in namespaces:
            ns = getattr(self, namespace)
            for o in ns.values():
                if name == o.name:
                    raise DuplicateNameError(
                        f"Duplicate name conflict found: \n\n1: {namespace} -> {o.name} -> {o.src.absolute()}\n2: {section} -> {name} -> {self.current_file}\n"
                    )

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
                raise ExpressionExpansionError(
                    f"Unable to expand expression {name} -> {symbol} not defined: {self.current_file}"
                )

            if re.search(rf"\b{name}\b", c.expression) is not None:
                raise CircularRefError(
                    f"Circular reference in expression: {name} -> {expr}."
                )

            if c.value is None:
                raise ExpressionExpansionError(
                    f"{c.name} has not been evaluated to a value."
                )

            expr = re.sub(rf"\b{c.name}\b", str(c.value), expr)

            if n > rdepth_limit:
                raise RecursionError(
                    f"Recursion limit reached expanding constant expression {name} in {self.current_file}"
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
        if imp.file.is_dir():
            raise FileFormatError(
                f"Imports must be yaml files, not directories. -> {self.current_file}"
            )
        if not imp.file.suffix.lower() in [".yaml", ".yml"]:
            raise FileFormatError(f"Imports must be .yaml files -> {self.current_file}")

        if imp.file.suffix == ".yml":
            self.warning(f"Please change {imp.file} to use '.yaml' extension.")

        self.parse_file(imp.file.absolute())

    def handle_expression(self, name: str, expression: Union[int, float, str]):
        self.check_name(name)
        self.check_duplicate_name(
            "constants",
            name,
            namespaces=(
                "constants",
                "string_constants",
                "aliases",
                "struct_defs",
                "message_defs",
            ),
        )

        if not isinstance(expression, (int, float, str)):
            raise InvalidTypeError(
                f"Values in 'constants' section must be of type int, float, or string not{type(expression).__name__}. {name} -> {self.current_file}"
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
        self.check_name(name)
        self.check_duplicate_name(
            "string_constants",
            name,
            namespaces=(
                "constants",
                "string_constants",
                "aliases",
                "struct_defs",
                "message_defs",
            ),
        )

        if not isinstance(value, str):
            raise RTMASyntaxError(
                f"Values in 'string_constants' section must evaluate to string type not {type(value)}. {name}: {value} -> {self.current_file}"
            )

        self.string_constants[name] = ConstantString(
            name, value=f'"{value}"', src=self.current_file
        )

    def handle_alias(self, alias: str, ftype: str):
        """Find the base type ultimately represented by the typedef alias"""
        if not isinstance(ftype, str):
            raise InvalidTypeError(
                f"Values in 'aliases' section must be a string not {type(ftype).__name__}.\n{alias} -> {self.current_file}"
            )

        self.check_name(alias)
        self.check_duplicate_name(
            "aliases",
            alias,
            namespaces=(
                "constants",
                "string_constants",
                "aliases",
                "struct_defs",
                "message_defs",
            ),
        )

        n = 0
        prev = ftype
        while n < 10:
            if ftype in supported_types.keys():
                self.aliases[alias] = TypeAlias(
                    alias, ftype, supported_types[ftype], self.current_file
                )
                return

            # Check if ftype points back to a user defined struct
            for sdf in self.struct_defs.values():
                if ftype == sdf.name:
                    ftype = sdf.name
                    self.aliases[alias] = TypeAlias(
                        alias, ftype, sdf, src=self.current_file
                    )
                    return

            # Check if ftype points back to another typedef
            for a in self.aliases.values():
                if ftype == a.name:
                    n += 1
                    ftype = a.type_name

            if ftype == prev:
                raise RTMASyntaxError(f"Unable to resolve alias {alias}: {ftype}")
            else:
                prev = ftype

        raise RecursionError(f"Recursion limit exceeded for alias: {alias}")

    def handle_host_id(self, name: str, value: int):
        self.check_name(name)
        self.check_duplicate_name("host_ids", name, namespaces=("host_ids",))

        if not isinstance(value, int):
            raise InvalidTypeError(
                f"Values in 'host_ids' section must evaluate to int type not {type(value).__name__}. {name}: {value}"
            )

        if value < 10 or value > 32767:
            if self.current_file.name != "core_defs.yaml":
                raise RTMASyntaxError(
                    f"Value outside of valid range [0 - 32767] for host_id: {name}: {value}"
                )

        for hid in self.host_ids.values():
            if value == hid.value:
                raise HostIDError(
                    f"Duplicate host id conflict found for {name} and {hid.name} -> {value}\n1: {hid.src.absolute()}\n2: {self.current_file}\n"
                )
        self.host_ids[name] = HID(name, int(value), src=self.current_file)

    def handle_module_id(self, name: str, value: int):
        self.check_name(name)
        self.check_duplicate_name("module_ids", name, namespaces=("module_ids",))

        if not isinstance(value, int):
            raise InvalidTypeError(
                f"Values in 'module_ids' section must evaluate to int type not {type(value).__name__}. {name}: {value} -> {self.current_file}"
            )

        if value < 10 or (99 < value < 200):
            if self.current_file.name != "core_defs.yaml" and value != 0:
                raise RTMASyntaxError(
                    f"Value outside of valid range [10 - 99 or > 200] for module_id: {name}: {value} -> {self.current_file}"
                )

        for mid in self.module_ids.values():
            if value == mid.value:
                raise ModuleIDError(
                    f"Duplicate module id conflict found for {name} and {mid.name} -> {value}\n1: {mid.src.absolute()}\n2: {self.current_file}\n"
                )

        self.module_ids[name] = MID(name, int(value), src=self.current_file)

    def check_alignment(self, s: Union[SDF, MDF], auto_pad: bool = True):
        """Confirm 64 bit alignment of structures"""
        npad = 0
        ptr = 0
        n = 0
        while n < len(s.fields):
            field = s.fields[n]
            boundary = field.boundary
            if ptr % boundary != 0:
                if not auto_pad:
                    raise AlignmentError(
                        f"{s.name}.{field.name} does not start on a valid memory boundary for type: {field.type_name}. Add padding fields prior for 64-bit alignment."
                    )
                else:
                    length = boundary - (ptr % boundary)
                    padding = Field(
                        name=f"padding_{npad}_",
                        type_name="char",
                        type_obj=supported_types["char"],
                        length_expression=f'"{length}"',
                        length_expanded=f'"{length}"',
                        length=length,
                    )

                    self.warning(
                        f"Adding {length} padding byte(s) before {s.name}.{field.name}."
                    )
                    s.fields.insert(n, padding)
                    n += 2
                    npad += 1
                    ptr += padding.size
                    ptr += field.size
            else:
                n += 1
                ptr += field.size

        # Align the end of the struct to 64 bit pointer boundary.
        # if ptr % 8 != 0:
        #     length = 8 - (ptr % 8)
        #     if length == 1:
        #         length = ""

        #     padding = Field(
        #         name=f"padding_{npad}_",
        #         type_name="char",
        #         type_obj=supported_types["char"],
        #         length_expression=f'"{length}"',
        #         length_expanded=f'"{length}"',
        #         length=length or None,
        #     )
        #     s.fields.append(padding)
        #     self.warning(f"WARNING: Adding {length} trailing padding byte(s) at end of {s.name}.")

        # Final size check using Python's builtin struct module
        assert s.size == struct.calcsize(
            s.format
        ), f"{s.name} is not 64-bit aligned. s.size = {s.size}, struct size = {struct.calcsize(s.format)}."

    def validate_msg_id(self, name: str, msg_id: int):
        if not isinstance(msg_id, int):
            raise InvalidTypeError(
                f"Message definition id must evaluate to int type not {type(msg_id).__name__}. {name}: {msg_id}"
            )

        if msg_id < 0 or msg_id > 10000:
            raise RTMASyntaxError(
                "Value outside of valid range [0 - 10000] for module_id: {name}: {value}"
            )

        for mt in self.message_ids.values():
            if msg_id == mt.value:
                raise MessageIDError(
                    f"Duplicate message ids conflict found for {mt.name} and {name}: {msg_id} ->\n1: {mt.src.absolute()}\n2: {self.current_file}\n"
                )

    def validate_msg_def(self, mdf):
        # Check number of fields > 0
        assert (
            len(mdf.fields) > 0
        ), f"Message and Struct definitions must have at least one field: {mdf.name} -> {self.current_file}"

        # Check memory alignment layout
        self.check_alignment(mdf, auto_pad=True)

    def add_fields(self, mdf: Union[SDF, MDF], fields: Union[Dict, str]):
        # Pattern to parse field specs
        FIELD_REGEX = r"\s*(?P<ftype>[\s\w]*)(\[(?P<len_str>.*)\])?"

        # Copy fields from another definition
        if isinstance(fields, str):
            type_name = fields
            df = self.message_defs.get(type_name) or self.struct_defs.get(type_name)
            if df is None:
                raise RTMASyntaxError(
                    f"Unable to find definition for {type_name} in {mdf.name} -> {self.current_file}"
                )

            for field in df.fields:
                mdf.fields.append(copy(field))
        elif isinstance(fields, dict):
            # Parse field specs into Field objects
            reserved_field_names = (
                "type_id",
                "type_name",
                "type_hash",
                "type_source",
                "type_def",
            )

            for fname, fstr in fields.items():
                if fname in reserved_field_names:
                    raise RTMASyntaxError(
                        f"{fname} is a reserved field name for internal use."
                    )

                if not isinstance(fstr, str):
                    raise InvalidTypeError(
                        f"Field types must be a string not type not {type(fstr).__name__}: {mdf.name}=> {fname}: {fstr} -> {self.current_file}"
                    )

                m = re.match(FIELD_REGEX, fstr)
                if m is None:
                    raise RTMASyntaxError(
                        f"Invalid syntax for field type specification: {mdf.name}=> {fname}: {fstr} -> {self.current_file}"
                    )

                ftype = m.groupdict()["ftype"].strip()
                len_str = (m.groupdict()["len_str"] or "").strip()

                if ftype is None:
                    raise RTMASyntaxError(
                        f"Invalid syntax for field type specification: {mdf.name}=> {fname}: {fstr} -> {self.current_file}"
                    )

                if len_str == "" and "[" in fstr:
                    raise RTMASyntaxError(
                        f"Invalid syntax for array field length: {mdf.name}=> {fname}: {fstr} -> {self.current_file}"
                    )

                # Check for a valid type
                if ftype in supported_types.keys():
                    ftype_obj = supported_types[ftype]
                elif ftype in self.aliases.keys():
                    ftype_obj = self.aliases[ftype]
                elif ftype in self.struct_defs.keys():
                    ftype_obj = self.struct_defs[ftype]
                elif ftype in self.message_defs.keys():
                    ftype_obj = self.message_defs[ftype]
                else:
                    raise RTMASyntaxError(
                        f"Unknown type specified ({ftype}): {mdf.name}=> {fname}: {fstr} -> {self.current_file}"
                    )

                # Check for invalid signal def usage
                if ftype in self.message_defs.keys():
                    assert (
                        len(self.message_defs[ftype].fields) != 0
                    ), f"Signal definitions can not be used as field types: {mdf.name}=> {fname}:{fstr} -> {self.current_file}"

                # Expand the length string if needed
                if len_str:
                    expanded, flen = self.expand_expression(
                        f"{mdf.name}->{fname}", len_str
                    )
                    new_field = Field(
                        name=fname,
                        type_name=ftype,
                        type_obj=ftype_obj,
                        length_expression=len_str,
                        length_expanded=expanded,
                        length=int(flen),
                    )
                else:
                    new_field = Field(name=fname, type_name=ftype, type_obj=ftype_obj)

                mdf.fields.append(new_field)
        else:
            raise InvalidTypeError(
                f"Invalid object for field spec of {type(mdf).__name__}. {mdf.name} -> {self.current_file}"
            )

        self.validate_msg_def(mdf)

    def handle_signal(self, name: str, mdf: Dict[str, Any]):
        # Create a string representation of the defintion to hash
        raw = f"{name}:\n  id: {mdf['id']}\n  fields: null"
        raw = textwrap.dedent(raw)
        hash = sha256(raw.encode()).hexdigest()

        # Check and validate message id
        msg_id = mdf["id"]
        self.validate_msg_id(name, msg_id)
        self.message_ids[name] = MT(name, msg_id, src=self.current_file)

        # Create the MDF data class
        obj = MDF(raw, hash, name, type_id=mdf["id"], src=self.current_file)

        # Store the new definition
        self.message_defs[name] = obj
        return

    def handle_struct(self, name: str, sdf: Dict[str, Any]):
        # Check for valid name
        self.check_name(name)

        self.check_duplicate_name(
            "struct_defs",
            name,
            namespaces=(
                "constants",
                "string_constants",
                "aliases",
                "struct_defs",
                "message_defs",
            ),
        )

        if not isinstance(sdf, dict):
            raise InvalidTypeError(
                f"Invalid object type for struct def {name} of {type(sdf).__name__} -> {self.current_file}"
            )

        # Check for correct section headers
        valid_sections = ("fields",)
        for section in sdf.keys():
            if section not in valid_sections:
                raise RTMASyntaxError(
                    f"Invalid top-level section '{section}' in message or struct definition of {name} -> {self.current_file}."
                )

        # Create a string representation of the defintion to hash
        if isinstance(sdf["fields"], str):
            f = f"    fields: {sdf['fields']}"
        else:
            f = [f"    {fname}: {ftype}" for fname, ftype in sdf["fields"].items()]
        f = "\n".join(f)

        raw = f"{name}:\n  fields:\n{f}"
        raw = textwrap.dedent(raw)
        hash = sha256(raw.encode()).hexdigest()

        # Create the SDF data class
        obj = SDF(raw, hash, name, src=self.current_file)

        # Parse and the fields of the definition
        self.add_fields(obj, sdf["fields"])

        # Store the new defintion
        self.struct_defs[name] = obj

    def check_name(self, name: str):
        """Check that names start with a letter."""
        if name == "_RESERVED_":
            return

        if not name.startswith(tuple(c for c in string.ascii_letters)):
            raise RTMASyntaxError(
                f"Invalid name {name} in {self.current_file}. Names can only start with letters"
            )

    def handle_message_def(self, name: str, mdf: Dict[str, Any]):
        # Check for valid name
        self.check_name(name)

        self.check_duplicate_name(
            "message_defs",
            name,
            namespaces=(
                "constants",
                "string_constants",
                "aliases",
                "struct_defs",
                "message_defs",
            ),
        )

        if not isinstance(mdf, dict):
            raise InvalidTypeError(
                f"Invalid object type for message def {name} of {type(mdf).__name__} -> {self.current_file}"
            )

        if name == "_RESERVED_":
            self.handle_reserve(name, mdf)
            return

        # Check for correct section headers
        valid_sections = ("id", "fields")
        for section in mdf.keys():
            if section not in valid_sections:
                raise RTMASyntaxError(
                    f"Invalid top-level section '{section}' in message or struct definition of {name} -> {self.current_file}."
                )

        # Check for a signal def
        if mdf["fields"] is None:
            self.handle_signal(name, mdf)
            return

        # Create a string representation of the defintion to hash
        if isinstance(mdf["fields"], str):
            f = f"    fields: {mdf['fields']}"
        else:
            f = [f"    {fname}: {ftype}" for fname, ftype in mdf["fields"].items()]
        f = "\n".join(f)
        raw = f"{name}:\n  id: {mdf['id']}\n  fields:\n{f}"

        raw = textwrap.dedent(raw)
        hash = sha256(raw.encode()).hexdigest()

        # Create the MDF data class
        obj = MDF(raw, hash, name, type_id=mdf["id"], src=self.current_file)

        # Check and validate message id
        msg_id = mdf["id"]
        self.validate_msg_id(name, msg_id)
        self.message_ids[name] = MT(name, msg_id, src=self.current_file)

        # Parse and the fields of the definition
        self.add_fields(obj, mdf["fields"])

        # Store the new defintion
        self.message_defs[name] = obj

    def handle_reserve(self, name: str, mdf: Dict[str, List]):
        for section in mdf.keys():
            if section not in ("id",):
                raise RTMASyntaxError(
                    f"Invalid top-level section '{section}'. Only 'id is allowed in {name} -> {self.current_file}"
                )

        if not isinstance(mdf["id"], list):
            raise InvalidTypeError("_RESERVED_.id must be a list.")

        reserved = []
        for e in mdf["id"]:
            if isinstance(e, int):
                reserved.append(e)
            elif isinstance(e, str):
                m = re.search(
                    r"\s*(?P<start>[0-9]+)\s*(:|\-|to)\s*(?P<end>[0-9]+)\s*", e
                )
                if m is None:
                    raise RTMASyntaxError(f"_RESERVED_.id has invalid entry: {e}")

                start = int(m.groupdict()["start"])
                end = int(m.groupdict()["end"])

                if start > end:
                    raise RTMASyntaxError(f"_RESERVED_.id has an invalid range: {e}")

                if ((end + 1) - start) > 100:
                    raise RTMASyntaxError(
                        f"_RESERVED_.id has an spans too large a range (100 max): {e}"
                    )

                reserved.extend(list(range(start, end + 1)))
            else:
                raise RTMASyntaxError(f"_RESERVED_.id has an invalid entry: {e}")

        # Generate reserved defintion placeholders
        for id in reserved:
            name = f"_RESERVED_{id:06d}"
            self.handle_signal(name, dict(id=id, fields=None))

    def parse_text(self, text: str):
        self.check_key_value_separation(text)

        # Parse the yaml file
        try:
            yaml = YAML(typ="unsafe", pure=True)
            data = yaml.load(text)
        except Exception as e:
            raise YAMLSyntaxError(
                f"Error encountered by YAML parser in {self.current_file}"
            ) from e

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
        for section in data.keys():
            if section not in valid_sections:
                raise RTMASyntaxError(
                    f"Invalid top-level section '{section}' in message defs file -> {self.current_file}."
                )

        if data.get("imports") is not None:
            if isinstance(data["imports"], list):
                for imp in data["imports"]:
                    self.handle_import(imp)
            else:
                raise RTMASyntaxError(
                    f"Imports must be a list of paths in message defs file -> {self.current_file}."
                )

        if data.get("constants") is not None:
            for name, expr in data["constants"].items():
                self.handle_expression(name, expr)
            self.yaml_dict["constants"].update(data["constants"])

        if data.get("string_constants") is not None:
            for name, str_const in data["string_constants"].items():
                self.handle_string(name, str_const)
            self.yaml_dict["string_constants"].update(data["string_constants"])

        if data.get("aliases") is not None:
            for alias, ftype in data["aliases"].items():
                self.handle_alias(alias, ftype)
            self.yaml_dict["aliases"].update(data["aliases"])

        if data.get("host_ids") is not None:
            for name, value in data["host_ids"].items():
                self.handle_host_id(name, value)
            self.yaml_dict["host_ids"].update(data["host_ids"])

        if data.get("module_ids") is not None:
            for name, value in data["module_ids"].items():
                self.handle_module_id(name, value)
            self.yaml_dict["module_ids"].update(data["module_ids"])

        if data.get("struct_defs") is not None:
            for name, sdf in data["struct_defs"].items():
                self.handle_struct(name, sdf)
            self.yaml_dict["struct_defs"].update(data["struct_defs"])

        if data.get("message_defs") is not None:
            for name, mdf in data["message_defs"].items():
                self.handle_message_def(name, mdf)
            self.yaml_dict["message_defs"].update(data["message_defs"])

    def check_key_value_separation(self, text: str):
        for n, line in enumerate(text.splitlines(), start=1):
            if ":" in line:
                if re.search(r"(:\s+)|(:$)", line) is None:
                    raise RTMASyntaxError(
                        f"Key-Value pairs must be separated with a ':' followed by a space. Add a space after the colon.\n{self.current_file}: line {n}\n{line}"
                    )

    def parse(self, msgdefs_file: os.PathLike):
        # Get the current pwd
        cwd = pathlib.Path.cwd()
        try:
            # Always start by parsing the core_defs.yaml file
            pkg_dir = pathlib.Path(os.path.realpath(__file__)).parent
            core_defs = pkg_dir / "core_defs/core_defs.yaml"
            self.parse_file(core_defs.absolute())

            defs_path = pathlib.Path(msgdefs_file)
            self.parse_file(defs_path)
        except Exception as e:
            self.clear()
            raise
        finally:
            os.chdir(str(cwd.absolute()))

    def parse_file(self, msgdefs_file: pathlib.Path):
        # Change the working directory
        cwd = pathlib.Path.cwd()
        msgdefs_path = (cwd / msgdefs_file).resolve()
        os.chdir(str(msgdefs_path.parent.absolute()))

        # check previously included files
        if any((msgdefs_path == f for f in self.included_files)):
            self.logger.debug(
                f"Skipping -> {msgdefs_path.absolute()} already parsed..."
            )
            os.chdir(str(cwd.absolute()))
            return

        self.logger.info(f"Parsing -> {msgdefs_path.absolute()}")
        prev_file = self.current_file
        self.current_file = msgdefs_path.absolute()
        self.included_files.append(msgdefs_path)

        try:
            with open(msgdefs_path, "rt") as f:
                text = f.read()
        except FileNotFoundError as e:
            alt_ext = ".yaml" if msgdefs_path.suffix == ".yml" else ".yml"
            alt_path = msgdefs_path.parent / (msgdefs_path.stem + alt_ext)
            if alt_path.is_file() and alt_path.exists():
                detail = f"\n\nCheck file extension -> Did you mean {alt_path}?"
            else:
                detail = ""
            e.args = tuple([*e.args, msgdefs_path.absolute(), detail])
            raise e

        self.parse_text(text)
        self.current_file = prev_file

        os.chdir(str(cwd.absolute()))

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


class CustomEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if is_dataclass(o):
            return asdict(o)
        if isinstance(o, pathlib.Path):
            return str(o.absolute())
        return super().default(o)
