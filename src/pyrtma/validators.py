from __future__ import annotations

import ctypes
import collections.abc as abc
import math

from typing import overload, TYPE_CHECKING, TypeVar, Generic

from abc import abstractmethod, ABCMeta
from contextlib import contextmanager
from contextvars import ContextVar

if TYPE_CHECKING:
    import numpy.typing as npt
    import numpy as np
    from typing_extensions import Self
    from typing import (
        List,
        ClassVar,
        Type,
        Union,
        Iterable,
        Optional,
        Type,
        Sequence,
        Iterator,
    )

try:
    import numpy as np
except ImportError:
    pass

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
    "Int8Array",
    "Int16Array",
    "Int32Array",
    "Int64Array",
    "Uint8Array",
    "Uint16Array",
    "Uint32Array",
    "Uint64Array",
    "FloatArray",
    "Float32Array",
    "DoubleArray",
    "StructArray",
    "disable_message_validation",
]

_VALIDATION_ENABLED: ContextVar[bool] = ContextVar("_VALIDATION_ENABLED", default=True)


@contextmanager
def disable_message_validation(ignore=False):
    """Context manager function to temporarily disable message field validation
    Use with `with` keyword:
    `with disable_message_validation():`

    Optionally pass in ignore=True to do nothing, e.g. for debugging:

    ```
    DEBUG = True
    with disable_message_validation(ignore=DEBUG):
        ... # disable validation unless DEBUG is True
    ```
    """
    if not ignore:
        token = _VALIDATION_ENABLED.set(False)
        yield
        _VALIDATION_ENABLED.reset(token)
    else:
        yield  # dummy context


_P = TypeVar("_P")  # Parent
_V = TypeVar("_V")  # Value
_C = TypeVar("_C")  # CType


class FieldValidator(Generic[_P, _V], metaclass=ABCMeta):
    """Abstract base class for all message field validator descriptors"""

    @abstractmethod
    def __init__(self) -> None:
        self._ctype: Type[ctypes._CData]

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


class FloatValidatorBase(FieldValidator[_P, float], Generic[_P, _C], metaclass=ABCMeta):
    """Abstract base class for float type validators"""

    @abstractmethod
    def __init__(self, *args) -> None:
        self._ctype: Type[ctypes._SimpleCData] = ctypes.c_float

    def __get__(self, obj: _P, objtype=None) -> float:
        return getattr(obj, self._private_name)

    def __set__(self, obj: _P, value: Union[float, int, _C]):
        if _VALIDATION_ENABLED.get():
            self.validate_one(value)
        setattr(obj, self._private_name, value)

    def validate_one(self, value: Union[float, int, _C, np.floating]):
        """Validate a float value

        Args:
            value (float): Float value

        Raises:
            TypeError: Wrong type
            ValueError: Value cannot be precisely represented with this datatype
        """

        if isinstance(value, self._ctype):
            return

        if not isinstance(value, (float, int)):
            try:
                if not isinstance(value, np.floating):
                    raise TypeError(f"Expected {value} to be a float")
            except NameError:
                raise TypeError(f"Expected {value} to be a float")

        if math.isinf(self._ctype(value).value):
            raise ValueError(
                f"The {value} can not be represented as a {type(self).__name__}"
            )

    def validate_many(self, value: Iterable[Union[float, int]]):
        """Validate multiple float values

        Args:
            value (Iterable[float]): Iterable of floats to validate

        Raises:
            TypeError: Wrong type
            ValueError: Value cannot be precisely represented with this datatype
        """

        # Note: This may not be worth it since this is a rare overflow case.
        try:
            if math.isinf(self._ctype(max(value)).value) or math.isinf(
                self._ctype(min(value)).value
            ):
                raise ValueError(
                    f"{value} contains value(s) that can not be represented as a {type(self).__name__}"
                )
        except TypeError:
            raise TypeError(f"Expected {value!r} to contain all float types.")

    def __repr__(self):
        return f"{type(self).__name__} at 0x{id(self):016X}"


