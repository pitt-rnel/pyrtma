import tempfile
import pyrtma.parser
import textwrap
import pathlib
import logging
import unittest


class TempDefFile:
    def __init__(self):
        self.file = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
        self.file.close()
        self.path = pathlib.Path(self.file.name)

    def __del__(self):
        if not self.file.closed:
            self.file.close()

        self.path.unlink()

    def write(self, text: str):
        if not self.file.closed:
            self.file.close()

        with open(self.path, "w") as f:
            f.write(text)


class TestParser(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = pyrtma.parser.Parser()
        self.parser.logger.setLevel(logging.ERROR)

        self.tmp = TempDefFile()
        self.tmp2 = TempDefFile()

    def TearDown(self) -> None:
        del self.tmp
        del self.tmp2

    def test_host_id_conflicts(self):
        dup_host_id = textwrap.dedent(
            """
            host_ids:
                A: 10
                B: 10
            """
        )

        self.tmp.write(dup_host_id)

        with self.assertRaises(pyrtma.parser.HostIDError):
            self.parser.parse(self.tmp.path)

    def test_module_id_conflicts(self):
        dup_mod_id = textwrap.dedent(
            """
            module_ids:
                A: 10
                B: 10
            """
        )

        self.tmp.write(dup_mod_id)

        with self.assertRaises(pyrtma.parser.ModuleIDError):
            self.parser.parse(self.tmp.path)

    def test_signal_id_conflicts(self):
        # Duplicate Signal
        dup_msg_id = textwrap.dedent(
            """
            message_defs:
                A:
                    id: 100
                    fields: null
                B:
                    id: 100
                    fields: null
            """
        )

        self.tmp.write(dup_msg_id)

        with self.assertRaises(pyrtma.parser.MessageIDError):
            self.parser.parse(self.tmp.path)

    def test_message_id_conflicts(self):
        # Duplicate Message
        dup_msg_id = textwrap.dedent(
            """
            message_defs:
                A:
                    id: 100
                    fields:
                        i: int
                B:
                    id: 100
                    fields:
                        i: int
            """
        )

        self.tmp.write(dup_msg_id)

        with self.assertRaises(pyrtma.parser.MessageIDError):
            self.parser.parse(self.tmp.path)

    def test_duplicate_message(self):
        dup_msg = textwrap.dedent(
            """
            message_defs:
                A:
                    id: 100
                    fields:
                        i: int
            """
        )

        self.tmp.write(dup_msg)
        self.parser.parse(self.tmp.path)
        self.tmp2.write(dup_msg)

        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp2.path)

    def test_duplicate_module(self):
        dup_msg = textwrap.dedent(
            """
            module_ids:
                A: 80
            """
        )

        self.tmp.write(dup_msg)
        self.parser.parse(self.tmp.path)
        self.tmp2.write(dup_msg)

        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp2.path)

    def test_duplicate_host(self):
        dup_msg = textwrap.dedent(
            """
            host_ids:
                A: 80
            """
        )

        self.tmp.write(dup_msg)
        self.parser.parse(self.tmp.path)
        self.tmp2.write(dup_msg)

        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp2.path)

    def test_duplicate_constant(self):
        dup_msg = textwrap.dedent(
            """
            constants:
                A: 80
            """
        )

        self.tmp.write(dup_msg)
        self.parser.parse(self.tmp.path)
        self.tmp2.write(dup_msg)

        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp2.path)

    def test_constant_name_conflicts(self):
        text = textwrap.dedent(
            """
            constants:
                A: 80
            string_constants:
                A: "abc"
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent(
            """
            constants:
                A: 80
            string_constants:
                A: "abc"
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent(
            """
            constants:
                A: 80
            aliases:
                A: int
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent(
            """
            constants:
                A: 80
            struct_defs:
                A:
                    id: 88
                    fields: null
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent(
            """
            constants:
                A: 80
            message_defs:
                A:
                    id: 88
                    fields: null
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

    def test_string_constant_name_conflicts(self):
        text = textwrap.dedent(
            """
            constants:
                A: 80
            string_constants:
                A: "abc"
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent(
            """
            string_constants:
                A: "abc"
            aliases:
                A: int
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent(
            """
            string_constants:
                A: "abc"
            struct_defs:
                A:
                    id: 88
                    fields: null
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent(
            """
            string_constants:
                A: "abc"
            message_defs:
                A:
                    id: 88
                    fields: null
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

    def test_alias_name_conflicts(self):
        text = textwrap.dedent(
            """
            constants:
                A: 80
            aliases:
                A: int
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent(
            """
            string_constants:
                A: "abc"
            aliases:
                A: int
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent(
            """
            aliases:
                A: int
            struct_defs:
                A:
                    fields:
                        i: int
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent(
            """
            aliases:
                A: int
            message_defs:
                A:
                    id: 88
                    fields: null
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

    def test_struct_name_conflicts(self):
        text = textwrap.dedent(
            """
            constants:
                A: 80
            struct_defs:
                A:
                    fields:
                        i: int
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent(
            """
            string_constants:
                A: "abc"
            struct_defs:
                A:
                    fields:
                        i: int
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent(
            """
            aliases:
                A: int
            struct_defs:
                A:
                    fields:
                        i: int
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent(
            """
            struct_defs:
                A:
                    fields:
                        i: int
            message_defs:
                A:
                    id: 88
                    fields: null
            """
        )

        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

    def test_message_name_conflicts(self):
        text = textwrap.dedent(
            """
            constants:
                A: 80
            message_defs:
                A:
                    id: 88
                    fields:
                        i: int
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent(
            """
            string_constants:
                A: "abc"
            message_defs:
                A:
                    id: 88
                    fields:
                        i: int
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent(
            """
            aliases:
                A: int
            message_defs:
                A:
                    id: 88
                    fields:
                        i: int
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent(
            """
            struct_defs:
                A:
                    fields:
                        i: int
            message_defs:
                A:
                    id: 88
                    fields: null
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

    def test_yaml_syntax(self):
        # Duplicate Key
        text = textwrap.dedent(
            """
            struct_defs:
                A:
                    fields:
                        i: int
            struct_defs:
                A:
                    fields:
                        i: int
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.YAMLSyntaxError):
            self.parser.parse(self.tmp.path)

    def test_rtma_syntax(self):
        # Bad Name
        text = textwrap.dedent(
            """
            struct_defs:
                _A:
                    fields:
                        i: int
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.RTMASyntaxError):
            self.parser.parse(self.tmp.path)

        # Bad Name
        text = textwrap.dedent(
            """
            message_defs:
                _A:
                    fields:
                        i: int
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.RTMASyntaxError):
            self.parser.parse(self.tmp.path)

        # Bad Name
        text = textwrap.dedent(
            """
            constants:
                _A: 10
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.RTMASyntaxError):
            self.parser.parse(self.tmp.path)

        # Bad Name
        text = textwrap.dedent(
            """
            aliases:
                _A: int
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.RTMASyntaxError):
            self.parser.parse(self.tmp.path)

        # Illegal field name
        text = textwrap.dedent(
            """
            message_defs:
                A:
                    id: 88
                    fields:
                        type_name: int
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.RTMASyntaxError):
            self.parser.parse(self.tmp.path)

        # Bad Indentation
        text = textwrap.dedent(
            """
            struct_defs:
            A:
                fields:
                    i: int
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.RTMASyntaxError):
            self.parser.parse(self.tmp.path)

        # Wrong Type for imports
        text = textwrap.dedent(
            """
            imports:
                A: abc
            """
        )

        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.RTMASyntaxError):
            self.parser.parse(self.tmp.path)

    def test_type_error(self):
        # Wrong Type for host_id
        text = textwrap.dedent(
            """
            host_ids:
                A: abc
            """
        )

        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.InvalidTypeError):
            self.parser.parse(self.tmp.path)

        # Wrong Type for module_id
        text = textwrap.dedent(
            """
            module_ids:
                A: abc
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.InvalidTypeError):
            self.parser.parse(self.tmp.path)

    def test_reserve_syntax(self):
        text = textwrap.dedent(
            """
            message_defs:
                _RESERVED_:
                    fields:
                        i: int
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.RTMASyntaxError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent(
            """
            message_defs:
                _RESERVED_: 1
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.InvalidTypeError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent(
            """
            message_defs:
                _RESERVED_: [1:2:10]
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.YAMLSyntaxError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent(
            """
            message_defs:
                _RESERVED_: [1-2-10]
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.InvalidTypeError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent(
            """
            message_defs:
                _RESERVED_:
                    id: 1
            """
        )
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.InvalidTypeError):
            self.parser.parse(self.tmp.path)

    def test_auto_padding(self):
        text = textwrap.dedent(
            """
            message_defs:
                A:
                    id: 1001
                    fields:
                        i: int
                        d: double
                        c: char
                B:
                    id: 1002
                    fields:
                        c: char
                        i: int
                        d: double
                C:
                    id: 1003
                    fields:
                        f: float[2]
                        i: int64
                        d: int32[3]
                D:
                    id: 1004
                    fields:
                        f: float
                        i: int64
                        c: char[7]
                E:
                    id: 1005
                    fields:
                        a: A
                        b: B
                        c: C
                        d: D

            """
        )

        self.tmp.write(text)
        self.parser.parse(self.tmp.path)
