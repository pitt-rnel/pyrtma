import unittest

# Import message defs to add to pyrtma.msg_defs map
from .test_msg_defs.test_defs import *


class TestEncoding(unittest.TestCase):
    """Test sending messages through MessageManager."""

    def test_validator_range(self):
        m = MDF_VALIDATOR_A()

        m.int8 = -128
        m.int8 = 127

        m.uint8 = 0
        m.uint8 = 255

        m.int16 = -32768
        m.int16 = 32767

        m.uint16 = 0
        m.uint16 = 65535

        m.int32 = -2_147_483_648
        m.int32 = 2_147_483_647

        m.uint32 = 0
        m.uint32 = 4_294_967_295

        m.int64 = -9_223_372_036_854_775_808
        m.int64 = 9_223_372_036_854_775_807

        m.uint64 = 0
        m.uint64 = 18_446_744_073_709_551_615

        m.float = 3.40282346638528859811704183484516925440e38
        m.float = -3.40282346638528859811704183484516925440e38

        m.double = 1.79769313486231570814527423731704356798070e308
        m.double = -1.79769313486231570814527423731704356798070e308

        m.byte = b"\x00"
        m.byte = b"\xFF"

        m.char = chr(0)
        m.char = chr(127)

        m.int8_arr[0] = -128
        m.int8_arr[0] = 127

        m.uint8_arr[0] = 0
        m.uint8_arr[0] = 255

        m.int16_arr[0] = -32768
        m.int16_arr[0] = 32767

        m.uint16_arr[0] = 0
        m.uint16_arr[0] = 65535

        m.int32_arr[0] = -2_147_483_648
        m.int32_arr[0] = 2_147_483_647

        m.uint32_arr[0] = 0
        m.uint32_arr[0] = 4_294_967_295

        m.int64_arr[0] = -9_223_372_036_854_775_808
        m.int64_arr[0] = 9_223_372_036_854_775_807

        m.uint64_arr[0] = 0
        m.uint64_arr[0] = 18_446_744_073_709_551_615

        m.float_arr[0] = -3.40282346638528859811704183484516925440e38
        m.float_arr[0] = 3.40282346638528859811704183484516925440e38

        m.double_arr[0] = -1.79769313486231570814527423731704356798070e308
        m.double_arr[0] = 1.79769313486231570814527423731704356798070e308

        m.byte_arr[0] = b"\x00"
        m.byte_arr[0] = b"\xFF"

    def test_validator_out_of_range(self):
        m = MDF_VALIDATOR_A()
        with self.assertRaises(ValueError):
            m.int8 = -129

        with self.assertRaises(ValueError):
            m.int8 = 128

        with self.assertRaises(ValueError):
            m.uint8 = -1

        with self.assertRaises(ValueError):
            m.uint8 = 256

        with self.assertRaises(ValueError):
            m.int16 = -32769

        with self.assertRaises(ValueError):
            m.int16 = 32768

        with self.assertRaises(ValueError):
            m.uint16 = -1

        with self.assertRaises(ValueError):
            m.uint16 = 65536

        with self.assertRaises(ValueError):
            m.int32 = -2_147_483_649

        with self.assertRaises(ValueError):
            m.int32 = 2_147_483_648

        with self.assertRaises(ValueError):
            m.uint32 = -1

        with self.assertRaises(ValueError):
            m.uint32 = 4_294_967_296

        with self.assertRaises(ValueError):
            m.int64 = -9_223_372_036_854_775_809

        with self.assertRaises(ValueError):
            m.int64 = 9_223_372_036_854_775_808

        with self.assertRaises(ValueError):
            m.uint64 = -1

        with self.assertRaises(ValueError):
            m.uint64 = 18_446_744_073_709_551_616

        with self.assertRaises(ValueError):
            m.float = -4.40282346638528859811704183484516925441e38

        with self.assertRaises(ValueError):
            m.float = 4.40282346638528859811704183484516925441e38

        with self.assertRaises(ValueError):
            m.double = 2.79769313486231570814527423731704356798071e308

        with self.assertRaises(ValueError):
            m.double = -2.79769313486231570814527423731704356798071e308

        with self.assertRaises(ValueError):
            m.byte = -1

        with self.assertRaises(ValueError):
            m.byte = 256

        # Arrays
        with self.assertRaises(ValueError):
            m.int8_arr[0] = -129

        with self.assertRaises(ValueError):
            m.int8_arr[0] = 128

        with self.assertRaises(ValueError):
            m.uint8_arr[0] = -1

        with self.assertRaises(ValueError):
            m.uint8_arr[0] = 256

        with self.assertRaises(ValueError):
            m.int16_arr[0] = -32769

        with self.assertRaises(ValueError):
            m.int16_arr[0] = 32768

        with self.assertRaises(ValueError):
            m.uint16_arr[0] = -1

        with self.assertRaises(ValueError):
            m.uint16_arr[0] = 65536

        with self.assertRaises(ValueError):
            m.int32_arr[0] = -2_147_483_649

        with self.assertRaises(ValueError):
            m.int32_arr[0] = 2_147_483_648

        with self.assertRaises(ValueError):
            m.uint32_arr[0] = -1

        with self.assertRaises(ValueError):
            m.uint32_arr[0] = 4_294_967_296

        with self.assertRaises(ValueError):
            m.int64_arr[0] = -9_223_372_036_854_775_809

        with self.assertRaises(ValueError):
            m.int64_arr[0] = 9_223_372_036_854_775_808

        with self.assertRaises(ValueError):
            m.uint64_arr[0] = -1

        with self.assertRaises(ValueError):
            m.uint64_arr[0] = 18_446_744_073_709_551_616

        with self.assertRaises(ValueError):
            m.float_arr[0] = -4.40282346638528859811704183484516925441e38

        with self.assertRaises(ValueError):
            m.float_arr[0] = 4.40282346638528859811704183484516925441e38

        with self.assertRaises(ValueError):
            m.double_arr[0] = 2.79769313486231570814527423731704356798071e308

        with self.assertRaises(ValueError):
            m.double_arr[0] = -2.79769313486231570814527423731704356798071e308

        with self.assertRaises(ValueError):
            m.byte_arr[0] = -1

        with self.assertRaises(ValueError):
            m.byte_arr[0] = 256

    def test_array_len(self):
        m = MDF_VALIDATOR_A()

        with self.assertRaises(ValueError):
            m.int8_arr[:] = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.int8_arr[:] = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.uint8_arr[:] = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.uint8_arr[:] = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.int16_arr[:] = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.int16_arr[:] = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.uint16_arr[:] = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.uint16_arr[:] = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.int32_arr[:] = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.int32_arr[:] = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.uint32_arr[:] = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.uint32_arr[:] = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.int64_arr[:] = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.int64_arr[:] = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.uint64_arr[:] = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.uint64_arr[:] = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.float_arr[:] = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.float_arr[:] = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.double_arr[:] = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.double_arr[:] = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.byte_arr[:] = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.byte_arr[:] = [1, 2, 3, 4, 5]

        # test again without [:]
        with self.assertRaises(ValueError):
            m.int8_arr = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.int8_arr = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.uint8_arr = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.uint8_arr = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.int16_arr = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.int16_arr = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.uint16_arr = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.uint16_arr = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.int32_arr = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.int32_arr = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.uint32_arr = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.uint32_arr = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.int64_arr = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.int64_arr = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.uint64_arr = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.uint64_arr = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.float_arr = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.float_arr = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.double_arr = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.double_arr = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.byte_arr = [1, 2, 3, 4, 5]

        with self.assertRaises(ValueError):
            m.byte_arr = [1, 2, 3, 4, 5]

    def test_get_types(self):
        m = MDF_VALIDATOR_A()
        self.assertIsInstance(m.int8, int)
        self.assertIsInstance(m.int16, int)
        self.assertIsInstance(m.int32, int)
        self.assertIsInstance(m.int64, int)
        self.assertIsInstance(m.uint8, int)
        self.assertIsInstance(m.uint16, int)
        self.assertIsInstance(m.uint32, int)
        self.assertIsInstance(m.uint64, int)
        self.assertIsInstance(m.float, float)
        self.assertIsInstance(m.double, float)
        self.assertIsInstance(m.byte, int)
        self.assertIsInstance(m.char, str)
        self.assertIsInstance(m.string, str)
        self.assertIsInstance(m.struct, VALIDATOR_STRUCT)

        self.assertIsInstance(m.int8_arr, IntArray)
        self.assertIsInstance(m.int16_arr, IntArray)
        self.assertIsInstance(m.int32_arr, IntArray)
        self.assertIsInstance(m.int64_arr, IntArray)
        self.assertIsInstance(m.uint8_arr, IntArray)
        self.assertIsInstance(m.uint16_arr, IntArray)
        self.assertIsInstance(m.uint32_arr, IntArray)
        self.assertIsInstance(m.uint64_arr, IntArray)
        self.assertIsInstance(m.float_arr, FloatArray)
        self.assertIsInstance(m.double_arr, FloatArray)
        self.assertIsInstance(m.byte_arr, ByteArray)
        self.assertIsInstance(m.struct_arr, StructArray)

        # Single value
        self.assertIsInstance(m.int8_arr[0], int)
        self.assertIsInstance(m.int16_arr[0], int)
        self.assertIsInstance(m.int32_arr[0], int)
        self.assertIsInstance(m.int64_arr[0], int)
        self.assertIsInstance(m.uint8_arr[0], int)
        self.assertIsInstance(m.uint16_arr[0], int)
        self.assertIsInstance(m.uint32_arr[0], int)
        self.assertIsInstance(m.uint64_arr[0], int)

        # Slice
        self.assertIsInstance(m.int8_arr[0:2], list)
        self.assertIsInstance(m.int8_arr[0:2][0], int)

        self.assertIsInstance(m.int16_arr[0:2], list)
        self.assertIsInstance(m.int16_arr[0:2][0], int)

        self.assertIsInstance(m.int32_arr[0:2], list)
        self.assertIsInstance(m.int32_arr[0:2][0], int)

        self.assertIsInstance(m.int64_arr[0:2], list)
        self.assertIsInstance(m.int64_arr[0:2][0], int)

        self.assertIsInstance(m.uint8_arr[0:2], list)
        self.assertIsInstance(m.uint8_arr[0:2][0], int)

        self.assertIsInstance(m.uint16_arr[0:2], list)
        self.assertIsInstance(m.uint16_arr[0:2][0], int)

        self.assertIsInstance(m.uint32_arr[0:2], list)
        self.assertIsInstance(m.uint32_arr[0:2][0], int)

        self.assertIsInstance(m.uint64_arr[0:2], list)
        self.assertIsInstance(m.uint64_arr[0:2][0], int)

        self.assertIsInstance(m.byte_arr[0:2], bytearray)
        self.assertIsInstance(m.byte_arr[0:2][0], int)

        self.assertIsInstance(m.struct_arr[0:2], list)
        self.assertIsInstance(m.struct_arr[0:2][0], VALIDATOR_STRUCT)

    def test_invalid_set_types(self):
        A = MDF_VALIDATOR_A()
        B = MDF_VALIDATOR_B()

        with self.assertRaises(TypeError):
            A.char = 1

        with self.assertRaises(TypeError):
            A.int8 = "a"

        with self.assertRaises(TypeError):
            A.int16 = [1, 2, 3]

        with self.assertRaises(TypeError):
            A.int32 = b"1"

        with self.assertRaises(TypeError):
            A.int64 = dict()

        with self.assertRaises(TypeError):
            A.uint8 = "abc"

        with self.assertRaises(TypeError):
            A.uint16 = object()

        with self.assertRaises(TypeError):
            A.uint32 = "a"

        with self.assertRaises(TypeError):
            A.uint64 = "a"

        with self.assertRaises(TypeError):
            A.float = "a"

        with self.assertRaises(TypeError):
            A.double = b"1"

        with self.assertRaises(TypeError):
            A.byte = "a"

        with self.assertRaises(TypeError):
            A.string = 1

        # Int8
        with self.assertRaises(ValueError):
            A.int8_arr = B.int8_arr

        with self.assertRaises(TypeError):
            A.int8_arr = IntArray(Int16, 4)

        with self.assertRaises(ValueError):
            A.int8_arr = IntArray(Int8, 4)

        # Int16
        with self.assertRaises(ValueError):
            A.int16_arr = B.int16_arr

        with self.assertRaises(TypeError):
            A.int16_arr = IntArray(Int8, 4)

        with self.assertRaises(ValueError):
            A.int16_arr = IntArray(Int16, 4)

        # Int32
        with self.assertRaises(ValueError):
            A.int32_arr = B.int32_arr

        with self.assertRaises(TypeError):
            A.int32_arr = IntArray(Int16, 4)

        with self.assertRaises(ValueError):
            A.int32_arr = IntArray(Int32, 4)

        # Int64
        with self.assertRaises(ValueError):
            A.int64_arr = B.int64_arr

        with self.assertRaises(TypeError):
            A.int64_arr = IntArray(Int16, 4)

        with self.assertRaises(ValueError):
            A.int64_arr = IntArray(Int64, 4)

        # Uint8
        with self.assertRaises(ValueError):
            A.uint8_arr = B.uint8_arr

        with self.assertRaises(TypeError):
            A.uint8_arr = IntArray(Int16, 4)

        with self.assertRaises(ValueError):
            A.uint8_arr = IntArray(Uint8, 4)

        # Uint16
        with self.assertRaises(ValueError):
            A.uint16_arr = B.uint16_arr

        with self.assertRaises(TypeError):
            A.uint16_arr = IntArray(Int16, 4)

        with self.assertRaises(ValueError):
            A.uint16_arr = IntArray(Uint16, 4)

        # Uint32
        with self.assertRaises(ValueError):
            A.uint32_arr = B.uint32_arr

        with self.assertRaises(TypeError):
            A.uint32_arr = IntArray(Int16, 4)

        with self.assertRaises(ValueError):
            A.uint32_arr = IntArray(Uint32, 4)

        # Uint64
        with self.assertRaises(ValueError):
            A.uint64_arr = B.uint64_arr

        with self.assertRaises(TypeError):
            A.uint64_arr = IntArray(Int16, 4)

        with self.assertRaises(ValueError):
            A.uint64_arr = IntArray(Uint64, 4)

        # Float
        with self.assertRaises(ValueError):
            A.float_arr = B.float_arr

        with self.assertRaises(TypeError):
            A.float_arr = FloatArray(Double, 4)

        with self.assertRaises(ValueError):
            A.float_arr = FloatArray(Float, 4)

        # Double
        with self.assertRaises(ValueError):
            A.double_arr = B.double_arr

        with self.assertRaises(TypeError):
            A.double_arr = FloatArray(Float, 4)

        with self.assertRaises(ValueError):
            A.double_arr = FloatArray(Double, 4)

        # Byte
        with self.assertRaises(ValueError):
            A.byte_arr = B.byte_arr

        with self.assertRaises(ValueError):
            A.byte_arr = ByteArray(4)

        # Struct
        with self.assertRaises(TypeError):
            A.struct_arr = [1, 2, 3, 4]

        with self.assertRaises(ValueError):
            A.struct_arr = B.struct_arr

        with self.assertRaises(TypeError):
            A.struct_arr = StructArray(MDF_VALIDATOR_B, 4)

        with self.assertRaises(ValueError):
            A.struct_arr = StructArray(VALIDATOR_STRUCT, 4)

    def test_valid_set_types(self):
        A = MDF_VALIDATOR_A()

        A.char = "a"
        A.int8 = 1
        A.int16 = 1
        A.int32 = 1
        A.int64 = 1
        A.uint8 = 1
        A.uint16 = 1
        A.uint32 = 1
        A.uint64 = 1

        A.float = 1.0
        A.double = 1.0

        A.float = 1
        A.double = 1

        A.byte = 1
        A.byte = b"A"
        A.byte = bytes(1)
        A.byte = bytearray(1)

        A.string = "abc"

        A.int8_arr[0] = 1
        A.int16_arr[0] = 1
        A.int32_arr[0] = 1
        A.int64_arr[0] = 1
        A.uint8_arr[0] = 1
        A.uint16_arr[0] = 1
        A.uint32_arr[0] = 1
        A.uint64_arr[0] = 1
        A.float_arr[0] = 1
        A.double_arr[0] = 1

        A.float_arr[0] = 1.0
        A.double_arr[0] = 1.0

        A.byte_arr[0] = 1
        A.byte_arr[0] = b"A"
        A.byte_arr[0] = bytes(1)
        A.byte_arr[0] = bytearray(1)

        A.struct_arr[0] = VALIDATOR_STRUCT()

        A.int8_arr[:] = [1, 2, 3, 4]
        A.int16_arr[:] = [1, 2, 3, 4]
        A.int32_arr[:] = [1, 2, 3, 4]
        A.int64_arr[:] = [1, 2, 3, 4]
        A.uint8_arr[:] = [1, 2, 3, 4]
        A.uint16_arr[:] = [1, 2, 3, 4]
        A.uint32_arr[:] = [1, 2, 3, 4]
        A.uint64_arr[:] = [1, 2, 3, 4]
        A.float_arr[:] = [1.0, 2.0, 3.0, 4.0]
        A.double_arr[:] = [1.0, 2.0, 3.0, 4.0]

        A.float_arr[:] = [1, 2, 3, 4]
        A.double_arr[:] = [1, 2, 3, 4]

        A.byte_arr[:] = [1, 2, 3, 4]
        A.byte_arr[:] = b"ABCD"
        A.byte_arr[:] = bytes(4)
        A.byte_arr[:] = bytearray(4)

        A.struct_arr[:] = [
            VALIDATOR_STRUCT(),
            VALIDATOR_STRUCT(),
            VALIDATOR_STRUCT(),
            VALIDATOR_STRUCT(),
        ]

        # again without [:]
        A.int8_arr = [1, 2, 3, 4]
        A.int16_arr = [1, 2, 3, 4]
        A.int32_arr = [1, 2, 3, 4]
        A.int64_arr = [1, 2, 3, 4]
        A.uint8_arr = [1, 2, 3, 4]
        A.uint16_arr = [1, 2, 3, 4]
        A.uint32_arr = [1, 2, 3, 4]
        A.uint64_arr = [1, 2, 3, 4]
        A.float_arr = [1.0, 2.0, 3.0, 4.0]
        A.double_arr = [1.0, 2.0, 3.0, 4.0]

        A.float_arr = [1, 2, 3, 4]
        A.double_arr = [1, 2, 3, 4]

        A.byte_arr = [1, 2, 3, 4]
        A.byte_arr = b"ABCD"
        A.byte_arr = bytes(4)
        A.byte_arr = bytearray(4)

        A.struct_arr = [
            VALIDATOR_STRUCT(),
            VALIDATOR_STRUCT(),
            VALIDATOR_STRUCT(),
            VALIDATOR_STRUCT(),
        ]

    def test_refs(self):
        A = MDF_VALIDATOR_A()
        B = MDF_VALIDATOR_A()

        A.char = "a"
        A.int8 = 1
        A.int16 = 1
        A.int32 = 1
        A.int64 = 1
        A.uint8 = 1
        A.uint16 = 1
        A.uint32 = 1
        A.uint64 = 1
        A.float = 1.0
        A.double = 1.0
        A.byte = 1
        A.string = "abc"

        A.int8_arr[0] = 1
        A.int16_arr[0] = 1
        A.int32_arr[0] = 1
        A.int64_arr[0] = 1
        A.uint8_arr[0] = 1
        A.uint16_arr[0] = 1
        A.uint32_arr[0] = 1
        A.uint64_arr[0] = 1
        A.float_arr[0] = 1
        A.double_arr[0] = 1
        A.byte_arr[0] = 1
        A.struct_arr[0].char = "a"

        self.assertFalse(A.char == B.char)
        self.assertFalse(A.int8 == B.int8)
        self.assertFalse(A.int16 == B.int16)
        self.assertFalse(A.int32 == B.int32)
        self.assertFalse(A.int64 == B.int64)
        self.assertFalse(A.uint8 == B.uint8)
        self.assertFalse(A.uint16 == B.uint16)
        self.assertFalse(A.uint32 == B.uint32)
        self.assertFalse(A.uint64 == B.uint64)
        self.assertFalse(A.float == B.float)
        self.assertFalse(A.double == B.double)
        self.assertFalse(A.byte == B.byte)
        self.assertFalse(A.string == B.string)
        self.assertFalse(A.int8_arr == B.int8_arr)
        self.assertFalse(A.int16_arr == B.int16_arr)
        self.assertFalse(A.int32_arr == B.int32_arr)
        self.assertFalse(A.int64_arr == B.int64_arr)
        self.assertFalse(A.uint8_arr == B.uint8_arr)
        self.assertFalse(A.uint16_arr == B.uint16_arr)
        self.assertFalse(A.uint32_arr == B.uint32_arr)
        self.assertFalse(A.uint64_arr == B.uint64_arr)
        self.assertFalse(A.float_arr == B.float_arr)
        self.assertFalse(A.double_arr == B.double_arr)
        self.assertFalse(A.byte_arr == B.byte_arr)
        self.assertFalse(A.struct_arr == B.struct_arr)

        self.assertFalse(A.int8_arr is B.int8_arr)
        self.assertFalse(A.int16_arr is B.int16_arr)
        self.assertFalse(A.int32_arr is B.int32_arr)
        self.assertFalse(A.int64_arr is B.int64_arr)
        self.assertFalse(A.uint8_arr is B.uint8_arr)
        self.assertFalse(A.uint16_arr is B.uint16_arr)
        self.assertFalse(A.uint32_arr is B.uint32_arr)
        self.assertFalse(A.uint64_arr is B.uint64_arr)
        self.assertFalse(A.float_arr is B.float_arr)
        self.assertFalse(A.double_arr is B.double_arr)
        self.assertFalse(A.byte_arr is B.byte_arr)
        self.assertFalse(A.struct_arr is B.struct_arr)