class Float(FloatValidatorBase[_P, ctypes.c_float], Generic[_P]):
    """32-bit Float validator class"""

    def __init__(self, *args) -> None:
        self._ctype: Type[ctypes._SimpleCData] = ctypes.c_float

    def validate_one(self, value: Union[float, int, np.float32, ctypes.c_float]):
        try:
            if isinstance(value, np.floating) and not isinstance(value, np.float32):  # type: ignore
                raise TypeError(f"Expected {value} to be a float32")
        except NameError:
            pass
        super().validate_one(value)


class Double(FloatValidatorBase[_P, ctypes.c_double], Generic[_P]):
    """Double (64-bit float) validator class"""

    def __init__(self, *args) -> None:
        self._ctype: Type[ctypes._SimpleCData] = ctypes.c_double

    def validate_one(self, value: Union[float, int, np.float64, ctypes.c_double]):
        try:
            if isinstance(value, np.floating) and not isinstance(value, np.float64):
                raise TypeError(f"Expected {value} to be a float32")
        except NameError:
            pass
        super().validate_one(value)


# Base Class for int validator fields
class IntValidatorBase(FieldValidator[_P, int], Generic[_P, _C], metaclass=ABCMeta):
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

    def __set__(self, obj: _P, value: Union[int, _C]):
        if _VALIDATION_ENABLED.get():
            self.validate_one(value)
        setattr(obj, self._private_name, value)

    def validate_one(self, value: Union[int, _C, np.integer]):
        """Validate an integer value

        Args:
            value (int): Integer to validate

        Raises:
            TypeError: Wrong type
            ValueError: Integer out of range for this datatype
        """

        if isinstance(value, self._ctype):
            return

        if not isinstance(value, int):
            try:
                if not isinstance(value, np.integer):
                    raise TypeError(f"Expected {value} to be an int")
            except NameError:
                raise TypeError(f"Expected {value} to be an int")

        if not (self._min <= int(value) <= self._max):
            raise ValueError(
                f"Expected {value} to be in range of {self._min} to {self._max}"
            )

    def validate_many(self, value: Iterable[int]):
        """Validate multiple integer values

        Args:
            value (Iterable[int]): Iterable of integers to validate

        Raises:
            TypeError: Wrong type
            ValueError: Integer out of range for this datatype
        """

        # Check all values
        try:
            if any(
                not (isinstance(v, np.integer) or isinstance(v, int)) for v in value
            ):
                raise TypeError(f"Expected {value} to contain all int types.")
        except NameError:
            if any(not isinstance(v, int) for v in value):
                raise TypeError(f"Expected {value} to contain all int types.")

        if (int(max(value)) > self._max) or (min(value) < self._min):
            raise ValueError(
                f"Expected {value} to be in range of {self._min} to {self._max}."
            )

    def __repr__(self):
        return f"{type(self).__name__}(size={self.size}, unsigned={self.unsigned}) at 0x{id(self):016X}"


class Int8(IntValidatorBase[_P, ctypes.c_int8], Generic[_P]):
    """Validator for 8-bit integers"""

    _size: ClassVar[int] = 1
    _unsigned: ClassVar[bool] = False
    _min: ClassVar[int] = -(2**7)
    _max: ClassVar[int] = 2**7 - 1

    def __init__(self, *args) -> None:
        self._ctype: Type[ctypes._SimpleCData] = ctypes.c_int8

    def validate_one(self, value: Union[int, ctypes.c_int8, np.int8]):
        try:
            if isinstance(value, np.integer) and not isinstance(value, np.int8):  # type: ignore
                raise TypeError(f"Expected {value} to be an int8")
        except NameError:
            pass
        super().validate_one(value)


class Int16(IntValidatorBase[_P, ctypes.c_int16], Generic[_P]):
    """Validator for 16-bit integers"""

    _size: ClassVar[int] = 2
    _unsigned: ClassVar[bool] = False
    _min: ClassVar[int] = -(2**15)
    _max: ClassVar[int] = 2**15 - 1

    def __init__(self, *args) -> None:
        self._ctype: Type[ctypes._SimpleCData] = ctypes.c_int16

    def validate_one(self, value: Union[int, ctypes.c_int16, np.int16]):
        try:
            if isinstance(value, np.integer) and not isinstance(value, np.int16):  # type: ignore
                raise TypeError(f"Expected {value} to be an int16")
        except NameError:
            pass
        super().validate_one(value)


