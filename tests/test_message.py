import ctypes
import unittest

from pyrtma import MessageData, msg_def

# Choose a unique message type id number
MT_TEST_MESSAGE = 1234
MT_NESTED_MESSAGE = 5678


@msg_def
class TEST_MESSAGE(MessageData):
    _pack_ = True
    _fields_ = [
        ("str_value", ctypes.c_char * 64),
        ("int_value", ctypes.c_int),
        ("float_value", ctypes.c_float),
        ("double_value", ctypes.c_double),
        ("intarr_value", ctypes.c_int * 4),
        ("longarr_value", ctypes.c_long * 2),
    ]

    type_id: int = MT_TEST_MESSAGE
    type_name: str = "TEST_MESSAGE"


@msg_def
class NESTED_MESSAGE(MessageData):
    _pack_ = True
    _fields_ = [("idx", ctypes.c_int), ("nested", TEST_MESSAGE)]

    type_id: int = MT_NESTED_MESSAGE
    type_name: str = "NESTED_MESSAGE"


class TestMessageData(unittest.TestCase):
    """
    Test MessageData functionality.
    """

    def test_whenSingleMessage_setCorrectValues(self):
        """
        Test if a single message sets correct values.
        """
        # Act
        msg = TEST_MESSAGE()
        msg.str_value = "test"
        msg.int_value = 2
        msg.float_value = 4.3
        msg.double_value = 5.4
        msg.intarr_value = (ctypes.c_int * 4)(6, 9, 3, 2)
        msg.longarr_value = (ctypes.c_long * 2)(4, 7)

        # Assert
        self.assertEqual(msg.str_value, "test")
        self.assertEqual(msg.int_value, 2)
        self.assertAlmostEqual(msg.float_value, 4.3, 5)
        self.assertEqual(msg.double_value, 5.4)
        self.assertEqual(list(msg.intarr_value), [6, 9, 3, 2])
        self.assertEqual(list(msg.longarr_value), [4, 7])

    def test_whenNestedMessage_setsCorrectValues(self):
        """
        Test if nested messages sets correct values.
        """
        # Act
        nested = TEST_MESSAGE()
        nested.str_value = "test"
        nested.int_value = 55

        msg = NESTED_MESSAGE()
        msg.idx = 1200
        msg.nested = nested

        # Assert
        self.assertEqual(msg.idx, 1200)
        self.assertEqual(msg.nested.str_value, "test")
        self.assertEqual(msg.nested.int_value, 55)
        self.assertEqual(msg.nested.float_value, 0.0)
        self.assertEqual(msg.nested.double_value, 0.0)
        self.assertEqual(list(msg.nested.intarr_value), [0, 0, 0, 0])
        self.assertEqual(list(msg.nested.longarr_value), [0, 0])
