import pyrtma
import pyrtma.message
import ctypes
import unittest
from typing import cast

# Import message defs to add to pyrtma.msg_defs map
from .test_msg_defs.test_defs import *


def is_equal(obj: ctypes.Structure, other: ctypes.Structure) -> bool:
    if type(obj) != type(other):
        raise TypeError("Can not compare two different struct types.")

    for name, ftype in obj._fields_:
        if issubclass(ftype, ctypes.Structure):
            if not is_equal(getattr(obj, name), getattr(other, name)):
                return False
        elif issubclass(ftype, ctypes.Array):
            length = cast(int, ftype._length_)
            etype = cast(type, ftype._type_)
            for i in range(length):
                if issubclass(etype, ctypes.Structure):
                    if not is_equal(getattr(obj, name)[i], getattr(other, name)[i]):
                        return False
                elif etype is ctypes.c_char:
                    if getattr(obj, name) != getattr(other, name):
                        return False
                else:
                    if getattr(obj, name)[i] != getattr(other, name)[i]:
                        return False
        else:
            if getattr(obj, name) != getattr(other, name):
                return False

    return True


class TestJSONConversion(unittest.TestCase):
    def test_dict(self):
        for mdf in pyrtma.message.get_msg_defs().values():
            # Fill the message with random data
            in_msg = mdf.from_random()

            # Convert to dict
            in_dict = in_msg.to_dict()

            # Create a message from the json string
            out_msg = mdf.from_dict(in_dict)  # type: ignore

            # Convert the output back to dict
            out_dict = out_msg.to_dict()

            # Check for equality in all respects
            self.assertTrue(is_equal(in_msg, out_msg))
            self.assertEqual(in_msg, out_msg)
            self.assertEqual(in_dict, out_dict)

    def test_json(self):
        for mdf in pyrtma.message.get_msg_defs().values():
            # Fill the message with random data
            in_msg = mdf.from_random()

            # Convert to json string
            in_str = in_msg.to_json()

            # Create a message from the json string
            out_msg = mdf.from_json(in_str)  # type: ignore

            # Convert the output back to json
            out_str = out_msg.to_json()

            # Check for equality in all respects
            self.assertTrue(is_equal(in_msg, out_msg))
            self.assertEqual(in_msg, out_msg)
            self.assertEqual(in_str, out_str)
