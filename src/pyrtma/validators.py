from __future__ import annotations

import ctypes
import collections.abc as abc
import math

from typing import (
    List,
    ClassVar,
    Type,
    Generic,
    TypeVar,
    Union,
    Iterable,
    Optional,
    overload,
    Type,
    Sequence,
    Iterator,
)
from abc import abstractmethod, ABCMeta
import numbers
from contextlib import contextmanager
from contextvars import ContextVar


from .message_base import MessageBase

__all__ = [
    "Int8",
    "Int16",
    "Int32",
    "Int64",
    "Byte",
    "Uint8",
    "Uint16",
    "Uint32",
    "Uint64",
    "Float",
    "Double",
    "Char",
    "Struct",
    "String",
    "ByteArray",
    "IntArray",
    "FloatArray",
    "StructArray",
    "disable_message_validation",
]

_VALIDATION_ENABLED: ContextVar[bool] = ContextVar("_VALIDATION_ENABLED", default=True)


@contextmanager
def disable_message_validation():
    """Context manager function to temporarily disable message field validation
    Use with `with` keyword:
    `with disable_message_validation():`
    """
    token = _VALIDATION_ENABLED.set(False)
    yield
    _VALIDATION_ENABLED.reset(token)


_P = TypeVar("_P")  # Parent
_V = TypeVar("_V")  # Value


class FieldValidator(Generic[_P, _V], metaclass=ABCMeta):
    """Abstract base class for all message field validator descriptors"""

    def __init__(self) -> None:
        self._ctype: Type[ctypes._CData] = ctypes._CData

    def __set_name__(self, owner: _P, name: str):
        self._owner = owner
        self._public_name = name
        self._private_name = "_" + name

    @abstractmethod
    def __get__(self, obj: _P, objtype=None): ...

    @abstractmethod
    def __set__(self, obj: _P, value: _V): ...

    @abstractmethod
    def validate_one(self, value: _V): ...

    @abstractmethod
    def validate_many(self, value: Iterable[_V]): ...


class FloatValidatorBase(FieldValidator[_P, float], Generic[_P], metaclass=ABCMeta):
    """Abstract base class for float type validators"""

    @abstractmethod
    def __init__(self, *args) -> None:
        self._ctype: Type[ctypes._SimpleCData] = ctypes.c_float

    def __get__(self, obj: _P, objtype=None) -> float:
        return getattr(obj, self._private_name)

    def __set__(self, obj: _P, value: float):
        if _VALIDATION_ENABLED.get():
            self.validate_one(value)
        setattr(obj, self._private_name, value)

    def validate_one(self, value: float):
        """Validate a float value

        Args:
            value (float): Float value

        Raises:
            TypeError: Wrong type
            ValueError: Value cannot be precisely represented with this datatype
        """

        if not isinstance(value, numbers.Number):
            raise TypeError(f"Expected {value} to be a float")

        if math.isinf(self._ctype(value).value):
            raise ValueError(
                f"The {value} can not be represented as a {type(self).__name__}"
            )

    def validate_many(self, value: Iterable[float]):
        """Validate multiple float values

        Args:
            value (Iterable[float]): Iterable of floats to validate

        Raises:
            TypeError: Wrong type
            ValueError: Value cannot be precisely represented with this datatype
        """
        if any(not isinstance(v, numbers.Number) for v in value):
            raise TypeError(f"Expected {value!r} to be a float.")

        if any(math.isinf(self._ctype(v).value) for v in value):
            raise ValueError(
                f"{value} contains value(s) that can not be represented as a {type(self).__name__}"
            )

    def __repr__(self):
        return f"{type(self).__name__} at 0x{id(self):016X}"


class Float(FloatValidatorBase):
    """32-bit Float validator class"""

    def __init__(self, *args) -> None:
        self._ctype: Type[ctypes._SimpleCData] = ctypes.c_float


