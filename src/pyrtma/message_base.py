import ctypes
import json

from typing import TypeVar, Any, Type, Dict
from .utils.print import print_ctype_array, hexdump
from .utils.random_fields import _random_struct
from .exceptions import JSONDecodingError

MB = TypeVar("MB", bound="MessageBase")


# MessageBase Metaclass - (for runtime ctypes field generation)
class MessageMeta(type(ctypes.Structure)):
    def __new__(cls, name, bases, namespace):
        fields = []
        for key in namespace.keys():
            if hasattr(namespace[key], "_ctype"):
                fname = "_" + key
                ftype = namespace[key]._ctype
                fields.append((fname, ftype))
        if fields:
            namespace["_fields_"] = fields
        return super().__new__(cls, name, bases, namespace)


# "abstract" base class for MessageHeader and MessageData
class MessageBase(ctypes.Structure, metaclass=MessageMeta):
    @property
    def size(self) -> int:
        return ctypes.sizeof(self)

    def pretty_print(self, add_tabs=0) -> str:
        str = "\t" * add_tabs + f"{type(self).__name__}:"
        for field_name, field_type in self._fields_:
            val = getattr(self, field_name)
            class_name = field_type.__name__
            # expand arrays
            if hasattr(val, "__len__"):
                if hasattr(val, "_type_"):
                    class_name = val._type_.__name__
                val = print_ctype_array(val)
            str += (
                f"\n"
                + "\t" * (add_tabs + 1)
                + f"{field_name[1:]} = ({class_name}){val}"
            )
        return str

    def hexdump(self, length=16, sep=" "):
        hexdump(bytes(self), length, sep)

    def to_dict(self) -> Dict[str, Any]:
        return _to_dict(self)

    def to_json(self, minify: bool = False, **kwargs) -> str:
        if minify:
            return json.dumps(
                self, cls=RTMAJSONEncoder, separators=(",", ":"), **kwargs
            )
        else:
            return json.dumps(self, cls=RTMAJSONEncoder, indent=2, **kwargs)

    def get_field_raw(self, name: str) -> bytes:
        """return copy of raw bytes for ctypes field 'name'"""
        meta = getattr(type(self), f"_{name}")
        if name not in [x[0] for x in self._fields_]:
            raise KeyError(f"{name} is not a field of {self.__name__}")
        else:
            offset = meta.offset
            sz = meta.size

        return bytes(memoryview(self).cast("c")[offset : offset + sz])

    @classmethod
    def from_dict(cls: Type[MB], data) -> MB:
        obj = cls()
        try:
            _from_dict(obj, data)
            return obj
        except Exception as e:
            raise JSONDecodingError(
                f"Unable to decode {type(obj).__name__} from {data}"
            )

    @classmethod
    def from_json(cls: Type[MB], s) -> MB:
        obj = cls.from_dict(json.loads(s))
        return obj

    @classmethod
    def from_random(cls: Type[MB]) -> MB:
        obj = _random_struct(cls())
        return obj

    def __str__(self) -> str:
        return self.pretty_print()

    def __eq__(self, other: Any) -> bool:
        if type(self) != type(other):
            return False

        return bytes(self) == bytes(other)


class RTMAJSONEncoder(json.JSONEncoder):
    """JSONEncoder object used to convert MessageData to json

    Example:
        data = json.dumps(msg, cls=pyrtma.encoding.RTMAJSONEncoder)
    """

    def default(self, o: Any) -> Any:
        if isinstance(o, MessageBase):
            return o.to_dict()

        if isinstance(o, ctypes.Array):
            return list(o)

        if isinstance(o, bytes):
            return [int(x) for x in o]

        return super().default(o)


def _from_dict(obj, data):
    for _name, ftype in obj._fields_:
        name = _name[1:]
        if issubclass(ftype, MessageBase):
            _from_dict(getattr(obj, name), data[name])
        elif issubclass(ftype, ctypes.Array):
            if issubclass(ftype._type_, MessageBase):  # type: ignore
                for i, elem in enumerate(getattr(obj, name)):
                    _from_dict(elem, data[name][i])
            elif ftype._type_ is ctypes.c_char:
                setattr(obj, name, data[name])
            else:
                getattr(obj, name)[:] = data[name]
        else:
            setattr(obj, name, data[name])


def _to_dict(obj) -> Dict[str, Any]:
    data = {}
    for _name, ftype in obj._fields_:
        name = _name[1:]
        if issubclass(ftype, MessageBase):
            data[name] = _to_dict(getattr(obj, name))
        elif issubclass(ftype, ctypes.Array):
            if issubclass(ftype._type_, MessageBase):  # type: ignore
                data[name] = []
                for elem in getattr(obj, name):
                    data[name].append(_to_dict(elem))
            elif ftype._type_ is ctypes.c_char:
                data[name] = getattr(obj, name)
            else:
                data[name] = getattr(obj, name)[:]
        else:
            data[name] = getattr(obj, name)

    return data
