import pathlib
import unittest

import pyrtma.core_defs as cd
from pyrtma.data_logger.dataset import Dataset
from pyrtma.definitions import MessageDefinitions
from pyrtma.loader import load_message_definitions


class TestMessageDefinitions(unittest.TestCase):
    def test_core_defs_exposes_message_definitions(self):
        defs = cd.get_message_definitions()

        self.assertIsInstance(defs, MessageDefinitions)
        self.assertEqual(defs.message_id_from_name("ACKNOWLEDGE"), cd.MT_ACKNOWLEDGE)

        msg_cls = defs.get_msg_cls(cd.MT_ACKNOWLEDGE)
        self.assertEqual(msg_cls.type_name, "ACKNOWLEDGE")

    def test_load_message_definitions_from_core_file(self):
        defs_path = pathlib.Path(cd.__file__)
        defs = load_message_definitions(defs_path)

        self.assertIsInstance(defs, MessageDefinitions)
        self.assertEqual(defs.message_name_from_id(cd.MT_ACKNOWLEDGE), "ACKNOWLEDGE")

    def test_load_legacy_message_definitions_file(self):
        defs_path = pathlib.Path(__file__).parent / "test_msg_defs" / "test_defs.py"
        defs = load_message_definitions(defs_path)

        self.assertIsInstance(defs, MessageDefinitions)
        self.assertEqual(defs.message_id_from_name("ACKNOWLEDGE"), cd.MT_ACKNOWLEDGE)

    def test_dataset_uses_explicit_definitions_without_client(self):
        defs_path = pathlib.Path(__file__).parent / "test_msg_defs" / "test_defs.py"
        defs = load_message_definitions(defs_path)

        ds = Dataset(
            name="alias",
            save_path=".",
            filename="alias",
            formatter="json",
            msg_types=[6000],
            create_client=False,
            definitions=defs,
        )

        self.assertEqual(ds.msg_names, ("ALIAS_TEST",))


if __name__ == "__main__":
    unittest.main()