class Int32(IntValidatorBase[_P, ctypes.c_int32], Generic[_P]):
    """Validator for 32-bit integers"""

    _size: ClassVar[int] = 4
    _unsigned: ClassVar[bool] = False
    _min: ClassVar[int] = -(2**31)
    _max: ClassVar[int] = 2**31 - 1

    def __init__(self, *args) -> None:
        self._ctype: Type[ctypes._SimpleCData] = ctypes.c_int32

    def validate_one(self, value: Union[int, ctypes.c_int32, np.int32]):
        try:
            if isinstance(value, np.integer) and not isinstance(value, np.int32):  # type: ignore
                raise TypeError(f"Expected {value} to be an int32")
        except NameError:
            pass
        super().validate_one(value)


class Int64(IntValidatorBase[_P, ctypes.c_int64], Generic[_P]):
    """Validator for 64-bit integers"""

    _size: ClassVar[int] = 8
    _unsigned: ClassVar[bool] = False
    _min: ClassVar[int] = -(2**63)
    _max: ClassVar[int] = 2**63 - 1

    def __init__(self, *args) -> None:
        self._ctype: Type[ctypes._SimpleCData] = ctypes.c_int64

    def validate_one(self, value: Union[int, ctypes.c_int64, np.int64]):
        try:
            if isinstance(value, np.integer) and not isinstance(value, np.int64):  # type: ignore
                raise TypeError(f"Expected {value} to be an int64")
        except NameError:
            pass
        super().validate_one(value)


class Uint8(IntValidatorBase[_P, ctypes.c_uint8], Generic[_P]):
    """Validator for unsigned 8-bit integers"""

    _size: ClassVar[int] = 1
    _unsigned: ClassVar[bool] = True
    _min: ClassVar[int] = 0
    _max: ClassVar[int] = 2**8 - 1

    def __init__(self, *args) -> None:
        self._ctype: Type[ctypes._SimpleCData] = ctypes.c_uint8

    def validate_one(self, value: Union[int, ctypes.c_uint8, np.uint8]):
        try:
            if isinstance(value, np.integer) and not isinstance(value, np.uint8):  # type: ignore
                raise TypeError(f"Expected {value} to be a uint8")
        except NameError:
            pass
        super().validate_one(value)


class Uint16(IntValidatorBase[_P, ctypes.c_uint16], Generic[_P]):
    """Validator for unsigned 16-bit integers"""

    _size: ClassVar[int] = 2
    _unsigned: ClassVar[bool] = True
    _min: ClassVar[int] = 0
    _max: ClassVar[int] = 2**16 - 1

    def __init__(self, *args) -> None:
        self._ctype: Type[ctypes._SimpleCData] = ctypes.c_uint16

    def validate_one(self, value: Union[int, ctypes.c_uint16, np.uint16]):
        try:
            if isinstance(value, np.integer) and not isinstance(value, np.uint16):  # type: ignore
                raise TypeError(f"Expected {value} to be a uint16")
        except NameError:
            pass
        super().validate_one(value)


class Uint32(IntValidatorBase[_P, ctypes.c_uint32], Generic[_P]):
    """Validator for unsigned 32-bit integers"""

    _size: ClassVar[int] = 4
    _unsigned: ClassVar[bool] = True
    _min: ClassVar[int] = 0
    _max: ClassVar[int] = 2**32 - 1

    def __init__(self, *args) -> None:
        self._ctype: Type[ctypes._SimpleCData] = ctypes.c_uint32

    def validate_one(self, value: Union[int, ctypes.c_uint32, np.uint32]):
        try:
            if isinstance(value, np.integer) and not isinstance(value, np.uint32):  # type: ignore
                raise TypeError(f"Expected {value} to be a uint32")
        except NameError:
            pass
        super().validate_one(value)