class Double(FloatValidatorBase):
    """Double (64-bit float) validator class"""

    def __init__(self, *args) -> None:
        self._ctype: Type[ctypes._SimpleCData] = ctypes.c_double


# Base Class for int validator fields
class IntValidatorBase(FieldValidator[_P, int], Generic[_P], metaclass=ABCMeta):
    """Abstract base class for integer type validators"""

    _size: ClassVar[int] = 1
    _unsigned: ClassVar[bool] = False
    _min: ClassVar[int] = 0
    _max: ClassVar[int] = 2**8 - 1

    @abstractmethod
    def __init__(self, *args): ...

    @property
    def size(self) -> int:
        return self._size

    @property
    def unsigned(self) -> bool:
        return self._unsigned

    @property
    def min(self) -> int:
        return self._min

    @property
    def max(self) -> int:
        return self._max

    def __get__(self, obj: _P, objtype=None) -> int:
        return getattr(obj, self._private_name)

    def __set__(self, obj: _P, value: int):
        if _VALIDATION_ENABLED.get():
            self.validate_one(value)
        setattr(obj, self._private_name, value)

    def validate_one(self, value: int):
        """Validate an integer value

        Args:
            value (int): Integer to validate

        Raises:
            TypeError: Wrong type
            ValueError: Integer out of range for this datatype
        """
        if not isinstance(value, numbers.Integral):
            raise TypeError(f"Expected {value} to be an int")

        if value < self._min:
            raise ValueError(f"Expected {value} to be at least {self._min}")
        if value > self._max:
            raise ValueError(f"Expected {value} to be no more than {self._max}")

    def validate_many(self, value: Iterable[int]):
        """Validate multiple integer values

        Args:
            value (Iterable[int]): Iterable of integers to validate

        Raises:
            TypeError: Wrong type
            ValueError: Integer out of range for this datatype
        """
        if any(not isinstance(v, numbers.Integral) for v in value):
            raise TypeError(f"Expected {value} to be an int.")

        if any((v < self._min for v in value)):
            raise ValueError(f"Expected {value} to be {self._min} or greater.")

        if any((v > self._max for v in value)):
            raise ValueError(f"Expected {value} to be no more than {self._max}")

    def __repr__(self):
        return f"{type(self).__name__}(size={self.size}, unsigned={self.unsigned}) at 0x{id(self):016X}"


class Int8(IntValidatorBase):
    """Validator for 8-bit integers"""

    _size: ClassVar[int] = 1
    _unsigned: ClassVar[bool] = False
    _min: ClassVar[int] = -(2**7)
    _max: ClassVar[int] = 2**7 - 1

    def __init__(self, *args) -> None:
        self._ctype: Type[ctypes._SimpleCData] = ctypes.c_int8


class Int16(IntValidatorBase):
    """Validator for 16-bit integers"""

    _size: ClassVar[int] = 2
    _unsigned: ClassVar[bool] = False
    _min: ClassVar[int] = -(2**15)
    _max: ClassVar[int] = 2**15 - 1

    def __init__(self, *args) -> None:
        self._ctype: Type[ctypes._SimpleCData] = ctypes.c_int16


class Int32(IntValidatorBase):
    """Validator for 32-bit integers"""

    _size: ClassVar[int] = 4
    _unsigned: ClassVar[bool] = False
    _min: ClassVar[int] = -(2**31)
    _max: ClassVar[int] = 2**31 - 1

    def __init__(self, *args) -> None:
        self._ctype: Type[ctypes._SimpleCData] = ctypes.c_int32


class Int64(IntValidatorBase):
    """Validator for 64-bit integers"""

    _size: ClassVar[int] = 8
    _unsigned: ClassVar[bool] = False
    _min: ClassVar[int] = -(2**63)
    _max: ClassVar[int] = 2**63 - 1

    def __init__(self, *args) -> None:
        self._ctype: Type[ctypes._SimpleCData] = ctypes.c_int64


