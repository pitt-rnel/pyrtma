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
)
from abc import abstractmethod, ABCMeta

from .message_base import MessageBase

__all__ = [
    "Int8",
    "Int16",
    "Int32",
    "Int64",
    "Uint8",
    "Uint16",
    "Uint32",
    "Uint64",
    "Float",
    "Double",
    "String",
    "Bytes",
    "Struct",
    "IntArray",
    "FloatArray",
    "StructArray",
]

_P = TypeVar("_P")  # Parent
_V = TypeVar("_V")  # Value


# Base Class for all type validator descriptors
class FieldValidator(Generic[_P, _V], metaclass=ABCMeta):
    def __set_name__(self, owner: _P, name: str):
        self.owner = owner
        self.public_name = name
        self.private_name = "_" + name

    @abstractmethod
    def __get__(self, obj: _P, objtype=None):
        ...

    @abstractmethod
    def __set__(self, obj: _P, value: _V):
        ...

    @abstractmethod
    def validate_one(self, value: _V):
        ...

    @abstractmethod
    def validate_many(self, value: _V):
        ...


class FloatValidatorBase(FieldValidator[_P, float], Generic[_P], metaclass=ABCMeta):
    _float_type = ctypes.c_float

    @abstractmethod
    def __init__(self):
        ...

    def __get__(self, obj: _P, objtype=None) -> float:
        return getattr(obj, self.private_name)

    def __set__(self, obj: _P, value: float):
        self.validate_one(value)
        setattr(obj, self.private_name, value)

    def validate_one(self, value: float):
        if not isinstance(value, (float, int)):
            raise TypeError(f"Expected {value} to be an float")

        if not math.isclose(self._float_type(value).value, value, rel_tol=1e-6):
            raise ValueError(
                f"The {value} can not be represented as a {type(self).__name__}"
            )

    def validate_many(self, value: Iterable[float]):
        if any(not isinstance(v, (float, int)) for v in value):
            raise TypeError(f"Expected {value!r} to be an int.")

        if any(
            not math.isclose(self._float_type(v).value, v, rel_tol=1e-6) for v in value
        ):
            raise ValueError(
                f"{value} contains value(s) that can not be represented as a {type(self).__name__}"
            )

    def __repr__(self):
        return f"{type(self).__name__} at 0x{id(self):016X}"


class Float(FloatValidatorBase):
    _float_type = ctypes.c_float

    def __init__(self):
        ...


class Double(FloatValidatorBase):
    _float_type = ctypes.c_double

    def __init__(self):
        ...


# Base Class for int validator fields
class IntValidatorBase(FieldValidator[_P, int], Generic[_P], metaclass=ABCMeta):
    _size: ClassVar[int] = 1
    _unsigned: ClassVar[bool] = False
    _min: ClassVar[int] = 0
    _max: ClassVar[int] = 2**8 - 1

    @abstractmethod
    def __init__(self):
        ...

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
        return getattr(obj, self.private_name)

    def __set__(self, obj: _P, value: int):
        self.validate_one(value)
        setattr(obj, self.private_name, value)

    def validate_one(self, value: int):
        if not isinstance(value, int):
            raise TypeError(f"Expected {value} to be an int")

        if value < self._min:
            raise ValueError(f"Expected {value} to be at least {self._min}")
        if value > self._max:
            raise ValueError(f"Expected {value} to be no more than {self._max}")

    def validate_many(self, value: Iterable[int]):
        if any(not isinstance(v, int) for v in value):
            raise TypeError(f"Expected {value} to be an int.")

        if any((v < self._min for v in value)):
            raise ValueError(f"Expected {value} to be {self._min} or greater.")

        if any((v > self._max for v in value)):
            raise ValueError(f"Expected {value} to be no more than {self._max}")

    def __repr__(self):
        return f"{type(self).__name__}(size={self.size}, unsigned={self.unsigned}) at 0x{id(self):016X}"


class Int8(IntValidatorBase):
    _size: ClassVar[int] = 1
    _unsigned: ClassVar[bool] = False
    _min: ClassVar[int] = -(2**7)
    _max: ClassVar[int] = 2**7 - 1

    def __init__(self):
        ...


