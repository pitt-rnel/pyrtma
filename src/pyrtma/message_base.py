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
        max_len = 20
        pstr = "\t" * add_tabs + f"{type(self).__name__}:"
        for field_name, field_type in self._fields_:
            if field_name[0] == "_":
                field_name = field_name[1:]
            val = getattr(self, field_name)
            class_name = field_type.__name__
            if type(val) is str:
                sval = f'"{val}"'
            elif hasattr(val, "pretty_print"):
                sval = val.pretty_print(add_tabs + 1)
            # expand arrays
            elif hasattr(val, "__len__"):
                if hasattr(val, "_type_"):
                    class_name = val._type_.__name__
                if hasattr(val, "pretty_print"):
                    sval = val.pretty_print(add_tabs + 1)
                elif (
                    type(val) not in (bytes, bytearray)
                    and type(val[0]) is not bytearray
                ):
                    sval = print_ctype_array(val)
                elif len(val) > max_len:
                    sval = f"{val[:max_len]}..."
                else:
                    sval = str(val)
            else:
                sval = str(val)
            if hasattr(val, "pretty_print"):
                pstr += (
                    f"\n"
                    + "\t" * (add_tabs + 1)
                    + f"{field_name} = ({class_name})\n{sval}"
                )
            else:
                pstr += (
                    f"\n"
                    + "\t" * (add_tabs + 1)
                    + f"{field_name} = ({class_name}){sval}"
                )
        return pstr

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

    def __getattribute__(self, name: str) -> Any:
        # for backwards compatibility with messages without descriptors
        # can be deprecated
        value = super().__getattribute__(name)
        # need to convert chars from bytes to str
        if type(value) is bytes:
            fnames, ftypes = zip(*self._fields_)
            if name in fnames:
                i = fnames.index(name)
                ftype = ftypes[i]
                if ftype is ctypes.c_char or (
                    issubclass(ftype, ctypes.Array) and ftype._type_ is ctypes.c_char
                ):
                    return value.decode()
        return value

    def __setattr__(self, name: str, value: Any) -> None:
        # for backwards compatibility with messages without descriptors
        # can be deprecated
        if type(value) is str:
            fnames, ftypes = zip(*self._fields_)
            if name in fnames:
                i = fnames.index(name)
                ftype = ftypes[i]
                if ftype is ctypes.c_char or (
                    issubclass(ftype, ctypes.Array) and ftype._type_ is ctypes.c_char
                ):
                    value = value.encode()
        super().__setattr__(name, value)


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