class Uint8(IntValidatorBase):
    """Validator for unsigned 8-bit integers"""

    _size: ClassVar[int] = 1
    _unsigned: ClassVar[bool] = True
    _min: ClassVar[int] = 0
    _max: ClassVar[int] = 2**8 - 1

    def __init__(self, *args) -> None:
        self._ctype: Type[ctypes._SimpleCData] = ctypes.c_uint8


class Uint16(IntValidatorBase):
    """Validator for unsigned 16-bit integers"""

    _size: ClassVar[int] = 2
    _unsigned: ClassVar[bool] = True
    _min: ClassVar[int] = 0
    _max: ClassVar[int] = 2**16 - 1

    def __init__(self, *args) -> None:
        self._ctype: Type[ctypes._SimpleCData] = ctypes.c_uint16


class Uint32(IntValidatorBase):
    """Validator for unsigned 32-bit integers"""

    _size: ClassVar[int] = 4
    _unsigned: ClassVar[bool] = True
    _min: ClassVar[int] = 0
    _max: ClassVar[int] = 2**32 - 1

    def __init__(self, *args) -> None:
        self._ctype: Type[ctypes._SimpleCData] = ctypes.c_uint32


class Uint64(IntValidatorBase):
    """Validator for unsigned 64-bit integers"""

    _size: ClassVar[int] = 8
    _unsigned: ClassVar[bool] = True
    _min: ClassVar[int] = 0
    _max: ClassVar[int] = 2**64 - 1

    def __init__(self, *args) -> None:
        self._ctype: Type[ctypes._SimpleCData] = ctypes.c_uint64


class Byte(FieldValidator[_P, int], Generic[_P]):
    """Validator for single byte values"""

    _size: ClassVar[int] = 1
    _unsigned: ClassVar[bool] = True
    _min: ClassVar[int] = 0
    _max: ClassVar[int] = 2**8 - 1

    def __init__(self, *args) -> None:
        self._ctype: Type[ctypes._SimpleCData] = ctypes.c_ubyte

    @property
    def size(self) -> int:
        return self._size

    @property
    def unsigned(self) -> bool:
        return self._unsigned

    @property
    def min(self) -> int:
        return self._min

    @property
    def max(self) -> int:
        return self._max

    def __get__(self, obj: _P, objtype=None) -> int:
        return getattr(obj, self._private_name)

    def __set__(self, obj: _P, value: Union[int, bytes, bytearray]):
        if _VALIDATION_ENABLED.get():
            self.validate_one(value)
            if isinstance(value, (bytes, bytearray)):
                int_value = int.from_bytes(value, "little")
                setattr(obj, self._private_name, int_value)
                return
        setattr(obj, self._private_name, value)

    def validate_one(self, value: Union[int, bytes, bytearray]):
        """validate a single byte value

        Args:
            value (Union[int, bytes, bytearray]): Byte value to validate

        Raises:
            ValueError: Value out of range
            TypeError: Wrong type
        """

        if isinstance(value, int):
            if value < self._min:
                raise ValueError(f"Expected {value} to be at least {self._min}")
            if value > self._max:
                raise ValueError(f"Expected {value} to be no more than {self._max}")
            return

        if not isinstance(value, (bytes, bytearray)):
            raise TypeError(f"Expected {value!r} to be bytes or int")

        if len(value) != 1:
            raise ValueError(f"Expected {value!r} to be no longer than 1")

    def validate_many(self, value: Union[Iterable[int], bytes, bytearray]):
        """Validate multiple byte values

        Args:
            value (Union[Iterable[int], bytes, bytearray]): Byte values to validate

        Raises:
            TypeError: Wrong type
            ValueError: Value out of range
        """
        if isinstance(value, (bytes, bytearray)):
            return

        if any(not isinstance(v, int) for v in value):
            raise TypeError(
                f"Expected {value} to be an int sequence, bytes, or bytearray."
            )

        if any((v < self._min for v in value)):
            raise ValueError(f"Expected {value} to be {self._min} or greater.")

        if any((v > self._max for v in value)):
            raise ValueError(f"Expected {value} to be no more than {self._max}")

    def __repr__(self):
        return f"Byte(len=1) at 0x{id(self):016X}"


