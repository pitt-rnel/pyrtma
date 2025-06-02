import unittest
import pyrtma
import pyrtma.core_defs as cd
import sys
from .test_msg_defs import test_defs as td

sys.path.append("..")
from examples.msg_defs import example_messages as em


class TestMessageVersion(unittest.TestCase):
    """Test that the core defs and example/test defs were built
    with the same version of pyrtma

    It is easy to miss this step before deployment, so this test will catch it
    """

    def test_version(self):
        with self.subTest("core def version"):
            self.assertEqual(pyrtma.__version__, cd.COMPILED_PYRTMA_VERSION)
        with self.subTest("test def version"):
            self.assertEqual(pyrtma.__version__, td.COMPILED_PYRTMA_VERSION)
        with self.subTest("example def version"):
            self.assertEqual(pyrtma.__version__, em.COMPILED_PYRTMA_VERSION)