class Int16(IntValidatorBase):
    _size: ClassVar[int] = 2
    _unsigned: ClassVar[bool] = False
    _min: ClassVar[int] = -(2**15)
    _max: ClassVar[int] = 2**15 - 1

    def __init__(self):
        ...


class Int32(IntValidatorBase):
    _size: ClassVar[int] = 4
    _unsigned: ClassVar[bool] = False
    _min: ClassVar[int] = -(2**31)
    _max: ClassVar[int] = 2**31 - 1

    def __init__(self):
        ...


class Int64(IntValidatorBase):
    _size: ClassVar[int] = 8
    _unsigned: ClassVar[bool] = False
    _min: ClassVar[int] = -(2**63)
    _max: ClassVar[int] = 2**63 - 1

    def __init__(self):
        ...


class Uint8(IntValidatorBase):
    _size: ClassVar[int] = 1
    _unsigned: ClassVar[bool] = True
    _min: ClassVar[int] = 0
    _max: ClassVar[int] = 2**8 - 1

    def __init__(self):
        ...


class Uint16(IntValidatorBase):
    _size: ClassVar[int] = 2
    _unsigned: ClassVar[bool] = True
    _min: ClassVar[int] = 0
    _max: ClassVar[int] = 2**16 - 1

    def __init__(self):
        ...


class Uint32(IntValidatorBase):
    _size: ClassVar[int] = 4
    _unsigned: ClassVar[bool] = True
    _min: ClassVar[int] = 0
    _max: ClassVar[int] = 2**32 - 1

    def __init__(self):
        ...


class Uint64(IntValidatorBase):
    _size: ClassVar[int] = 8
    _unsigned: ClassVar[bool] = True
    _min: ClassVar[int] = 0
    _max: ClassVar[int] = 2**64 - 1

    def __init__(self):
        ...


class String(FieldValidator[_P, str], Generic[_P]):
    def __init__(self, len: int = 1):
        self.len = len

    def __get__(self, obj: _P, objtype=None) -> str:
        return getattr(obj, self.private_name).decode()

    def __set__(self, obj: _P, value: str):
        self.validate_one(value)
        setattr(obj, self.private_name, value.encode())

    def validate_one(self, value: str):
        if not isinstance(value, str):
            raise TypeError(f"Expected {value} to be an str")

        if len(value) > self.len:
            raise ValueError(f'Expected "{value}" to be no longer than {self.len}')

    def validate_many(self, value):
        raise NotImplementedError

    def __repr__(self):
        return f"String(len={self.len}) at 0x{id(self):016X}"


_B = TypeVar("_B", bytes, bytearray)


class Bytes(FieldValidator[_P, _B], Generic[_P, _B]):
    _min: ClassVar[int] = 0
    _max: ClassVar[int] = 2**8 - 1

    def __init__(self, len: int = 1):
        self.len = len

    def __get__(self, obj: _P, objtype=None) -> _B:
        return getattr(obj, self.private_name)

    def __set__(self, obj: _P, value: _B):
        self.validate_one(value)
        if self.len == 1 and isinstance(value, bytes):
            int_value = int.from_bytes(value, "little")
            setattr(obj, self.private_name, int_value)
            return
        setattr(obj, self.private_name, value)

    def validate_one(self, value: Union[int, bytes]):
        if isinstance(value, int):
            if value < self._min:
                raise ValueError(f"Expected {value} to be at least {self._min}")
            if value > self._max:
                raise ValueError(f"Expected {value} to be no more than {self._max}")
            return

        if not isinstance(value, (bytes, bytearray)):
            raise TypeError(f"Expected {value} to be bytes")

        if len(value) > self.len:
            raise ValueError(f"Expected {value} to be no bigger than {self.len}")

    def validate_many(self, value):
        raise NotImplementedError

    def __repr__(self):
        return f"Bytes(len={self.len}) at 0x{id(self):016X}"


_FV = TypeVar("_FV", bound=FieldValidator)