class Uint64(IntValidatorBase[_P, ctypes.c_uint64], Generic[_P]):
    """Validator for unsigned 64-bit integers"""

    _size: ClassVar[int] = 8
    _unsigned: ClassVar[bool] = True
    _min: ClassVar[int] = 0
    _max: ClassVar[int] = 2**64 - 1

    def __init__(self, *args) -> None:
        self._ctype: Type[ctypes._SimpleCData] = ctypes.c_uint64

    def validate_one(self, value: Union[int, ctypes.c_uint64, np.uint64]):
        try:
            if isinstance(value, np.integer) and not isinstance(value, np.uint64):  # type: ignore
                raise TypeError(f"Expected {value} to be a uint64")
        except NameError:
            pass
        super().validate_one(value)


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

    def __set__(
        self, obj: _P, value: Union[int, bytes, bytearray, ctypes.c_ubyte, np.byte]
    ):
        if _VALIDATION_ENABLED.get():
            self.validate_one(value)
            if isinstance(value, (bytes, bytearray)):
                int_value = int.from_bytes(value, "little")
                setattr(obj, self._private_name, int_value)
                return
        setattr(obj, self._private_name, value)

    def validate_one(
        self, value: Union[int, bytes, bytearray, ctypes.c_ubyte, np.byte]
    ):
        """validate a single byte value

        Args:
            value (Union[int, bytes, bytearray]): Byte value to validate

        Raises:
            ValueError: Value out of range
            TypeError: Wrong type
        """

        if isinstance(value, self._ctype):
            return

        if isinstance(value, int):
            if not self._min <= value <= self._max:
                raise ValueError(
                    f"Expected {value} to be in range of {self._min} to {self._max}"
                )
            return

        try:
            if isinstance(value, np.byte):  # type: ignore
                return
        except NameError:
            pass

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

        # Commented this check to help performance
        try:
            if any(not (isinstance(v, np.byte) or isinstance(v, int)) for v in value):  # type: ignore
                raise TypeError(
                    f"Expected {value} to be an int sequence, bytes, or bytearray."
                )
        except NameError:
            if any(not isinstance(v, int) for v in value):
                raise TypeError(
                    f"Expected {value} to be an int sequence, bytes, or bytearray."
                )

        if (max(value) > self._max) or (min(value) < self._min):
            raise ValueError(
                f"Expected {value} to be in range of {self._min} to {self._max}."
            )

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
        if isinstance(value, self._ctype):
            setattr(obj, self._private_name, value)
            return

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

        if len(value) > (self.len - 1):
            raise ValueError(f'Expected "{value}" to be no longer than {self.len - 1}')

        if not value.isascii():
            raise TypeError(f"Expected {value} to only contain valid ascii points")

    def validate_many(self, value):
        """Validate multiple strings

        Not implemented

        Raises:
            NotImplementedError
        """
        raise NotImplementedError

    def __repr__(self):
        return f"String(len={self.len}) at 0x{id(self):016X}"


class Char(String[_P], Generic[_P]):
    """Validator for scalar char values"""

    def __init__(self) -> None:
        self._ctype = ctypes.c_char
        self.len = 1

    def __set__(self, obj: _P, value: Union[str, ctypes.c_char]):
        if isinstance(value, ctypes.c_char):
            setattr(obj, self._private_name, value)
        else:
            super().__set__(obj, value)

    def validate_one(self, value: Union[str, ctypes.c_char]):
        """Validate a char value

        Args:
            value (str): String value

        Raises:
            TypeError: Wrong type
            ValueError: String exceeds max length
        """

        if isinstance(value, self._ctype):
            return

        if not isinstance(value, str):
            raise TypeError(f"Expected {value} to be a str")

        if len(value) > self.len:
            raise ValueError(f'Expected "{value}" to be no longer than {self.len}')

        if not value.isascii():
            raise TypeError(f"Expected {value} to only contain valid ascii points")

    def __repr__(self):
        return f"Char() at 0x{id(self):016X}"


