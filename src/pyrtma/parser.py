"""Message definition YAML parser"""

import re
import json
import pathlib
import os
import textwrap
import ctypes
import logging
import string
import sys

# import yaml
from ruamel.yaml import YAML

from copy import copy
from hashlib import sha256
from typing import (
    List,
    Optional,
    Any,
    Union,
    Tuple,
    Dict,
    Type,
    Literal,
    cast,
    TYPE_CHECKING,
)
from dataclasses import dataclass, field, fields, is_dataclass, asdict

if TYPE_CHECKING:
    from _typeshed import DataclassInstance

try:
    from .core_defs import MAX_MESSAGE_TYPES
except AttributeError:
    # if we deprecate and remove this constant, we can fall back on inf
    # changed from inf to maxsize to maintain int type
    MAX_MESSAGE_TYPES = sys.maxsize

try:
    from .core_defs import DYN_MOD_ID_START, MAX_HOSTS
except (AttributeError, ImportError):
    # The values in rtma_core.yaml, for a build of the core definitions
    # themselves.
    DYN_MOD_ID_START = 10000
    MAX_HOSTS = 5

MAX_REFERENCE_DEPTH: int = 16
"""How deeply constants and aliases may be defined in terms of each other.

A constant whose expression uses only numbers has depth 0, and one that uses
other constants is one deeper than the deepest of them. An alias of a native
type or a struct has depth 1, and an alias of an alias is one deeper than it.
Deeper definitions raise `RecurisionError`.
"""

import os
import re
from typing import Optional


def expand_env_variables(input_string: str) -> str:
    """
    Expand environment variables in a string using ${VAR_NAME} syntax.

    Detects ${VAR_NAME} patterns, looks up the variable value from os.environ,
    validates it's a string, and replaces the syntax with the value.

    Args:
        input_string: A string that may contain ${VAR_NAME} patterns

    Returns:
        The expanded string with environment variables replaced

    Raises:
        ValueError: If an environment variable is referenced but not found

    Examples:
        >>> os.environ['MY_PROJECT'] = '/home/user/myproject'
        >>> expand_env_variables('C:/${MY_PROJECT}/path/to/file')
        'C:/home/user/myproject/path/to/file'
    """
    # Pattern to find ${VAR_NAME} - matches word characters only
    pattern = r"\$\{(?P<name>\w+)\}"

    def replace_var(match):
        var_name = match.group("name")

        # Get the environment variable
        value = os.environ.get(var_name)

        if value is None:
            raise RTMASyntaxError(f"Environment variable '{var_name}' not found")

        # Verify it's a string
        if not isinstance(value, str):
            raise RTMASyntaxError(
                f"Environment variable '{var_name}' is not a string, "
                f"got {type(value).__name__}"
            )

        return value

    # Replace all ${VAR_NAME} patterns with their values
    expanded = re.sub(pattern, replace_var, input_string)
    return expanded


@dataclass
class NativeType:
    name: str
    size: int
    format: str