class String(FieldValidator[_P, str], Generic[_P]):
    """Validator for strings (char arrays)"""

    def __init__(self, len: int):
        assert len > 1
        self.len = len
        self._ctype = ctypes.c_char * len

    def __get__(self, obj: _P, objtype=None) -> str:
        return getattr(obj, self._private_name).decode("ascii")

    def __set__(self, obj: _P, value: str):
        if _VALIDATION_ENABLED.get():
            self.validate_one(value)
        setattr(obj, self._private_name, value.encode("ascii"))

    def validate_one(self, value: str):
        """Validate a string value

        Args:
            value (str): String value

        Raises:
            TypeError: Wrong type
            ValueError: String exceeds max length
        """
        if not isinstance(value, str):
            raise TypeError(f"Expected {value} to be a str")

        if len(value) > self.len:
            raise ValueError(f'Expected "{value}" to be no longer than {self.len}')

        if any(ord(c) > 127 for c in value):
            raise TypeError(f"Expected {value} to only containt valid ascii points")

    def validate_many(self, value):
        """Validate multiple strings

        Not implemented

        Raises:
            NotImplementedError
        """
        raise NotImplementedError

    def __repr__(self):
        return f"String(len={self.len}) at 0x{id(self):016X}"


_FV = TypeVar("_FV", bound=FieldValidator)


class Char(String):
    """Validator for scalar char values"""

    def __init__(self) -> None:
        self._ctype = ctypes.c_char
        self.len = 1

    def __repr__(self):
        return f"Char() at 0x{id(self):016X}"


