from __future__ import annotations

import ctypes

from typing import List, ClassVar, Type, Generic, TypeVar, Union, Sequence, Iterable, Optional, overload
from abc import abstractmethod, ABCMeta
import collections.abc as abc


class MessageBase(ctypes.Structure):
    type_id: ClassVar[int] = 0
    type_name: ClassVar[str] = ""
    type_hash: ClassVar[int] = 0x0
    type_source: ClassVar[str] = ""

    @classmethod
    def copy(cls, s: ctypes.Structure):
        return cls.from_buffer_copy(s)


_P = TypeVar("_P") # Parent
_V = TypeVar("_V") # Value


# Base Class for all type validator descriptors
class FieldValidator(Generic[_P, _V], metaclass=ABCMeta):

    def __set_name__(self, owner: _P, name: str):
        self.owner = owner
        self.public_name = name
        self.private_name = "_" + name

    @abstractmethod
    def __get__(self, obj: _P, objtype=None):
        pass

    @abstractmethod
    def __set__(self, obj: _P, value: _V):
        pass

    @abstractmethod
    def validate_one(self, value: _V):
        pass
    
    @abstractmethod
    def validate_many(self, value: _V): 
        pass


# Base Class for int validator fields
class IntValidatorBase(FieldValidator, Generic[_P], metaclass=ABCMeta):
    _size: ClassVar[int] = 1
    _unsigned: ClassVar[bool] = False
    _min: ClassVar[int] = 0
    _max: ClassVar[int] = 2**8 - 1

    def __init__(self):
        pass

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
            raise TypeError(f"Expected {value!r} to be an int")

        if value < self._min:
            raise ValueError(f"Expected {value} to be at least {self._min}")
        if value > self._max:
            raise ValueError(f"Expected {value} to be no more than {self._max}")

    def validate_many(self, value: Iterable[int]):
        if any(not isinstance(v, int) for v in value):
            raise TypeError(f"Expected {value!r} to be an int.")

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


class Int16(IntValidatorBase):
    _size: ClassVar[int] = 2
    _unsigned: ClassVar[bool] = False
    _min: ClassVar[int] = -(2**15)
    _max: ClassVar[int] = 2**15 - 1


class Int32(IntValidatorBase):
    _size: ClassVar[int] = 4
    _unsigned: ClassVar[bool] = False
    _min: ClassVar[int] = -(2**31)
    _max: ClassVar[int] = 2**31 - 1


class Int64(IntValidatorBase):
    _size: ClassVar[int] = 8
    _unsigned: ClassVar[bool] = False
    _min: ClassVar[int] = -(2**63)
    _max: ClassVar[int] = 2**63 - 1

class Uint8(IntValidatorBase):
    _size: ClassVar[int] = 1
    _unsigned: ClassVar[bool] = True
    _min: ClassVar[int] = 0
    _max: ClassVar[int] = 2**8 - 1


class Uint16(IntValidatorBase):
    _size: ClassVar[int] = 2
    _unsigned: ClassVar[bool] = True
    _min: ClassVar[int] = 0
    _max: ClassVar[int] = 2**16 - 1


class Uint32(IntValidatorBase):
    _size: ClassVar[int] = 4
    _unsigned: ClassVar[bool] = True
    _min: ClassVar[int] = 0
    _max: ClassVar[int] = 2**32 - 1


class Uint64(IntValidatorBase):
    _size: ClassVar[int] = 8
    _unsigned: ClassVar[bool] = True
    _min: ClassVar[int] = 0
    _max: ClassVar[int] = 2**64 - 1


class String(FieldValidator, Generic[_P]):
    def __init__(self, len: int):
        self.len = len

    def __get__(self, obj: _P, objtype=None) -> str:
        return getattr(obj, self.private_name).decode()

    def __set__(self, obj: _P, value: str):
        self.validate_one(value)
        setattr(obj, self.private_name, value.encode())

    def validate_one(self, value: str):
        if not isinstance(value, str):
            raise TypeError(f"Expected {value!r} to be an str")

        if len(value) > self.len:
            raise ValueError(f"Expected \"{value}\" to be no longer than {self.len}")

    def validate_many(self, value):
        raise NotImplementedError

    def __repr__(self):
        return f"String(len={self.len}) at 0x{id(self):016X}"


_B = TypeVar("_B", bytes, bytearray)
class Bytes(FieldValidator, Generic[_P, _B]):
    def __init__(self, len: int):
        self.len = len

    def __get__(self, obj: _P, objtype=None) -> _B:
        return getattr(obj, self.private_name)

    def __set__(self, obj: _P, value: _B):
        self.validate_one(value)
        setattr(obj, self.private_name, value)

    def validate_one(self, value: bytes):
        if not isinstance(value, (bytes, bytearray)):
            raise TypeError(f"Expected {value!r} to be bytes")

        if len(value) > self.len:
            raise ValueError(f"Expected {value!r} to be no bigger than {self.len}")

    def validate_many(self, value):
        raise NotImplementedError

    def __repr__(self):
        return f"Bytes(len={self.len}) at 0x{id(self):016X}"


