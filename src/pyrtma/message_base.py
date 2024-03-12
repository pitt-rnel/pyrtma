import ctypes
import json
from dataclasses import is_dataclass
from typing import TypeVar, Any, Type, Dict
from .utils.print import print_ctype_array, hexdump
from .utils.random_fields import _random_struct
from .exceptions import JSONDecodingError

MB = TypeVar("MB", bound="MessageBase")


# MessageBase Metaclass - (for runtime ctypes field generation)
CStructType: type = type(
    ctypes.Structure
)  # technically incorrect typehint, but makes mypy happy


class MessageMeta(CStructType):
    """MessageMeta metaclass

    Responsible for generating ctypes fields from descriptor attributes prior to class creation
    """

    def __new__(cls, name, bases, namespace):
        fields = []
        for key in namespace.keys():
            if hasattr(namespace[key], "_ctype"):
                fname = "_" + key
                ftype = namespace[key]._ctype
                fields.append((fname, ftype))
        if fields:
            namespace["_fields_"] = fields
        elif "_fields_" not in namespace:
            # else important to not overwrite v1 message def fields
            namespace["_fields_"] = []

        return super().__new__(cls, name, bases, namespace)


# "abstract" base class for MessageHeader and MessageData
class MessageBase(ctypes.Structure, metaclass=MessageMeta):
    """MessageBase base class

    This class should be treated as if abstract and not instantiated directly.
    """

    @property
    def size(self) -> int:
        return ctypes.sizeof(self)

    def pretty_print(self, add_tabs=0) -> str:
        """Generate formatted message structure string for pretty printing

        Args:
            add_tabs (int, optional): Indentation level, used for recursively calling. Defaults to 0.

        Returns:
            str: Formatted string
        """
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
        """hexdump of message

        Args:
            length (int, optional): Row length. Defaults to 16.
            sep (str, optional): Separator for non-printable ascii chars. Defaults to " ".
        """
        hexdump(bytes(self), length, sep)

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary

        Returns:
            Dict[str, Any]: Message dictionary
        """
        return _to_dict(self)

    def to_json(self, minify: bool = False, **kwargs) -> str:
        """Convert message to json string

        Args:
            minify (bool, optional): Flag to minify (compact format). Defaults to False.
            kwargs for json.dumps

        Returns:
            str: json string
        """
        if minify:
            return json.dumps(
                self, cls=RTMAJSONEncoder, separators=(",", ":"), **kwargs
            )
        else:
            return json.dumps(self, cls=RTMAJSONEncoder, indent=2, **kwargs)

    def get_field_raw(self, name: str) -> bytes:
        """return copy of raw bytes for ctypes field

        Args:
            name (str): Message fieldname

        Raises:
            KeyError: Invalid fieldname

        Returns:
            bytes: Copy of message field data bytes
        """
        meta = getattr(type(self), f"_{name}")
        if name not in [x[0] for x in self._fields_]:
            raise KeyError(f"{name} is not a field of {self.__name__}")
        else:
            offset = meta.offset
            sz = meta.size

        return bytes(memoryview(self).cast("c")[offset : offset + sz])

    @classmethod
    def from_dict(cls: Type[MB], data: Dict[str, Any]) -> MB:
        """Generate message instance from dictionary

        Args:
            data (Dict[str, Any]): Message dictionary
        Raises:
            JSONDecodingError: Unable to decode dictionary
        """
        obj = cls()
        try:
            _from_dict(obj, data)
            return obj
        except Exception as e:
            raise JSONDecodingError(
                f"Unable to decode {type(obj).__name__} from {data}"
            )

    @classmethod
    def from_json(cls: Type[MB], s: str) -> MB:
        """Generate message instance from JSON string

        Args:
            s (str): Message JSON string
        """
        obj = cls.from_dict(json.loads(s))
        return obj

    @classmethod
    def from_random(cls: Type[MB]) -> MB:
        """Generate message instance with random values"""
        obj = _random_struct(cls())
        return obj

    @classmethod
    def copy(cls: Type[MB], m: MB) -> MB:
        """Generate a copy of a message structure

        Args:
            m: Message structure to copy
        """
        return cls.from_buffer_copy(m)

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
            if name in fnames and name[0] != "_":  # v1 fields
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
            if name in fnames and name[0] != "_":  # v1 fields
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
        """Default method to return serializable objects

        Args:
            o (Any): data to serialize

        Returns:
            Any: Serializable data
        """
        if isinstance(o, MessageBase) or (hasattr(o, "to_dict")):
            return o.to_dict()

        if isinstance(o, ctypes.Array):
            return list(o)

        if isinstance(o, (bytes, bytearray)):
            return [int(x) for x in o]

        return super().default(o)


def _from_dict(obj: MessageBase, data: Dict[str, Any]):
    """Helper function to set message fields from dictionary values

    Args:
        obj (MessageBase): Message object
        data (Dict[str, Any]): Message data dictionary
    """
    for _name, ftype in obj._fields_:
        name = _name[1:] if _name[0] == "_" else _name
        if issubclass(ftype, MessageBase):
            _from_dict(getattr(obj, name), data[name])
        elif issubclass(ftype, ctypes.Array):
            if issubclass(ftype._type_, MessageBase):  # type: ignore
                for i, elem in enumerate(getattr(obj, name)):
                    _from_dict(elem, data[name][i])
            elif ftype._type_ is ctypes.c_char:
                # list of characters is equivalent to str
                if type(data[name]) is list and all(
                    [(type(x) is str and len(x) <= 1) for x in data[name]]
                ):
                    data[name] = "".join(data[name])

                setattr(obj, name, data[name])
            else:
                getattr(obj, name)[:] = data[name]
        else:
            setattr(obj, name, data[name])


def _to_dict(obj: MessageBase) -> Dict[str, Any]:
    """Helper function to create dictionary from message fields

    Args:
        obj (MessageBase): Message object

    Returns:
        Dict[str, Any]: Dictionary
    """
    data: Dict[str, Any] = {}
    for _name, ftype in obj._fields_:
        name = _name[1:]
        if issubclass(ftype, MessageBase):
            data[name] = _to_dict(getattr(obj, name))
        elif issubclass(ftype, ctypes.Array):
            # Struct
            if issubclass(ftype._type_, MessageBase):  # type: ignore
                data[name] = []
                for elem in getattr(obj, name):
                    data[name].append(_to_dict(elem))

            # String
            elif ftype._type_ is ctypes.c_char:
                data[name] = getattr(obj, name)

            # Int8 Array
            elif ftype._type_ is ctypes.c_byte:
                data[name] = getattr(obj, name)[:].copy()

            # Uint8 or Byte Array
            elif ftype._type_ is ctypes.c_ubyte:
                if type(getattr(obj, name)).__name__ == "ByteArray":
                    # ByteArray
                    data[name] = bytes(getattr(obj, name)[:])
                else:
                    # Uint8Array
                    data[name] = getattr(obj, name)[:].copy()

            # Any other Array Type
            else:
                data[name] = getattr(obj, name)[:]
        else:
            data[name] = getattr(obj, name)

    return data
