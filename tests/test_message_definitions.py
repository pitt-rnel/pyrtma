import pathlib
import shutil
import sys
import unittest

import pytest

import pyrtma.core_defs as cd
from pyrtma.data_logger.dataset import Dataset
from pyrtma.definitions import MessageDefinitions
from pyrtma.exceptions import MessageDefinitionsLoadError
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


TEST_DEFS = pathlib.Path(__file__).parent / "test_msg_defs" / "test_defs.py"


def loaded_definition_files() -> set[str]:
    """The names of the modules the loader has put in ``sys.modules``.

    Returns:
        Their names, which start with ``_pyrtma_defs_``.
    """
    return {name for name in sys.modules if name.startswith("_pyrtma_defs_")}


def test_failed_import_leaves_nothing_in_sys_modules(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "broken_defs.py"
    path.write_text("raise RuntimeError('half written')\n", encoding="utf-8")
    before = loaded_definition_files()

    with pytest.raises(MessageDefinitionsLoadError):
        load_message_definitions(path)

    assert loaded_definition_files() == before


def test_failed_import_can_be_retried(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "fixed_defs.py"
    path.write_text("raise RuntimeError('half written')\n", encoding="utf-8")
    with pytest.raises(MessageDefinitionsLoadError):
        load_message_definitions(path)
    shutil.copyfile(TEST_DEFS, path)

    defs = load_message_definitions(path)

    assert defs.message_id_from_name("TEST_START") is not None


def test_loading_a_file_twice_gives_the_same_classes(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "copied_defs.py"
    shutil.copyfile(TEST_DEFS, path)

    first = load_message_definitions(path)
    second = load_message_definitions(path)

    type_id = first.message_id_from_name("TEST_START")
    assert type_id is not None
    assert first.get_msg_cls(type_id) is second.get_msg_cls(type_id)


def test_errors_from_get_message_definitions_are_wrapped(
    tmp_path: pathlib.Path,
) -> None:
    path = tmp_path / "failing_defs.py"
    path.write_text(
        "COMPILED_PYRTMA_VERSION = '4.0.0'\n"
        "def get_message_definitions():\n"
        "    raise KeyError('missing')\n",
        encoding="utf-8",
    )

    with pytest.raises(MessageDefinitionsLoadError) as info:
        load_message_definitions(path)

    assert isinstance(info.value.__cause__, KeyError)


if __name__ == "__main__":
    unittest.main()