# Native C types and sizes that are supported
supported_types = {
    "char": NativeType(name="char", size=1, format="c"),
    "signed char": NativeType(name="signed char", size=1, format="b"),
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


class DuplicateFileError(ParserError):
    """Raised when the a file is already in use"""

    pass


class MessageIDError(ParserError):
    """Raised when the a message id is already in use"""

    pass


class CircularRefError(ParserError):
    """Raised when an expression contains a circular reference"""

    pass


class CircularImportError(ParserError):
    """Raised when an message definition files contain a circular reference"""

    pass


class ExpressionExpansionError(ParserError):
    """Raised when an expression can not be expanded."""

    pass


class RecurisionError(ParserError, RecursionError):
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


class GeneratedSourceError(ParserError):
    """The compiler generated code that isn't valid in its language."""

    pass


class InvalidMessageSize(ParserError):
    """Raised when a message is too large"""

    pass


@dataclass
class CompilerOptions:
    import_coredefs: bool = True
    validate_alignment: bool = True
    auto_pad: bool = True


@dataclass
class MsgDefIndex:
    name: str
    value: str
    file: pathlib.Path


@dataclass
class Metadata:
    name: str
    value: Union[int, float, bool, str]
    src: MsgDefIndex


@dataclass
class Import:
    name: str
    file: pathlib.Path
    src: MsgDefIndex


@dataclass
class ConstantExpr:
    name: str
    expression: str
    expanded: Optional[str]
    value: Union[str, int, float]
    src: MsgDefIndex
    depth: int = 0


@dataclass
class ConstantString:
    """A string constant.

    Attributes:
        name: The constant's name.
        value: The text as a double-quoted literal, with backslashes and
            double quotes escaped by a backslash. It is valid, and means the
            same text, in Python, C and JavaScript.
        src: The definitions file it came from.
        text: The text itself.
    """

    name: str
    value: str
    src: MsgDefIndex
    text: str = ""


@dataclass
class MT:
    name: str
    value: int
    src: MsgDefIndex


@dataclass
class MID:
    name: str
    value: int
    src: MsgDefIndex


@dataclass
class HID:
    name: str
    value: int
    src: MsgDefIndex


@dataclass
class TypeAlias:
    name: str
    type_name: str
    type_obj: Union[NativeType, "SDF"]
    src: MsgDefIndex
    depth: int = 1

    @property
    def size(self) -> int:
        return self.type_obj.size

    @property
    def alignment(self) -> int:
        if isinstance(self.type_obj, NativeType):
            return self.type_obj.size
        else:
            return self.type_obj.alignment

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
    offset: int = -1

    @property
    def base_size(self) -> int:
        return self.type_obj.size

    @property
    def size(self):
        return self.type_obj.size * (self.length or 1)

    @property
    def alignment(self) -> int:
        if isinstance(self.type_obj, NativeType):
            return self.type_obj.size
        else:
            return self.type_obj.alignment

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
    src: MsgDefIndex
    fields: List[Field] = field(default_factory=list)
    alignment: int = 8

    @property
    def signal(self) -> bool:
        return len(self.fields) > 0

    @property
    def size(self) -> int:
        return sum([f.size for f in self.fields])

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
    src: MsgDefIndex
    fields: List[Field] = field(default_factory=list)
    alignment: int = 8

    @property
    def size(self) -> int:
        return sum([f.size for f in self.fields])

    @property
    def format(self) -> str:
        s = ""
        for field in self.fields:
            s += field.format

        return s


RTMAObject = Union[ConstantExpr, ConstantString, HID, MID, TypeAlias, MDF, SDF, Field]


class Parser:
    """Parser class"""

    core_imports = ("rtma_core", "data_logger", "quick_logger")
    _instance_count: int = -1

    def __init__(
        self,
        debug: bool = False,
    ):
        """Parser class

        Args:
            debug (bool, optional): Flag for debug mode. Defaults to False.
        """
        self.included_files: List[MsgDefIndex] = []
        self.current_index = MsgDefIndex("", "", pathlib.Path())
        self.debug = debug
        Parser._instance_count += 1

        self.yaml_dict: Dict[str, Dict[str, Any]] = dict(
            metadata={},
            imports={},
            constants={},
            string_constants={},
            host_ids={},
            module_ids={},
            aliases={},
            struct_defs={},
            message_defs={},
        )

        # Compiler File Data:
        self.index: Dict[str, MsgDefIndex] = {}
        self.compiler_options = CompilerOptions()
        self.deps: list[MsgDefIndex] = []

        self.metadata: Dict[str, Metadata] = {}
        self.imports: List[Import] = []
        self.constants: Dict[str, ConstantExpr] = {}
        self.string_constants: Dict[str, ConstantString] = {}
        self.aliases: Dict[str, TypeAlias] = {}
        self.host_ids: Dict[str, HID] = {}
        self.module_ids: Dict[str, MID] = {}
        self.struct_defs: Dict[str, SDF] = {}
        self.message_ids: Dict[str, MT] = {}
        self.message_defs: Dict[str, MDF] = {}

        # Aliases of structs defined later in the file being parsed, by name,
        # with the struct each names. They are resolved as the structs are.
        self._pending_aliases: Dict[str, str] = {}

        self.logger = logging.getLogger(f"pyrtma.parser ({self._instance_count})")
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

        # Reserved field names
        reserved_file = pathlib.Path(__file__).parent / "reserved_field_names.json"
        with open(reserved_file, "r") as f:
            self.reserved_field_names = json.load(f)

    @property
    def current_file(self) -> pathlib.Path:
        return self.current_index.file

    @property
    def import_coredefs(self) -> bool:
        return self.compiler_options.import_coredefs

    @property
    def auto_pad(self) -> bool:
        return self.compiler_options.auto_pad

    @property
    def validate_alignment(self) -> bool:
        return self.compiler_options.validate_alignment

    def warning(self, msg: str):
        self.logger.warning(msg)

    def clear(self):
        self.current_index = MsgDefIndex("", "", pathlib.Path())
        self.yaml_dict = dict(
            metadata={},
            imports={},
            constants={},
            string_constants={},
            host_ids={},
            module_ids={},
            aliases={},
            struct_defs={},
            message_defs={},
        )
        self.compiler_options = CompilerOptions()
        self.index = {}
        self.deps = []

        self.included_files = []
        self.metadata = {}
        self.imports = []
        self.constants = {}
        self.string_constants = {}
        self.aliases = {}
        self.host_ids = {}
        self.module_ids = {}
        self.struct_defs = {}
        self.message_ids = {}
        self.message_defs = {}
        self._pending_aliases = {}

    def check_duplicate_name(
        self, section: str, name: str, namespaces: Tuple[str, ...]
    ):
        """Check namespaces for conflicting names."""
        for namespace in namespaces:
            ns = getattr(self, namespace)
            for o in ns.values():
                if name == o.name:
                    raise DuplicateNameError(
                        f"Duplicate name conflict found: \n\n1: {namespace} -> {o.name} -> {o.src.file.absolute()}\n2: {section} -> {name} -> {self.current_file}\n"
                    )

    def expand_expression(self, name: str, expr: str) -> Tuple[str, Any]:
        """Replace the constants in an expression with their values, and evaluate it.

        Every constant an expression uses must be defined before it, and
        already has a value, so one pass replaces them all and nothing is
        expanded again. That rules out circular references between constants;
        an expression that uses its own name raises `CircularRefError`.

        Args:
            name: What the expression defines, such as a constant's name, or
                ``MESSAGE->field`` for an array length.
            expr: The expression.

        Returns:
            The expression with every constant replaced by its value, and the
            value it evaluates to.

        Raises:
            CircularRefError: The expression uses the name it defines.
            ExpressionExpansionError: It uses a name that isn't a constant
                defined before it, or doesn't evaluate.
        """
        symbol_regex = r"\b(?P<symbol>[a-zA-Z_]+\w*)\b"

        def substitute(m: "re.Match[str]") -> str:
            symbol = m.group("symbol")
            if symbol == name:
                raise CircularRefError(
                    f"Circular reference in expression: {name} -> {expr} -> {self.current_file}"
                )
            try:
                c = self.constants[symbol]
            except KeyError:
                raise ExpressionExpansionError(
                    f"Unable to expand expression {name} -> {symbol} not defined. "
                    f"Constants must be defined before they are used: {self.current_file}"
                ) from None

            if c.value is None:
                raise ExpressionExpansionError(
                    f"{c.name} has not been evaluated to a value."
                )
            # Not parenthesized, as before, so existing values don't change.
            return str(c.value)

        expanded = re.sub(symbol_regex, substitute, expr)

        # TODO: check that only numbers and operators are left in expression
        try:
            value = eval(expanded)
        except Exception as e:
            raise ExpressionExpansionError(
                f"Unable to evaluate expression {name}: {expr} -> {expanded} ({type(e).__name__}: {e}) -> {self.current_file}"
            ) from e

        return expanded, value

    def expression_depth(self, expr: str) -> int:
        """How deeply an expression is nested in other constants.

        Args:
            expr: An expression whose constants are all defined.

        Returns:
            0 for an expression of numbers only, otherwise one more than the
            deepest constant it uses.
        """
        symbols = re.findall(r"\b[a-zA-Z_]+\w*\b", expr)
        depths = [self.constants[s].depth for s in symbols if s in self.constants]
        return 1 + max(depths) if depths else 0

    def handle_import(self, fname: str):
        if fname not in self.index.keys():
            raise RTMASyntaxError(
                f"The name '{fname}' was not found in the compiler defs file index."
            )

        for m in self.deps:
            if m.name == fname:
                raise CircularImportError(
                    f"{m.name} and {self.current_index.name} have circular import reference."
                )

        msgdefs = self.index[fname]
        imp = Import(fname, msgdefs.file, src=self.current_index)

        self.imports.append(imp)
        if imp.file.is_dir():
            raise FileFormatError(
                f"Imports must be yaml files, not directories. -> {self.current_file}"
            )
        if not imp.file.suffix.lower() in [".yaml", ".yml"]:
            raise FileFormatError(f"Imports must be .yaml files -> {self.current_file}")

        if imp.file.suffix == ".yml":
            self.warning(f"Please change {imp.file} to use '.yaml' extension.")

        self.parse_index(fname)

    def handle_metadata(self, name: str, value: Union[int, float, bool, str]):
        self.check_name(name)
        self.check_duplicate_name(
            "metadata",
            name,
            namespaces=("metadata",),
        )

        if not isinstance(value, (int, float, bool, str)):
            raise InvalidTypeError(
                f"Values in 'metadata' section must be of type int, float, bool, or string not{type(value).__name__}. {name} -> {self.current_file}"
            )

        self.metadata[name] = Metadata(
            name,
            value,
            src=self.current_index,
        )

    def handle_compiler_options(self, name: str, value: Union[int, float, bool, str]):
        self.check_name(name)
        # setattr() on the dataclass accepts any name, so check it first.
        known = [f.name for f in fields(CompilerOptions)]
        if name not in known:
            raise RTMASyntaxError(
                f"Unknown compiler option: {name}. The options are {', '.join(known)} -> {self.defs_path}"
            )
        setattr(self.compiler_options, name, value)

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
                src=self.current_index,
            )
        elif isinstance(expression, str):
            expanded, value = self.expand_expression(name, expression)
            depth = self.expression_depth(expression)
            if depth > MAX_REFERENCE_DEPTH:
                raise RecurisionError(
                    f"Constant {name} is nested {depth} deep in other constants, more than the limit of {MAX_REFERENCE_DEPTH} -> {self.current_file}"
                )
            self.constants[name] = ConstantExpr(
                name,
                expression=expression,
                expanded=expanded,
                value=value,
                src=self.current_index,
                depth=depth,
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

        # Printable ASCII only: strings are ASCII on the wire, and control
        # characters would need a different escape in every target.
        for ch in value:
            if not " " <= ch <= "~":
                raise RTMASyntaxError(
                    f"String constant {name} contains {ch!r}. String constants can only hold printable ASCII characters -> {self.current_file}"
                )

        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        self.string_constants[name] = ConstantString(
            name,
            value=f'"{escaped}"',
            src=self.current_index,
            text=value,
        )

    def handle_alias(self, alias: str, ftype: str):
        """Find the base type ultimately represented by the typedef alias.

        The alias's `type_name` is the native type or struct it resolves to,
        through any aliases in between.

        Args:
            alias: The alias's name.
            ftype: The type it names: a native type, a struct, or an alias,
                each defined before it.

        Raises:
            InvalidTypeError: `ftype` isn't a string.
            CircularRefError: The alias names itself.
            RTMASyntaxError: `ftype` isn't a type defined before it.
            RecurisionError: The chain of aliases is longer than
                `MAX_REFERENCE_DEPTH`.
        """
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

        self.aliases[alias] = self.resolve_alias(alias, ftype)

    def resolve_alias(self, alias: str, ftype: str) -> TypeAlias:
        """Resolve the type an alias names.

        Args:
            alias: The alias's name.
            ftype: The type it names.

        Returns:
            The alias, resolved to a native type or struct.

        Raises:
            CircularRefError: The alias names itself.
            RTMASyntaxError: `ftype` isn't a type defined before it.
            RecurisionError: The chain of aliases is too long.
        """
        if ftype == alias:
            raise CircularRefError(
                f"Alias {alias} refers to itself -> {self.current_file}"
            )

        if ftype in supported_types:
            return TypeAlias(alias, ftype, supported_types[ftype], self.current_index)

        if ftype in self.struct_defs:
            return TypeAlias(
                alias, ftype, self.struct_defs[ftype], src=self.current_index
            )

        # An alias defined earlier is already resolved, so one step is enough.
        if ftype in self.aliases:
            target = self.aliases[ftype]
            depth = target.depth + 1
            if depth > MAX_REFERENCE_DEPTH:
                raise RecurisionError(
                    f"Alias {alias} is a chain of {depth} aliases, more than the limit of {MAX_REFERENCE_DEPTH} -> {self.current_file}"
                )
            return TypeAlias(
                alias,
                target.type_name,
                target.type_obj,
                src=self.current_index,
                depth=depth,
            )

        raise RTMASyntaxError(
            f"Unable to resolve alias {alias}: {ftype} -> {self.current_file}"
        )

    def handle_host_id(self, name: str, value: int):
        self.check_name(name)
        self.check_duplicate_name("host_ids", name, namespaces=("host_ids",))

        if not isinstance(value, int):
            raise InvalidTypeError(
                f"Values in 'host_ids' section must evaluate to int type not {type(value).__name__}. {name}: {value}"
            )

        user_file = (
            self.current_index.name not in Parser.core_imports and self.import_coredefs
        )
        if value < 1 or value > 32767:
            if user_file:
                raise RTMASyntaxError(
                    f"Value outside of valid range [1 - 32767] for host_id: {name}: {value}"
                )
        elif value > MAX_HOSTS and user_file:
            self.warning(
                f"Host ID {name}: {value} is above MAX_HOSTS ({MAX_HOSTS}). A client can send from it, but messages can't be addressed to it -> {self.current_file}"
            )

        for hid in self.host_ids.values():
            if value == hid.value:
                raise HostIDError(
                    f"Duplicate host id conflict found for {name} and {hid.name} -> {value}\n1: {hid.src.file.absolute()}\n2: {self.current_file}\n"
                )
        self.host_ids[name] = HID(
            name,
            int(value),
            src=self.current_index,
        )

    def handle_module_id(self, name: str, value: int):
        self.check_name(name)
        self.check_duplicate_name("module_ids", name, namespaces=("module_ids",))

        if not isinstance(value, int):
            raise InvalidTypeError(
                f"Values in 'module_ids' section must evaluate to int type not {type(value).__name__}. {name}: {value} -> {self.current_file}"
            )

        # IDs from DYN_MOD_ID_START up are assigned by the manager; a client
        # can't ask for one.
        if value < 10 or (99 < value < 200) or value >= DYN_MOD_ID_START:
            if (
                self.current_index.name not in Parser.core_imports
                and value != 0
                and self.import_coredefs
            ):
                raise RTMASyntaxError(
                    f"Value outside of valid range [10 - 99 or 200 - {DYN_MOD_ID_START - 1}] for module_id: {name}: {value} -> {self.current_file}"
                )

        for mid in self.module_ids.values():
            if value == mid.value:
                raise ModuleIDError(
                    f"Duplicate module id conflict found for {name} and {mid.name} -> {value}\n1: {mid.src.file.absolute()}\n2: {self.current_file}\n"
                )

        self.module_ids[name] = MID(name, int(value), src=self.current_index)

    def check_alignment(self, s: Union[SDF, MDF]):
        """Confirm 64 bit alignment of structures"""
        PADDING_BYTE_TYPE = "byte"

        # This value will represent the memory address currently pointed to in the struct layout
        ptr = 0

        npad = 0  # padding field count
        n = 0  # field index

        pad_len: Union[int, Literal[""]]

        # Loop over all fields in struct
        while n < len(s.fields):
            # Get the next field object
            field = s.fields[n]

            # Check if current address meets alignment requirement of the field
            if (ptr % field.alignment) == 0:
                # Store the fields offset in struct
                field.offset = ptr

                # Stride by an amount equal to the field size
                ptr += field.size

                # Go on to the next field (No padding required)
                n += 1
                continue

            # Bail if auto padding is disabled
            if not self.auto_pad:
                raise AlignmentError(
                    f"{s.name}.{field.name} does not start on a valid memory boundary for type: {field.type_name}. Add padding fields prior for 64-bit alignment."
                )

            # Calculate number of bytes needed to get to next alignment boundary
            pad_len = field.alignment - (ptr % field.alignment)

            # Create the required padding field
            padding = Field(
                name=f"padding_{npad}_",
                type_name=PADDING_BYTE_TYPE,
                type_obj=supported_types[PADDING_BYTE_TYPE],
                length_expression=f'"{pad_len}"',
                length_expanded=f'"{pad_len}"',
                length=pad_len,
                offset=ptr,
            )

            # Insert the padding into MDF or SDF object before the current field
            s.fields.insert(n, padding)

            # Stride by an amount equal to the field size
            ptr += padding.size

            # Ideally the user should explicitly pad their struct layout
            self.warning(
                f"Adding {pad_len} padding byte(s) before {s.name}.{field.name}."
            )

            # Store the fields offset in struct
            field.offset = ptr

            # Stride by an amount equal to the field size
            ptr += field.size

            # Skip 2 since len of fields has been extended
            n += 2
            npad += 1

        # Note: ptr currently points to the byte immediately following the struct

        # Explicitly align the end of the struct to allow for the strictest alignment to be satisfied
        # Must account for C packing of array of structs and striding using sizeof
        # We do this by calculating the padding required for consecutive structs

        pad_len = 0  # Start with no padding
        while 1:
            # Check if any fields do not meet their required alignment
            if any([(pad_len + ptr + f.offset) % f.alignment for f in s.fields]):
                # Increase the padding and try again
                pad_len += 1
                continue

            # No padding required
            if pad_len == 0:
                break

            # Bail if auto padding is disabled
            if not self.auto_pad:
                raise AlignmentError(
                    f"{s.name} requires trailing padding of {pad_len} bytes for 64-bit alignment."
                )

            # Don't make an array type if we only need one byte padding
            if pad_len == 1:
                pad_len = ""

            # Create the required padding field
            padding = Field(
                name=f"padding_{npad}_",
                type_name=PADDING_BYTE_TYPE,
                type_obj=supported_types[PADDING_BYTE_TYPE],
                length_expression=f'"{pad_len}"',
                length_expanded=f'"{pad_len}"',
                length=pad_len or None,
                # It starts where the last field ends.
                offset=ptr,
            )

            # Stride by an amount equal to the field size
            ptr += padding.size

            # Append the padding at the end of the MDF or SDF object
            s.fields.append(padding)

            # Ideally the user should explicitly pad their struct layout
            self.warning(
                f"WARNING: Adding {pad_len} trailing padding byte(s) at end of {s.name}."
            )

            # Exit loop
            break

        # Determine the alignment requirement for the struct
        strictest_alignment = max(f.alignment for f in s.fields)
        for a in (8, 4, 2, 1):
            # Find where the current ptr aligns
            if (ptr % a) == 0:
                s.alignment = min(a, strictest_alignment)
                break
        else:  # only runs if we don't break
            # Note: This should never happen
            raise RuntimeError(f"Unable to determine alignment required for {s.name}")

        # Final size check using Python's builtin ctypes module
        assert s.size == self.get_ctype_size(
            s
        ), f"{s.name} is not 64-bit aligned. s.size = {s.size}, struct size = {self.get_ctype_size(s)}."

    def get_ctype_cls(self, s: Union[MDF, SDF]) -> Type[ctypes.Structure]:
        # Field type name to ctypes
        type_map = {
            "char": ctypes.c_char,
            "signed char": ctypes.c_int8,
            "unsigned char": ctypes.c_ubyte,
            "byte": ctypes.c_ubyte,
            "int": ctypes.c_int32,
            "signed int": ctypes.c_int32,
            "unsigned int": ctypes.c_uint32,
            "unsigned": ctypes.c_uint32,
            "short": ctypes.c_int16,
            "signed short": ctypes.c_int16,
            "unsigned short": ctypes.c_uint16,
            "long": ctypes.c_int32,
            "signed long": ctypes.c_int32,
            "unsigned long": ctypes.c_uint32,
            "long long": ctypes.c_int64,
            "signed long long": ctypes.c_int64,
            "unsigned long long": ctypes.c_uint64,
            "float": ctypes.c_float,
            "double": ctypes.c_double,
            "uint8": ctypes.c_uint8,
            "uint16": ctypes.c_uint16,
            "uint32": ctypes.c_uint32,
            "uint64": ctypes.c_uint64,
            "int8": ctypes.c_int8,
            "int16": ctypes.c_int16,
            "int32": ctypes.c_int32,
            "int64": ctypes.c_int64,
        }

        f = []
        cobj: Any
        for n, field in enumerate(s.fields):
            if isinstance(field.type_obj, (MDF, SDF)):
                cobj = self.get_ctype_cls(field.type_obj)
            elif isinstance(field.type_obj, NativeType):
                cobj = type_map[field.type_obj.name]
            elif isinstance(field.type_obj, TypeAlias):
                if isinstance(field.type_obj.type_obj, NativeType):
                    cobj = type_map[field.type_obj.type_obj.name]
                else:
                    cobj = self.get_ctype_cls(field.type_obj.type_obj)
            else:
                raise RuntimeError(f"Unexpected type {type(field.type_obj)}")

            if field.length:
                f.append((f"f{n}", cobj * (field.length)))
            else:
                f.append((f"f{n}", cobj))

        return type(s.name, (ctypes.Structure,), {"_fields_": f})

    def get_ctype_size(self, s: Union[MDF, SDF]) -> int:
        return ctypes.sizeof(self.get_ctype_cls(s))

    def validate_msg_id(self, name: str, msg_id: int):
        if not isinstance(msg_id, int):
            raise InvalidTypeError(
                f"Message definition id must evaluate to int type not {type(msg_id).__name__}. {name}: {msg_id}"
            )

        if msg_id < 0 or msg_id > MAX_MESSAGE_TYPES:
            raise RTMASyntaxError(
                f"Value outside of valid range [0 - {MAX_MESSAGE_TYPES}] for module_id: {name}: {msg_id}"
            )

        for mt in self.message_ids.values():
            if msg_id == mt.value:
                raise MessageIDError(
                    f"Duplicate message ids conflict found for {mt.name} and {name}: {msg_id} ->\n1: {mt.src.file.absolute()}\n2: {self.current_file}\n"
                )

    def validate_msg_def(self, mdf):
        # Check number of fields > 0
        assert (
            len(mdf.fields) > 0
        ), f"Message and Struct definitions must have at least one field: {mdf.name} -> {self.current_file}"

        # Check memory alignment layout
        if self.validate_alignment:
            self.check_alignment(mdf)

        # Check size
        if mdf.size > 65535:
            raise InvalidMessageSize(
                f"{mdf.name} size of {mdf.size} exceeds maximum allowe of 65535 bytes."
            )

    def check_array_length(
        self, def_name: str, field_name: str, spec: str, value: Any
    ) -> int:
        """Check an array field's evaluated length.

        Args:
            def_name: The message or struct the field belongs to.
            field_name: The field's name.
            spec: The field's type spec, for the error message.
            value: What its length expression evaluated to.

        Returns:
            The length.

        Raises:
            RTMASyntaxError: The length isn't a whole number of 1 or more.
                A length of 0 used to give a scalar in Python and an empty
                array in the other targets, so no layout fits it.
        """
        where = f"{def_name}.{field_name}: {spec} -> {self.current_file}"
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise RTMASyntaxError(
                f"Array length must be a number, not {value!r}: {where}"
            )
        if isinstance(value, float) and not value.is_integer():
            raise RTMASyntaxError(
                f"Array length must be a whole number, not {value}: {where}"
            )
        if value < 1:
            raise RTMASyntaxError(
                f"Array length must be 1 or more, not {int(value)}: {where}"
            )
        return int(value)

    def add_fields(self, mdf: Union[SDF, MDF], fields: Union[Dict, str]):
        # Pattern to parse field specs
        FIELD_REGEX = r"\s*(?P<ftype>[\s\w]*)(\[(?P<len_str>.*)\])?\s*"

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
            for fname, fstr in fields.items():
                for language, reserved_fields in self.reserved_field_names.items():
                    if fname in reserved_fields:
                        raise RTMASyntaxError(
                            f"{fname} is a reserved field name for {language} use."
                        )

                if fname[0] not in string.ascii_letters:
                    raise RTMASyntaxError(
                        f"Field names must start with a letter: {mdf.name}=> {fname} -> {self.current_file}"
                    )
                if not isinstance(fstr, str):
                    raise InvalidTypeError(
                        f"Field types must be a string not {type(fstr).__name__}: {mdf.name}=> {fname}: {fstr} -> {self.current_file}"
                    )

                # The whole spec must match, so trailing text is an error.
                m = re.fullmatch(FIELD_REGEX, fstr)
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
                ftype_obj: Union[NativeType, TypeAlias, MDF, SDF]
                if ftype in supported_types.keys():
                    ftype_obj = supported_types[ftype]
                elif ftype in self.aliases.keys():
                    ftype_obj = self.aliases[ftype]
                elif ftype in self.struct_defs.keys():
                    ftype_obj = self.struct_defs[ftype]
                elif ftype in self.message_defs.keys():
                    ftype_obj = self.message_defs[ftype]
                elif ftype in self._pending_aliases:
                    raise RTMASyntaxError(
                        f"{mdf.name}.{fname} uses alias {ftype} of {self._pending_aliases[ftype]}, which isn't defined yet. Define {self._pending_aliases[ftype]} before the definitions that use {ftype} -> {self.current_file}"
                    )
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
                        length=self.check_array_length(mdf.name, fname, fstr, flen),
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
        self.message_ids[name] = MT(name, msg_id, src=self.current_index)

        # Create the MDF data class
        obj = MDF(raw, hash, name, type_id=mdf["id"], src=self.current_index)

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
        f: Union[str, List[str]]
        if isinstance(sdf["fields"], str):
            f = f"    fields: {sdf['fields']}"
        else:
            f = [f"    {fname}: {ftype}" for fname, ftype in sdf["fields"].items()]
        f = "\n".join(f)

        raw = f"{name}:\n  fields:\n{f}"
        raw = textwrap.dedent(raw)
        hash = sha256(raw.encode()).hexdigest()

        # Create the SDF data class
        obj = SDF(raw, hash, name, src=self.current_index)

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
        f: Union[str, List[str]]
        if isinstance(mdf["fields"], str):
            f = f"    fields: {mdf['fields']}"
        else:
            f = [f"    {fname}: {ftype}" for fname, ftype in mdf["fields"].items()]
            f = "\n".join(f)
        raw = f"{name}:\n  id: {mdf['id']}\n  fields:\n{f}"

        raw = textwrap.dedent(raw)
        hash = sha256(raw.encode()).hexdigest()

        # Create the MDF data class
        obj = MDF(raw, hash, name, type_id=mdf["id"], src=self.current_index)

        # Check and validate message id
        msg_id = mdf["id"]
        self.validate_msg_id(name, msg_id)
        self.message_ids[name] = MT(name, msg_id, src=self.current_index)

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
                m = re.search(r"\s*(?P<start>[0-9]+)\s*(\-|to)\s*(?P<end>[0-9]+)\s*", e)
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
            name = f"RESERVED_{id:06d}"
            self.handle_signal(name, dict(id=id, fields=None))

    def names_later_struct(self, ftype: Any, file_structs: Dict[str, Any]) -> bool:
        """Whether an alias's type is a struct defined later in this file.

        Args:
            ftype: The type the alias names.
            file_structs: The ``struct_defs`` section of the file.

        Returns:
            True when `ftype` is a struct in `file_structs`, or an alias of one
            that is waiting for it.
        """
        if not isinstance(ftype, str):
            return False
        return ftype in self._pending_aliases or (
            ftype in file_structs and ftype not in self.struct_defs
        )

    def defer_alias(self, alias: str, ftype: str, file_structs: Dict[str, Any]):
        """Check an alias now, and resolve it once the struct it names is defined.

        Args:
            alias: The alias's name.
            ftype: The struct it names, or an alias waiting for one.
            file_structs: The ``struct_defs`` section of the file.

        Raises:
            RTMASyntaxError: The name is invalid.
            DuplicateNameError: The name is already used, or is a struct in
                this file too.
        """
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
        if alias in self._pending_aliases or alias in file_structs:
            raise DuplicateNameError(
                f"Duplicate name conflict found: {alias} -> {self.current_file}"
            )
        self._pending_aliases[alias] = ftype

    def resolve_pending_aliases(self):
        """Resolve the deferred aliases whose type is now defined, in order."""
        for alias, ftype in list(self._pending_aliases.items()):
            if ftype in self.struct_defs or ftype in self.aliases:
                del self._pending_aliases[alias]
                self.aliases[alias] = self.resolve_alias(alias, ftype)

    def parse_text(self, text: str):
        self.check_key_value_separation(text)

        # Parse the yaml file
        try:
            yaml = YAML(typ="safe")  # typ="unsafe", pure=True)
            data = yaml.load(text)
        except Exception as e:
            raise YAMLSyntaxError(
                f"Error encountered by YAML parser in {self.current_file}"
            ) from e

        valid_sections = (
            "metadata",
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

        if data.get("metadata") is not None:
            for name, value in data["metadata"].items():
                self.handle_metadata(name, value)
            self.yaml_dict["metadata"].update(data["metadata"])

        if data.get("imports") is not None:
            if isinstance(data["imports"], list):
                for imp in data["imports"]:
                    self.handle_import(imp)
            else:
                raise RTMASyntaxError(
                    f"Imports must be a list of names referring to the message defs file index -> {self.current_file}."
                )

        if data.get("constants") is not None:
            for name, expr in data["constants"].items():
                self.handle_expression(name, expr)
            self.yaml_dict["constants"].update(data["constants"])

        if data.get("string_constants") is not None:
            for name, str_const in data["string_constants"].items():
                self.handle_string(name, str_const)
            self.yaml_dict["string_constants"].update(data["string_constants"])

        # An alias may name a struct defined later in this file. It is
        # resolved once that struct is, like a struct that uses another.
        file_structs = data.get("struct_defs") or {}
        if not isinstance(file_structs, dict):
            file_structs = {}
        if data.get("aliases") is not None:
            for alias, ftype in data["aliases"].items():
                if self.names_later_struct(ftype, file_structs):
                    self.defer_alias(alias, ftype, file_structs)
                else:
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
                self.resolve_pending_aliases()
            self.yaml_dict["struct_defs"].update(data["struct_defs"])
        # Only a struct in this file defers an alias, so all are resolved.
        assert not self._pending_aliases, self._pending_aliases

        if data.get("message_defs") is not None:
            for name, mdf in data["message_defs"].items():
                self.handle_message_def(name, mdf)
            message_defs = dict(data["message_defs"])
            # Each file may reserve IDs; keep them all for --combined output.
            earlier = self.yaml_dict["message_defs"].get("_RESERVED_")
            if earlier is not None and "_RESERVED_" in message_defs:
                message_defs["_RESERVED_"] = {
                    "id": list(earlier["id"]) + list(message_defs["_RESERVED_"]["id"])
                }
            self.yaml_dict["message_defs"].update(message_defs)

    def check_key_value_separation(self, text: str):
        for n, line in enumerate(text.splitlines(), start=1):
            # strip comments
            if "#" in line:
                idx = line.index("#")
                line = line[:idx]
            if ":" in line:
                idx = line.index(":")  # check first :
                if idx + 1 < len(line) and not line[idx + 1].isspace():
                    raise RTMASyntaxError(
                        f"Key-Value pairs must be separated with a ':' followed by a space. Add a space after the colon.\n{self.current_file}: line {n}\n{line}"
                    )

    def parse_compiler_file(self, defs_file: os.PathLike, quiet: bool = False):
        self.defs_path = pathlib.Path(defs_file)
        if not quiet:
            self.logger.info(
                f"Parsing Compiler Defs File-> {self.defs_path.absolute()}"
            )

        with open(self.defs_path, "rt") as f:
            text = f.read()

        self.check_key_value_separation(text)

        # Parse the yaml file
        try:
            yaml = YAML(typ="safe")  # typ="unsafe", pure=True)
            data = yaml.load(text)
        except Exception as e:
            raise YAMLSyntaxError(
                f"Error encountered by YAML parser in {self.defs_path}"
            ) from e
        if not isinstance(data, dict):
            raise RTMASyntaxError(
                f"Compiler defs file must contain a mapping at top level -> {self.defs_path}."
            )

        valid_sections = (
            "compiler_options",
            "index",
        )

        # Check file format
        for section in data.keys():
            if section not in valid_sections:
                raise RTMASyntaxError(
                    f"Invalid top-level section '{section}' in compiler defs file -> {self.defs_path}."
                )

        if data.get("compiler_options") is not None:
            for name, value in data["compiler_options"].items():
                self.handle_compiler_options(name, value)

        if data.get("index") is not None:
            for name, value in data["index"].items():
                self.handle_index(name, value)

    def handle_index(self, name: str, value: str):
        if name in self.index:
            raise DuplicateNameError(
                f"Duplicate entry for {name} in compiler defs file -> {self.defs_path}."
            )

        expanded = expand_env_variables(value)

        msgdefs_path = pathlib.Path(expanded)
        if not msgdefs_path.is_absolute():
            msgdefs_path = self.defs_path.parent.absolute() / msgdefs_path

        if not msgdefs_path.is_file() or not msgdefs_path.exists():
            raise FileNotFoundError(
                f"Message definition file for entry: '{name}' not found at: {msgdefs_path}"
            )

        for other in self.index.values():
            if other.file == msgdefs_path:
                raise DuplicateNameError(
                    f"Duplicate message definition file in compiler defs file for {name} and {other.name}-> {msgdefs_path}."
                )

        self.index[name] = MsgDefIndex(name, value, msgdefs_path)

    def parse(self, defs_file: os.PathLike):
        # Get the current pwd
        cwd = pathlib.Path.cwd()

        # Extract the paths to the message definitions
        self.parse_compiler_file(defs_file)

        # Add builtin core message definitions
        if self.import_coredefs:
            # Reserve certain names for internal use
            for name in ("rtma_core", "data_logger", "quick_logger"):
                if name in self.index:
                    raise RTMASyntaxError(
                        f"The name '{name}' is reserved for internal use"
                    )

            pkg_dir = pathlib.Path(os.path.realpath(__file__)).parent
            core_path = pkg_dir / "core_defs"
            core = {}
            core["rtma_core"] = MsgDefIndex(
                "rtma_core",
                f"core_defs/rtma_core.yaml",
                core_path / "rtma_core.yaml",
            )
            core["data_logger"] = MsgDefIndex(
                "data_logger",
                f"core_defs/data_logger.yaml",
                core_path / "data_logger.yaml",
            )
            core["quick_logger"] = MsgDefIndex(
                "quick_logger",
                f"core_defs/quick_logger.yaml",
                core_path / "quick_logger.yaml",
            )
            core.update(self.index)
            self.index = core

        try:
            for name in self.index.keys():
                self.parse_index(name)
        except Exception as e:
            self.clear()
            raise
        finally:
            os.chdir(str(cwd.absolute()))

    def parse_index(self, name: str):
        msgdefs = self.index[name]
        # check previously included files
        if any((msgdefs.name == f.name for f in self.included_files)):
            self.logger.debug(
                f"Skipping -> {msgdefs.file.absolute()} already parsed..."
            )
            return

        self.deps.append(msgdefs)

        self.logger.info(f"Parsing -> {msgdefs.name:24}  {msgdefs.file.absolute()}")
        prev_index = self.current_index
        self.current_index = msgdefs
        self.included_files.append(msgdefs)

        try:
            with open(msgdefs.file, "rt") as f:
                text = f.read()
        except FileNotFoundError as e:
            alt_ext = ".yaml" if msgdefs.file.suffix == ".yml" else ".yml"
            alt_path = msgdefs.file.parent / (msgdefs.file.stem + alt_ext)
            if alt_path.is_file() and alt_path.exists():
                detail = f"\n\nCheck file extension -> Did you mean {alt_path}?"
            else:
                detail = ""
            e.args = tuple([*e.args, msgdefs.file.absolute(), detail])
            raise e

        self.parse_text(text)
        self.current_index = prev_index
        self.deps.pop()

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
        if is_dataclass(o):  # this is true for instance OR type
            if TYPE_CHECKING:
                o = cast(DataclassInstance, o)
            if not isinstance(o, type):
                return asdict(o)
        if isinstance(o, pathlib.Path):
            return str(o.absolute())
        return super().default(o)


def read_compiler_index(compiler_file: str | pathlib.Path) -> dict[str, pathlib.Path]:
    parser = Parser()
    parser.parse_compiler_file(pathlib.Path(compiler_file), quiet=True)
    return {m.name: m.file for m in parser.index.values()}