class ArrayField(FieldValidator, Generic[_FV]):
    def __init__(self, validator: Type[_FV], len: int):
        self._validator = validator()
        self._len = len
        self._bound_obj: Optional[MessageBase] = None

    @classmethod
    def _bound(cls, obj: ArrayField[_FV], bound_obj: MessageBase) -> ArrayField[_FV]:
        new_obj = super().__new__(cls)
        new_obj._bound_obj = bound_obj
        new_obj._validator = obj._validator
        new_obj._len = obj._len
        new_obj.owner = obj.owner
        new_obj.public_name = obj.public_name
        new_obj.private_name = obj.private_name

        return new_obj

    def __get__(self, obj: MessageBase, objtype=None) -> ArrayField[_FV]:
        """Return an Array bound to a message obj instance."""
        return ArrayField._bound(self, obj)

    def __set__(self, obj: MessageBase, value: ArrayField[_FV]):
        self.validate_array(value)
        setattr(obj, self.private_name, getattr(value._bound_obj, value.private_name))

    def __getitem__(self, key):
        if self._bound_obj is None:
            raise AttributeError("Array descriptor is not bound to an instance object.")

        return getattr(self._bound_obj, self.private_name)[key]

    def __setitem__(self, key, value):
        if self._bound_obj is None:
            raise AttributeError("Array descriptor is not bound to an instance object.")

        if isinstance(value, abc.Iterable):
            self.validate_many(value)
        else:
            self.validate_one(value)

        getattr(self._bound_obj, self.private_name)[key] = value

    def __len__(self) -> int:
        return self._len

    def __repr__(self) -> str:
        return f"ArrayField({type(self._validator).__name__}, len={self._len}) at 0x{id(self):016X}"

    def validate_one(self, value):
        self._validator.validate_one(value)

    def validate_many(self, value):
        self._validator.validate_many(value)

    def validate_array(self, value):
        if not isinstance(value._validator, type(self._validator)):
            raise TypeError(f"Expected an ArrayField({type(self._validator).__name__}")
        return


_IV = TypeVar("_IV", bound=IntValidatorBase)


class IntArray(ArrayField[_IV]):
    def __init__(self, validator: Type[_IV], len: int):
        self._validator = validator()
        self._len = len
        self._bound_obj: Optional[MessageBase] = None

    @classmethod
    def _bound(cls, obj: IntArray[_IV], bound_obj: MessageBase) -> IntArray[_IV]:
        new_obj = super().__new__(cls)
        new_obj._bound_obj = bound_obj
        new_obj._validator = obj._validator
        new_obj._len = obj._len
        new_obj.owner = obj.owner
        new_obj.public_name = obj.public_name
        new_obj.private_name = obj.private_name

        return new_obj

    def __get__(self, obj: MessageBase, objtype=None) -> IntArray[_IV]:
        """Return an Array bound to a message obj instance."""
        return IntArray._bound(self, obj)

    def __set__(self, obj: MessageBase, value: IntArray[_IV]):
        self.validate_array(value)
        setattr(obj, self.private_name, getattr(value._bound_obj, value.private_name))

    @overload
    def __getitem__(self, key: int) -> int:
        ...

    @overload
    def __getitem__(self, key: slice) -> List[int]:
        ...

    def __getitem__(self, key) -> Union[int, List[int]]:
        if self._bound_obj is None:
            raise AttributeError("Array descriptor is not bound to an instance object.")

        return getattr(self._bound_obj, self.private_name)[key]


_FPV = TypeVar("_FPV", bound=FloatValidatorBase)


