import ctypes
import random
import string
from typing import List


def _random_str(length: int) -> str:
    return "".join(random.choice(string.printable) for _ in range(length))


def _random_int_array(length: int, min: int = 0, max: int = 9) -> List[int]:
    return [random.randint(min, max) for _ in range(length)]


def _random_float_array(length: int) -> List[float]:
    return [random.random() for _ in range(length)]


def _random_byte_array(length: int) -> bytes:
    return bytes([random.randint(0, 255) for _ in range(length)])


def _random_struct(obj: ctypes.Structure):
    for name, ftype in obj._fields_:
        if issubclass(ftype, ctypes.Structure):
            setattr(obj, name, _random_struct(getattr(obj, name)))
        elif issubclass(ftype, ctypes.Array):
            length: int = ftype._length_  # type: ignore
            etype: type = ftype._type_  # type: ignore
            if issubclass(etype, ctypes.Structure):
                for i in range(length):
                    getattr(obj, name)[i] = _random_struct(getattr(obj, name)[i])
            elif etype is ctypes.c_char:
                setattr(obj, name, _random_str(length))
            elif etype is ctypes.c_ubyte:
                getattr(obj, name)[:] = _random_byte_array(length)
            elif etype is ctypes.c_int8:
                getattr(obj, name)[:] = _random_int_array(
                    length, min=-(2**7), max=2**7 - 1
                )
            elif etype is ctypes.c_uint8:
                getattr(obj, name)[:] = _random_int_array(length, min=0, max=2**8 - 1)
            elif etype in (ctypes.c_short, ctypes.c_int16):
                getattr(obj, name)[:] = _random_int_array(
                    length, min=-(2**15), max=2**15 - 1
                )
            elif etype in (ctypes.c_ushort, ctypes.c_uint16):
                getattr(obj, name)[:] = _random_int_array(
                    length, min=0, max=2**16 - 1
                )
            elif etype in (ctypes.c_int, ctypes.c_long, ctypes.c_int32):
                getattr(obj, name)[:] = _random_int_array(
                    length, min=-(2**31), max=2**31 - 1
                )
            elif etype in (ctypes.c_uint, ctypes.c_ulong, ctypes.c_uint32):
                getattr(obj, name)[:] = _random_int_array(
                    length, min=0, max=2**32 - 1
                )
            elif etype in (ctypes.c_longlong, ctypes.c_int64):
                getattr(obj, name)[:] = _random_int_array(
                    length, min=-(2**63), max=2**63 - 1
                )
            elif etype in (ctypes.c_ulonglong, ctypes.c_uint64):
                getattr(obj, name)[:] = _random_int_array(
                    length, min=0, max=2**64 - 1
                )
            elif etype is ctypes.c_float:
                getattr(obj, name)[:] = _random_float_array(length)
            elif etype is ctypes.c_double:
                getattr(obj, name)[:] = _random_float_array(length)
        elif ftype is ctypes.c_char:
            setattr(obj, name, _random_str(1))
        elif ftype is ctypes.c_ubyte:
            setattr(obj, name, random.randint(0, 255))
        elif ftype is ctypes.c_int8:
            setattr(obj, name, random.randint(-(2**7), 2**7 - 1))
        elif ftype is ctypes.c_uint8:
            setattr(obj, name, random.randint(0, 2**8 - 1))
        elif ftype in (ctypes.c_short, ctypes.c_int16):
            setattr(obj, name, random.randint(-(2**15), 2**15 - 1))
        elif ftype in (ctypes.c_ushort, ctypes.c_uint16):
            setattr(obj, name, random.randint(0, 2**16 - 1))
        elif ftype in (ctypes.c_int, ctypes.c_long, ctypes.c_int32):
            setattr(obj, name, random.randint(-(2**31), 2**31 - 1))
        elif ftype in (ctypes.c_uint, ctypes.c_ulong, ctypes.c_uint32):
            setattr(obj, name, random.randint(0, 2**32 - 1))
        elif ftype in (ctypes.c_longlong, ctypes.c_int64):
            setattr(obj, name, random.randint(-(2**63), 2**63 - 1))
        elif ftype in (ctypes.c_ulonglong, ctypes.c_uint64):
            setattr(obj, name, random.randint(0, 2**64 - 1))
        elif ftype is ctypes.c_float:
            setattr(obj, name, random.random())
        elif ftype is ctypes.c_double:
            setattr(obj, name, random.random())

    return obj