class ArrayField(FieldValidator, abc.Sequence, Generic[_FV]):
    """Array field validator base class"""

    def __init__(self, validator: Type[_FV], len: int):
        """Array field validator base class

        Args:
            validator (Type[_FV]): Field validator class for datatype
            len (int): Field length
        """
        self._validator: FieldValidator = validator()
        self._len = len
        self._bound_obj: Optional[MessageBase] = None
        self._ctype = self._validator._ctype * len

    @classmethod
    def _bound(cls, obj: ArrayField[_FV], bound_obj: MessageBase) -> ArrayField[_FV]:
        new_obj = super().__new__(cls)
        new_obj._bound_obj = bound_obj
        new_obj._validator = obj._validator
        new_obj._len = obj._len
        new_obj._ctype = obj._ctype
        new_obj._owner = obj._owner
        new_obj._public_name = obj._public_name
        new_obj._private_name = obj._private_name

        return new_obj

    def __get__(self, obj: MessageBase, objtype=None) -> ArrayField[_FV]:
        """Return an Array bound to a message obj instance."""
        return ArrayField._bound(self, obj)

    def __set__(self, obj: MessageBase, value: Union[ArrayField[_FV], Sequence]):
        if isinstance(value, ArrayField):
            if _VALIDATION_ENABLED.get():
                self.validate_array(value)
            setattr(
                obj, self._private_name, getattr(value._bound_obj, value._private_name)
            )
        else:
            self.__get__(obj).__setitem__(slice(None), value)

    def __getitem__(self, key):
        if self._bound_obj is None:
            raise AttributeError("Array descriptor is not bound to an instance object.")

        return getattr(self._bound_obj, self._private_name)[key]

    def __iter__(self) -> Iterator:
        return iter(self[:])

    def __setitem__(self, key, value):
        if self._bound_obj is None:
            raise AttributeError("Array descriptor is not bound to an instance object.")

        if _VALIDATION_ENABLED.get():
            if isinstance(value, abc.Iterable):
                self.validate_many(value)
            else:
                self.validate_one(value)

        getattr(self._bound_obj, self._private_name)[key] = value

    def __len__(self) -> int:
        return self._len

    def __repr__(self) -> str:
        return f"ArrayField({type(self._validator).__name__}, len={self._len}) at 0x{id(self):016X}"

    def __str__(self):
        if self._bound_obj:
            return str(getattr(self._bound_obj, self._private_name)[:])
        else:
            return self.__repr__()

    def __eq__(self, value) -> bool:
        if not isinstance(value, abc.Sequence):
            return False
        if len(value) != self._len:
            return False
        for self_val, comp_val in zip(self, value):
            if self_val != comp_val:
                return False
        return True

    def validate_one(self, value):
        """Validate one value

        Args:
            value: Value to validate
        """
        self._validator.validate_one(value)

    def validate_many(self, value):
        """Validate multiple values

        Args:
            value: Values to validate
        """
        self._validator.validate_many(value)

    def validate_array(self, value: ArrayField):
        """Validate array

        Args:
            value (ArrayField): Array value to validate

        Raises:
            TypeError: Wrong type
        """
        if not isinstance(value, type(self)):
            raise TypeError(
                f"Expected a {self.__class__.__name__}({type(self._validator).__name__}). Got {type(value).__name__}."
            )

        if not isinstance(value._validator, type(self._validator)):
            raise TypeError(
                f"Expected an {self.__class__.__name__}({type(self._validator).__name__}, {len(self)}). Got {type(value).__name__}({type(value._validator).__name__}, {len(value)})."
            )

        if len(value) != len(self):
            raise ValueError(
                f"Array size mismatch. Expected an {self.__class__.__name__}({type(self._validator).__name__}, {len(self)}). Got {type(value).__name__}({type(value._validator).__name__}, {len(value)})."
            )

        if value._bound_obj is None:
            raise ValueError(
                f"The instance of {type(value).__name__}({type(value._validator).__name__}, {len(value)}) is not bound to a MessageBase object."
            )

        return


_IV = TypeVar("_IV", bound=IntValidatorBase)


class IntArray(ArrayField[_IV], Generic[_IV]):
    """IntArray validator class"""

    def __init__(self, validator: Type[_IV], len: int):
        """IntArray validator class

        Args:
            validator (Type[IV]): Field validator class for Int type
            len (int): Field length
        """
        self._validator = validator()
        self._len = len
        self._bound_obj: Optional[MessageBase] = None
        self._ctype = self._validator._ctype * len

    @classmethod
    def _bound(cls, obj: ArrayField[_IV], bound_obj: MessageBase) -> IntArray[_IV]:
        new_obj = super().__new__(cls)
        new_obj._bound_obj = bound_obj
        new_obj._validator = obj._validator
        new_obj._len = obj._len
        new_obj._ctype = obj._ctype
        new_obj._owner = obj._owner
        new_obj._public_name = obj._public_name
        new_obj._private_name = obj._private_name

        return new_obj

    def __get__(self, obj: MessageBase, objtype=None) -> IntArray[_IV]:
        """Return an Array bound to a message obj instance."""
        return IntArray._bound(self, obj)

    def __set__(self, obj: MessageBase, value: Union[ArrayField[_IV], Sequence[int]]):
        if isinstance(value, ArrayField):
            if _VALIDATION_ENABLED.get():
                self.validate_array(value)
            setattr(
                obj, self._private_name, getattr(value._bound_obj, value._private_name)
            )
        else:
            self.__get__(obj).__setitem__(slice(None), value)

    @overload
    def __getitem__(self, key: int) -> int: ...

    @overload
    def __getitem__(self, key: slice) -> List[int]: ...

    def __getitem__(self, key) -> Union[int, List[int]]:
        if self._bound_obj is None:
            raise AttributeError("Array descriptor is not bound to an instance object.")

        return getattr(self._bound_obj, self._private_name)[key]

    def __iter__(self) -> Iterator[int]:
        return iter(self[:])

    def __repr__(self) -> str:
        return f"IntArray({type(self._validator).__name__}, len={self._len}) at 0x{id(self):016X}"