_FV = TypeVar("_FV", bound=FieldValidator)


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
        self._ctype: Type[ctypes.Array] = self._validator._ctype * len  # type: ignore

    @classmethod
    def _bound(cls, obj: ArrayField[_FV], bound_obj: MessageBase) -> Self:
        new_obj = super().__new__(cls)
        new_obj._bound_obj = bound_obj
        new_obj._validator = obj._validator
        new_obj._len = obj._len
        new_obj._ctype = obj._ctype
        new_obj._owner = obj._owner
        new_obj._public_name = obj._public_name
        new_obj._private_name = obj._private_name

        return new_obj

    def __get__(self, obj: MessageBase, objtype=None) -> Self:
        """Return an Array bound to a message obj instance."""
        return self._bound(self, obj)

    def __set__(
        self, obj: MessageBase, value: Union[ArrayField[_FV], Sequence, npt.NDArray]
    ):
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
            if isinstance(value, abc.Iterable) or hasattr(value, "__getitem__"):
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
        self._ctype = self._validator._ctype * len  # type: ignore

    @classmethod
    def _bound(cls, obj: ArrayField[_IV], bound_obj: MessageBase) -> Self:
        new_obj = super().__new__(cls)
        new_obj._bound_obj = bound_obj
        new_obj._validator = obj._validator
        new_obj._len = obj._len
        new_obj._ctype = obj._ctype
        new_obj._owner = obj._owner
        new_obj._public_name = obj._public_name
        new_obj._private_name = obj._private_name

        return new_obj

    def __get__(self, obj: MessageBase, objtype=None) -> Self:
        """Return an Array bound to a message obj instance."""
        return self._bound(self, obj)

    def __set__(
        self,
        obj: MessageBase,
        value: Union[
            ArrayField[_IV], Sequence[int], ctypes.Array, npt.NDArray[np.integer]
        ],
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


class Int8Array(IntArray[Int8]):
    def __init__(self, len: int):
        """Int8Array validator class

        Args:
            len (int): Field length
        """
        super().__init__(Int8, len)

    def __set__(
        self,
        obj: MessageBase,
        value: Union[
            ArrayField[_IV],
            Sequence[int],
            ctypes.Array[ctypes.c_int8],
            npt.NDArray[np.int8],
        ],
    ):
        return super().__set__(obj, value)


class Int16Array(IntArray[Int16]):
    def __init__(self, len: int):
        """Int16Array validator class

        Args:
            len (int): Field length
        """
        super().__init__(Int16, len)

    def __set__(
        self,
        obj: MessageBase,
        value: Union[
            ArrayField[_IV],
            Sequence[int],
            ctypes.Array[ctypes.c_int16],
            npt.NDArray[np.int16],
        ],
    ):
        return super().__set__(obj, value)


class Int32Array(IntArray[Int32]):
    def __init__(self, len: int):
        """Int32Array validator class

        Args:
            len (int): Field length
        """
        super().__init__(Int32, len)

    def __set__(
        self,
        obj: MessageBase,
        value: Union[
            ArrayField[_IV],
            Sequence[int],
            ctypes.Array[ctypes.c_int32],
            npt.NDArray[np.int32],
        ],
    ):
        return super().__set__(obj, value)


class Int64Array(IntArray[Int64]):
    def __init__(self, len: int):
        """Int64Array validator class

        Args:
            len (int): Field length
        """
        super().__init__(Int64, len)

    def __set__(
        self,
        obj: MessageBase,
        value: Union[
            ArrayField[_IV],
            Sequence[int],
            ctypes.Array[ctypes.c_int64],
            npt.NDArray[np.int64],
        ],
    ):
        return super().__set__(obj, value)


class Uint8Array(IntArray[Uint8]):
    def __init__(self, len: int):
        """Uint8Array validator class

        Args:
            len (int): Field length
        """
        super().__init__(Uint8, len)

    def __set__(
        self,
        obj: MessageBase,
        value: Union[
            ArrayField[_IV],
            Sequence[int],
            ctypes.Array[ctypes.c_uint8],
            npt.NDArray[np.uint8],
        ],
    ):
        return super().__set__(obj, value)


class Uint16Array(IntArray[Uint16]):
    def __init__(self, len: int):
        """Uint16Array validator class

        Args:
            len (int): Field length
        """
        super().__init__(Uint16, len)

    def __set__(
        self,
        obj: MessageBase,
        value: Union[
            ArrayField[_IV],
            Sequence[int],
            ctypes.Array[ctypes.c_uint16],
            npt.NDArray[np.uint16],
        ],
    ):
        return super().__set__(obj, value)


class Uint32Array(IntArray[Uint32]):
    def __init__(self, len: int):
        """Uint32Array validator class

        Args:
            len (int): Field length
        """
        super().__init__(Uint32, len)

    def __set__(
        self,
        obj: MessageBase,
        value: Union[
            ArrayField[_IV],
            Sequence[int],
            ctypes.Array[ctypes.c_uint32],
            npt.NDArray[np.uint32],
        ],
    ):
        return super().__set__(obj, value)


class Uint64Array(IntArray[Uint64]):
    def __init__(self, len: int):
        """Uint64Array validator class

        Args:
            len (int): Field length
        """
        super().__init__(Uint64, len)

    def __set__(
        self,
        obj: MessageBase,
        value: Union[
            ArrayField[_IV],
            Sequence[int],
            ctypes.Array[ctypes.c_uint64],
            npt.NDArray[np.uint64],
        ],
    ):
        return super().__set__(obj, value)


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
    def _bound(cls, obj: ArrayField[Byte], bound_obj: MessageBase) -> Self:
        new_obj = super().__new__(cls)
        new_obj._bound_obj = bound_obj
        new_obj._validator = obj._validator
        new_obj._len = obj._len
        new_obj._ctype = obj._ctype
        new_obj._owner = obj._owner
        new_obj._public_name = obj._public_name
        new_obj._private_name = obj._private_name

        return new_obj

    def __get__(self, obj: MessageBase, objtype=None) -> Self:
        return self._bound(self, obj)

    def __set__(
        self,
        obj: MessageBase,
        value: Union[
            ArrayField[Byte],
            Sequence[int],
            bytes,
            bytearray,
            ctypes.Array,
            npt.NDArray[np.byte],
        ],
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
            if isinstance(value, abc.Iterable) or hasattr(value, "__getitem__"):
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


_FPV = TypeVar("_FPV", bound=FloatValidatorBase)


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
    def _bound(cls, obj: ArrayField[_FPV], bound_obj: MessageBase) -> Self:
        new_obj = super().__new__(cls)
        new_obj._bound_obj = bound_obj
        new_obj._validator = obj._validator
        new_obj._len = obj._len
        new_obj._ctype = obj._ctype
        new_obj._owner = obj._owner
        new_obj._public_name = obj._public_name
        new_obj._private_name = obj._private_name

        return new_obj

    def __get__(self, obj: MessageBase, objtype=None) -> Self:
        """Return an Array bound to a message obj instance."""
        return self._bound(self, obj)

    def __set__(
        self,
        obj: MessageBase,
        value: Union[
            ArrayField[_FPV], Sequence[float], ctypes.Array, npt.NDArray[np.floating]
        ],
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


class Float32Array(FloatArray[Float]):
    def __init__(self, len: int):
        """Float32Array validator class

        Args:
            len (int): Field length
        """
        super().__init__(Float, len)

    def __set__(
        self,
        obj: MessageBase,
        value: Union[
            ArrayField[_FPV],
            Sequence[float],
            ctypes.Array[ctypes.c_float],
            npt.NDArray[np.float32],
        ],
    ):
        return super().__set__(obj, value)


class DoubleArray(FloatArray[Double]):
    def __init__(self, len: int):
        """DoubleArray validator class

        Args:
            len (int): Field length
        """
        super().__init__(Double, len)

    def __set__(
        self,
        obj: MessageBase,
        value: Union[
            ArrayField[_FPV],
            Sequence[float],
            ctypes.Array[ctypes.c_double],
            npt.NDArray[np.float64],
        ],
    ):
        return super().__set__(obj, value)


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
        self._ctype = self._validator._ctype * len  # type: ignore

    @classmethod
    def _bound(cls, obj: StructArray[_S], bound_obj: MessageBase) -> Self:
        new_obj: StructArray[_S] = super().__new__(cls)
        new_obj._bound_obj = bound_obj
        new_obj._validator = obj._validator
        new_obj._len = obj._len
        new_obj._ctype = obj._ctype
        new_obj._owner = obj._owner
        new_obj._public_name = obj._public_name
        new_obj._private_name = obj._private_name

        return new_obj

    def __get__(self, obj: MessageBase, objtype=None) -> Self:
        """Return an StructArray bound to a message obj instance."""
        return self._bound(self, obj)

    def __set__(self, obj, value: Union[StructArray, Sequence[_S], ctypes.Array[_S]]):
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
            if isinstance(value, abc.Iterable) or hasattr(value, "__getitem__"):
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