class FloatArray(ArrayField[_FPV]):
    def __init__(self, validator: Type[_FPV], len: int):
        self._validator = validator()
        self._len = len
        self._bound_obj: Optional[MessageBase] = None

    @classmethod
    def _bound(cls, obj: FloatArray[_FPV], bound_obj: MessageBase) -> FloatArray[_FPV]:
        new_obj = super().__new__(cls)
        new_obj._bound_obj = bound_obj
        new_obj._validator = obj._validator
        new_obj._len = obj._len
        new_obj.owner = obj.owner
        new_obj.public_name = obj.public_name
        new_obj.private_name = obj.private_name

        return new_obj

    def __get__(self, obj: MessageBase, objtype=None) -> FloatArray[_FPV]:
        """Return an Array bound to a message obj instance."""
        return FloatArray._bound(self, obj)

    def __set__(self, obj: MessageBase, value: FloatArray[_FPV]):
        self.validate_array(value)
        setattr(obj, self.private_name, getattr(value._bound_obj, value.private_name))

    @overload
    def __getitem__(self, key: int) -> float:
        ...

    @overload
    def __getitem__(self, key: slice) -> List[float]:
        ...

    def __getitem__(self, key) -> Union[float, List[float]]:
        if self._bound_obj is None:
            raise AttributeError("Array descriptor is not bound to an instance object.")

        return getattr(self._bound_obj, self.private_name)[key]


_S = TypeVar("_S", bound=MessageBase)


class Struct(FieldValidator, Generic[_S]):
    def __init__(self, stype: Type[_S]):
        self.stype = stype

    def __get__(self, obj, objtype=None) -> _S:
        return getattr(obj, self.private_name)

    @overload
    def __set__(self, obj: MessageBase, value: _S):
        ...

    @overload
    def __set__(self, obj: StructArray, value: Struct[_S]):
        ...

    def __set__(self, obj, value):
        self.validate_one(value)
        # Note: ctypes already copies the data here
        setattr(obj, self.private_name, value)

    def validate_one(self, value: _S):
        if not isinstance(value, self.stype):
            raise TypeError(f"Expected {self.stype.__name__}")

    def validate_many(self, value: Iterable[_S]):
        if any(not isinstance(v, self.stype) for v in value):
            raise TypeError(f"Expected {value} to be an {self.stype.__name__}.")

    def __repr__(self) -> str:
        return f"Struct({self.stype.__name__}) at 0x{id(self):016X}"


class StructArray(FieldValidator, Generic[_S]):
    def __init__(self, msg_struct: Type[_S], len: int):
        self._validator = Struct(msg_struct)
        self._len = len
        self._bound_obj: Optional[MessageBase] = None

    @classmethod
    def _bound(cls, obj: StructArray[_S], bound_obj: MessageBase) -> StructArray[_S]:
        new_obj: StructArray[_S] = super().__new__(cls)
        new_obj._bound_obj = bound_obj
        new_obj._validator = obj._validator
        new_obj._len = obj._len
        new_obj.owner = obj.owner
        new_obj.public_name = obj.public_name
        new_obj.private_name = obj.private_name

        return new_obj

    def __get__(self, obj: MessageBase, objtype=None) -> StructArray[_S]:
        """Return an StructArray bound to a message obj instance."""
        return StructArray._bound(self, obj)

    def __set__(self, obj, value):
        self.validate_array(value)
        setattr(obj, self.private_name, getattr(value._bound_obj, value.private_name))

    def __getitem__(self, key) -> Union[_S, List[_S]]:
        if self._bound_obj is None:
            raise AttributeError("Array descriptor is not bound to an instance object.")
        return getattr(self._bound_obj, self.private_name)[key]

    def __setitem__(self, key, value):
        if self._bound_obj is None:
            raise AttributeError(
                "StructArray descriptor is not bound to an instance object."
            )

        if isinstance(value, abc.Iterable):
            self.validate_many(value)
        else:
            self.validate_one(value)

        getattr(self._bound_obj, self.private_name)[key] = value

    def __len__(self) -> int:
        return self._len

    def __repr__(self) -> str:
        return f"StructArray({self._validator.stype.__name__}, len={self._len}) at 0x{id(self):016X}"

    def validate_one(self, value: _S):
        self._validator.validate_one(value)

    def validate_many(self, value: Iterable[_S]):
        self._validator.validate_many(value)

    def validate_array(self, value: StructArray[_S]):
        if not isinstance(value._validator.stype, type(self._validator.stype)):
            raise TypeError(f"Expected a StructArray({self._validator.stype.__name__}")
        return