_FPV = TypeVar("_FPV", bound=FloatValidatorBase)


class ByteArray(ArrayField[Byte]):
    """Validator class for Bytes arrays"""

    def __init__(self, len: int):
        """Validator class for Bytes arrays

        Args:
            len (int): Byte array length
        """
        assert len > 1
        self._validator = Byte()
        self._len = len
        self._bound_obj: Optional[MessageBase] = None
        self._ctype = ctypes.c_ubyte * len

    @classmethod
    def _bound(cls, obj: ArrayField[Byte], bound_obj: MessageBase) -> ByteArray:
        new_obj = super().__new__(cls)
        new_obj._bound_obj = bound_obj
        new_obj._validator = obj._validator
        new_obj._len = obj._len
        new_obj._ctype = obj._ctype
        new_obj._owner = obj._owner
        new_obj._public_name = obj._public_name
        new_obj._private_name = obj._private_name

        return new_obj

    def __get__(self, obj: MessageBase, objtype=None) -> ByteArray:
        return ByteArray._bound(self, obj)

    def __set__(
        self,
        obj: MessageBase,
        value: Union[ArrayField[Byte], Sequence[int], bytes, bytearray],
    ):
        if isinstance(value, ArrayField):
            if _VALIDATION_ENABLED.get():
                self.validate_array(value)
            setattr(
                obj, self._private_name, getattr(value._bound_obj, value._private_name)
            )
        else:
            self.__get__(obj).__setitem__(slice(None), value)

    @overload
    def __getitem__(self, key: int) -> bytearray: ...

    @overload
    def __getitem__(self, key: slice) -> bytearray: ...

    def __getitem__(self, key) -> bytearray:
        if self._bound_obj is None:
            raise AttributeError("Array descriptor is not bound to an instance object.")

        int_vals = getattr(self._bound_obj, self._private_name)[key]
        try:
            barray = [x.to_bytes(1, "little") for x in int_vals]
        except TypeError:
            barray = [int_vals.to_bytes(1, "little")]

        return bytearray().join(barray)

    def __iter__(self) -> Iterator[bytearray]:  # Generator[_S, None, None]:
        for i in range(self._len):
            yield self.__getitem__(i)

    def __setitem__(self, key, value):
        if self._bound_obj is None:
            raise AttributeError("Array descriptor is not bound to an instance object.")

        if _VALIDATION_ENABLED.get():
            if isinstance(value, abc.Iterable):
                self.validate_many(value)
            else:
                self.validate_one(value)

            if isinstance(value, (bytes, bytearray)):
                if len(value) == 1:
                    value = int.from_bytes(value, "little")
                else:
                    value = [v for v in value]

        getattr(self._bound_obj, self._private_name)[key] = value

    def __repr__(self) -> str:
        return f"ByteArray(len={self._len}) at 0x{id(self):016X}"