_FV = TypeVar("_FV", bound=FieldValidator)


class ArrayField(FieldValidator, Generic[_FV]):
    def __init__(self, validator: Type[_FV], len: int):
        self._validator = validator()
        self._len = len
        self._bound_obj:Optional[MessageBase] = None

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

    def __set__(self, obj: MessageBase, value:ArrayField[_FV]):
        self.validate_array(value)
        setattr(obj, self.private_name, getattr(value._bound_obj, value.private_name))

    def __getitem__(self, key) -> Union[_FV, List[_FV]]:
        if self._bound_obj is None:
            raise AttributeError(
                "Array descriptor is not bound to an instance object."
            )

        return getattr(self._bound_obj, self.private_name)[key]

    def __setitem__(self, key, value):
        if self._bound_obj is None:
            raise AttributeError(
                "Array descriptor is not bound to an instance object."
            )

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
            raise TypeError(
                f"Expected an ArrayField({type(self._validator).__name__}"
            )
        return


_S = TypeVar("_S", bound=MessageBase)


class StructField(FieldValidator, Generic[_S]):
    def __init__(self, stype: Type[_S]):
        self.stype = stype

    def __get__(self, obj, objtype=None) -> _S:
        return getattr(obj, self.private_name)

    @overload
    def __set__ (self, obj: MessageBase, value: _S): ...

    @overload
    def __set__(self, obj: StructArrayField, value: StructField[_S]): ...

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


class StructArrayField(FieldValidator, Generic[_S]):
    def __init__(self, msg_struct: Type[_S], len: int):
        self._validator = StructField(msg_struct)
        self._len = len
        self._bound_obj: Optional[MessageBase] = None

    @classmethod
    def _bound(cls, obj: StructArrayField[_S], bound_obj: MessageBase) -> StructArrayField[_S]:
        new_obj: StructArrayField[_S] = super().__new__(cls)
        new_obj._bound_obj = bound_obj
        new_obj._validator = obj._validator
        new_obj._len = obj._len
        new_obj.owner = obj.owner
        new_obj.public_name = obj.public_name
        new_obj.private_name = obj.private_name

        return new_obj

    def __get__(self, obj: MessageBase, objtype=None) -> StructArrayField[_S]:
        """Return an StructArray bound to a message obj instance."""
        return StructArrayField._bound(self, obj)

    def __set__(self, obj, value):
        self.validate_array(value)
        setattr(obj, self.private_name, getattr(value._bound_obj, value.private_name))

    def __getitem__(self, key) -> Union[_S, List[_S]]:
        if self._bound_obj is None:
            raise AttributeError(
                "Array descriptor is not bound to an instance object."
            )
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

    def validate_array(self, value:StructArrayField[_S]):
        if not isinstance(value._validator.stype, type(self._validator.stype)):
            raise TypeError(
                f"Expected a StructArrayField({self._validator.stype.__name__}"
            )
        return


# User defined struct
class USER_STRUCT(MessageBase):
    # Internal Underlying memory layout (Generated)
    _fields_ = [
        ("_char", ctypes.c_char),
        ("_int8", ctypes.c_int8),
        ("_char_arr", ctypes.c_char * 32),
        ("_int8_arr", ctypes.c_int8 * 8),
    ]

    # Attribute Validator Descriptors
    char: String = String(1)
    int8: Int8 = Int8()
    char_arr: String = String(32)
    int8_arr: ArrayField[Int8] = ArrayField(Int8, len=8)


# User defined message class
class MDF_ARRAY_TEST(MessageBase):
    # Internal underlying memory layout (Generated)
    _fields_ = [
        ("_char", ctypes.c_char),
        ("_int8", ctypes.c_int8),
        ("_char_arr", ctypes.c_char * 32),
        ("_int8_arr", ctypes.c_int8 * 8),
        ("_user_struct", USER_STRUCT),
        ("_user_struct1", USER_STRUCT),
        ("_user_struct_arr", USER_STRUCT * 3),
    ]

    # Class Vars
    type_id: ClassVar[int] = 9999
    type_name: ClassVar[str] = "ARRAY_TEST"
    type_hash: ClassVar[int] = 0x0
    type_source: ClassVar[str] = ""

    # Attribute Validator Descriptors
    char: String = String(1)
    int8: Int8 = Int8()
    char_arr: String = String(32)
    int8_arr: ArrayField[Int8] = ArrayField(Int8, len=8)
    user_struct: StructField[USER_STRUCT] = StructField(USER_STRUCT)
    user_struct1: StructField[USER_STRUCT] = StructField(USER_STRUCT)
    user_struct_arr: StructArrayField[USER_STRUCT] = StructArrayField(USER_STRUCT, len=3)

msg = MDF_ARRAY_TEST()
msg.char
msg.char_arr
msg.int8
msg.int8_arr
msg.user_struct
msg.user_struct1
msg.user_struct_arr # Don't know why this breaks the type checking / linting
