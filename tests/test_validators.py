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