class FloatArray(ArrayField[_FPV], Generic[_FPV]):
    """Validator class for float arrays"""

    def __init__(self, validator: Type[_FPV], len: int):
        """Validator class for float arrays

        Args:
            validator (Type[_FPV]): Float type validator
            len (int): Array length
        """
        self._validator = validator()
        self._len = len
        self._bound_obj: Optional[MessageBase] = None
        self._ctype = self._validator._ctype * len

    @classmethod
    def _bound(cls, obj: ArrayField[_FPV], bound_obj: MessageBase) -> FloatArray[_FPV]:
        new_obj = super().__new__(cls)
        new_obj._bound_obj = bound_obj
        new_obj._validator = obj._validator
        new_obj._len = obj._len
        new_obj._ctype = obj._ctype
        new_obj._owner = obj._owner
        new_obj._public_name = obj._public_name
        new_obj._private_name = obj._private_name

        return new_obj

    def __get__(self, obj: MessageBase, objtype=None) -> FloatArray[_FPV]:
        """Return an Array bound to a message obj instance."""
        return FloatArray._bound(self, obj)

    def __set__(
        self, obj: MessageBase, value: Union[ArrayField[_FPV], Sequence[float]]
    ):
        if isinstance(value, ArrayField):
            if _VALIDATION_ENABLED.get():
                self.validate_array(value)
            setattr(
                obj, self._private_name, getattr(value._bound_obj, value._private_name)
            )
        else:
            self.__get__(obj).__setitem__(slice(None), value)

    @overload
    def __getitem__(self, key: int) -> float: ...

    @overload
    def __getitem__(self, key: slice) -> List[float]: ...

    def __getitem__(self, key) -> Union[float, List[float]]:
        if self._bound_obj is None:
            raise AttributeError("Array descriptor is not bound to an instance object.")

        return getattr(self._bound_obj, self._private_name)[key]

    def __iter__(self) -> Iterator[float]:
        return iter(self[:])

    def __repr__(self) -> str:
        return f"FloatArray({type(self._validator).__name__}, len={self._len}) at 0x{id(self):016X}"


_S = TypeVar("_S", bound=MessageBase)


class Struct(FieldValidator, Generic[_S]):
    """Validator class for Structures"""

    def __init__(self, _ctype: Type[_S]):
        self._ctype = _ctype

    def __get__(self, obj, objtype=None) -> _S:
        return getattr(obj, self._private_name)

    @overload
    def __set__(self, obj: MessageBase, value: _S): ...

    @overload
    def __set__(self, obj: StructArray, value: Struct[_S]): ...

    def __set__(self, obj, value):
        if _VALIDATION_ENABLED.get():
            self.validate_one(value)
        # Note: ctypes already copies the data here
        setattr(obj, self._private_name, value)

    def validate_one(self, value: _S):
        """Validate a structure

        Args:
            value (_S): Structure value to validate

        Raises:
            TypeError: Wrong type
        """
        if not isinstance(value, self._ctype):
            raise TypeError(f"Expected {self._ctype.__name__}")

    def validate_many(self, value: Iterable[_S]):
        """Validate multiple structures

        Args:
            value (Iterable[_S]): Iterable of structures to validate

        Raises:
            TypeError: Wrong type
        """
        if any(not isinstance(v, self._ctype) for v in value):
            raise TypeError(f"Expected {value} to be an {self._ctype.__name__}.")

    def __repr__(self) -> str:
        return f"Struct({self._ctype.__name__}) at 0x{id(self):016X}"


