import json
from hashlib import sha256
from typing import List, Optional, Any, Dict, Union
from dataclasses import dataclass, field, is_dataclass, asdict

from .parser import Include, TypeDef, Define, Struct, Token


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
    name: str
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

    @property
    def signal(self) -> bool:
        return len(self.fields) > 0


@dataclass
class SDF:
    hash: str
    name: str
    fields: List[Field] = field(default_factory=list)


RTMAObjects = Union[Constant, MT, MID, TypeAlias, MDF, SDF, Field]


class Processor:
    def __init__(self, tokens: List[Token]):
        self.constants = {}
        self.MT: Dict[str, str] = {}
        self.MID: Dict[str, str] = {}
        self.typedefs: Dict[str, str] = {}
        self.structs: Dict[str, Struct] = {}

        self.objs: List[RTMAObjects] = []

        self.process(tokens)

    def process_define(self, macro: Define):
        name, value = (macro.name, macro.value)

        assert value is not None, f"No value assigned to define: {name}"

        # Message Type Ids
        if name.startswith("MT_"):
            if not isinstance(value, int):
                raise SyntaxError(f"Message Type ids must be an int: {name} -> {value}")

            obj = MT(name, value)

        # Module Ids
        elif macro.name.startswith("MID_"):
            if not isinstance(value, int):
                raise SyntaxError(f"Module ids must be an int: {name} -> {value}")

            obj = MID(name, value)

        # Constant values
        else:
            assert isinstance(
                value, (int, float, str)
            ), f"Constants must evaluate to a str, float, or int."
            obj = Constant(name, value)

        self.objs.append(obj)

    def process_typedef(self, typedef: TypeDef):
        self.objs.append(TypeAlias(typedef.name, typedef.type))

    def process_struct(self, struct: Struct):
        if len(struct.fields) == 0:
            raise RuntimeError(f"Struct {struct.name} does not contain any fields.")

        # Message Definition Structure
        if struct.name.startswith("MDF_"):
            # Look for a matching message type id
            mt = None
            for o in self.objs:
                if not isinstance(o, MT):
                    continue

                if o.name[3:] == struct.name[4:]:
                    mt = o

            if mt is None:
                raise SyntaxError(f"No Message Type id defined for {struct.name}")

            obj = MDF(struct.hash, struct.name, mt)

        # Regular Structure
        else:
            obj = SDF(struct.hash, struct.name)

        # Add the field info
        for f in struct.fields:
            obj.fields.append(Field(f.name, f.type_name, f.length))

        self.objs.append(obj)

    def process_signals(self):
        """Add an empty MDF placeholder for signal definitions"""
        n = 0
        while n < len(self.objs):
            obj = self.objs[n]
            if isinstance(obj, MT):
                mt = obj
                mdfs = [o.name for o in self.objs[n:] if isinstance(o, MDF)]
                name = "MDF_" + mt.name[3:]
                if name not in mdfs:
                    hash = sha256(b"").hexdigest()
                    self.objs.append(MDF(hash, name, mt))
            n += 1

    def process(self, tokens: List[Token]):
        for token in tokens:
            # Check for duplicates names
            for o in self.objs:
                if o.name == token.name:
                    raise KeyError(f"Duplicate name found: {token.name}")

            if isinstance(token, Define):
                self.process_define(token)
            elif isinstance(token, TypeDef):
                self.process_typedef(token)
            elif isinstance(token, Struct):
                self.process_struct(token)
            elif isinstance(token, Include):
                pass

        self.process_signals()

    def to_json(self):
        return json.dumps(self.objs, indent=2, cls=CustomEncoder)


class CustomEncoder(json.JSONEncoder):
    def default(self, o: Any) -> Any:
        if is_dataclass(o):
            return asdict(o)
        return super().default(o)
