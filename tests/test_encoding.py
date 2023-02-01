import ctypes
import json
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


class TestJSONEncoding(unittest.TestCase):
    """
    Test JSON encoding/decoding functionality.
    """

    def test_whenSingleMessage_encodesToJSON(self):
        """
        Test if a single message can be encoded to json.
        """
        # Arrange
        msg = TEST_MESSAGE()
        msg.str_value = "test"
        msg.int_value = 2
        msg.float_value = 4.3
        msg.double_value = 5.4
        msg.intarr_value = (ctypes.c_int * 4)(6, 9, 3, 2)
        msg.longarr_value = (ctypes.c_long * 2)(4, 7)

        # Act
        result = msg.to_json()

        # Assert
        result_map = json.loads(result)
        self.assertEqual(result_map["str_value"], "test")
        self.assertEqual(result_map["int_value"], 2)
        self.assertAlmostEqual(result_map["float_value"], 4.3, 5)
        self.assertEqual(result_map["double_value"], 5.4)
        self.assertEqual(result_map["intarr_value"], [6, 9, 3, 2])
        self.assertEqual(result_map["longarr_value"], [4, 7])

    def test_whenNestedMessage_encodesToJSON(self):
        """
        Test if a nested message can be encoded to json.
        """
        # Arrange
        nested = TEST_MESSAGE()
        nested.str_value = "test"
        nested.int_value = 55

        msg = NESTED_MESSAGE()
        msg.idx = 1200
        msg.nested = nested

        print(msg.nested.str_value)
        print(msg.nested.int_value)

        # Act
        result = msg.to_json()

        # Assert
        result_map = json.loads(result)
        self.assertEqual(result_map["idx"], 1200)
        nested_map = result_map["nested"]
        self.assertEqual(nested_map["str_value"], "test")
        self.assertEqual(nested_map["int_value"], 55)
        self.assertEqual(nested_map["float_value"], 0.0)
        self.assertEqual(nested_map["double_value"], 0.0)
        self.assertEqual(nested_map["intarr_value"], [0, 0, 0, 0])
        self.assertEqual(nested_map["longarr_value"], [0, 0])