class StructArray(FieldValidator, abc.Sequence, Generic[_S]):
    """Validator for structure arrays"""

    def __init__(self, msg_struct: Type[_S], len: int):
        """Validator for structure arrays

        Args:
            msg_struct (Type[_S]): Structure class
            len (int): Array length
        """
        self._validator = Struct(msg_struct)
        self._len = len
        self._bound_obj: Optional[MessageBase] = None
        self._ctype = self._validator._ctype * len

    @classmethod
    def _bound(cls, obj: StructArray[_S], bound_obj: MessageBase) -> StructArray[_S]:
        new_obj: StructArray[_S] = super().__new__(cls)
        new_obj._bound_obj = bound_obj
        new_obj._validator = obj._validator
        new_obj._len = obj._len
        new_obj._ctype = obj._ctype
        new_obj._owner = obj._owner
        new_obj._public_name = obj._public_name
        new_obj._private_name = obj._private_name

        return new_obj

    def __get__(self, obj: MessageBase, objtype=None) -> StructArray[_S]:
        """Return an StructArray bound to a message obj instance."""
        return StructArray._bound(self, obj)

    def __set__(self, obj, value: Union[StructArray, Sequence[_S]]):
        if isinstance(value, StructArray):
            if _VALIDATION_ENABLED.get():
                self.validate_array(value)
            setattr(
                obj, self._private_name, getattr(value._bound_obj, value._private_name)
            )
        else:
            self.__get__(obj).__setitem__(slice(None), value)

    @overload
    def __getitem__(self, key: int) -> _S: ...

    @overload
    def __getitem__(self, key: slice) -> List[_S]: ...

    def __getitem__(self, key) -> Union[_S, List[_S]]:
        if self._bound_obj is None:
            raise AttributeError("Array descriptor is not bound to an instance object.")
        return getattr(self._bound_obj, self._private_name)[key]

    def __iter__(self) -> Iterator[_S]:
        return iter(self[:])

    def __setitem__(self, key, value):
        if self._bound_obj is None:
            raise AttributeError(
                "StructArray descriptor is not bound to an instance object."
            )

        if _VALIDATION_ENABLED.get():
            if isinstance(value, abc.Iterable):
                self.validate_many(value)
            else:
                self.validate_one(value)

        getattr(self._bound_obj, self._private_name)[key] = value

    def __len__(self) -> int:
        return self._len

    def __repr__(self) -> str:
        return f"StructArray({self._validator._ctype.__name__}, len={self._len}) at 0x{id(self):016X}"

    def __str__(self):
        return self.pretty_print()

    def pretty_print(self, add_tabs=0):
        """Generate formatted string for structure array

        Args:
            add_tabs (int, optional): Indent level. Defaults to 0.

        Returns:
            str: Formatted string
        """
        if self._bound_obj:
            max_len = 5
            val = getattr(self._bound_obj, self._private_name)
            tab = "\t" * add_tabs
            if self._len <= max_len:
                return (
                    f"{tab}[\n"
                    + "\n".join(x.pretty_print(add_tabs) for x in val)
                    + f"\n{tab}]"
                )
            else:
                return (
                    f"{tab}[\n"
                    + "\n".join(
                        f"{val[i].pretty_print(add_tabs)}" for i in range(max_len)
                    )
                    + f"\n{tab}...]"
                )
        else:
            return self.__repr__()

    def __eq__(self, value) -> bool:
        if not isinstance(value, abc.Sequence):
            return False
        if len(value) != self._len:
            return False
        for self_val, comp_val in zip(self, value):
            if self_val != comp_val:
                return False
        return True

    def validate_one(self, value: _S):
        """Validate a structure

        Args:
            value (_S): Structure value to validate
        """
        self._validator.validate_one(value)

    def validate_many(self, value: Iterable[_S]):
        """Validate multiple structures

        Args:
            value (Iterable[_S]): Structure values to validate
        """
        self._validator.validate_many(value)

    def validate_array(self, value: StructArray[_S]):
        """Validate structure array

        Args:
            value (StructArray[_S]): StructArray to validate

        Raises:
            TypeError: Wrong type
        """
        if not isinstance(value, StructArray):
            raise TypeError(
                f"Expected a StructArray({self._validator._ctype.__name__}, {len(self)}). Got {type(value).__name__}."
            )

        if value._validator._ctype is not self._validator._ctype:
            raise TypeError(
                f"Expected a StructArray({self._validator._ctype.__name__}, {len(self)}). Got {type(value).__name__}({value._validator._ctype.__name__}, {len(value)})."
            )

        if len(value) != len(self):
            raise ValueError(
                f"Array size mismatch. Expected an {self.__class__.__name__}({self._validator._ctype.__name__}, {len(self)}). Got {type(value).__name__}({value._validator._ctype.__name__}, {len(value)})."
            )

        if value._bound_obj is None:
            raise ValueError(
                f"The instance of {type(value).__name__}({value._validator._ctype.__name__}, {len(value)}) is not bound to a MessageBase object."
            )

        return
