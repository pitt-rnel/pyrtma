from sys import version_info
import unittest

if version_info[:2] < (3, 8):
    raise unittest.SkipTest("parser does not support < 3.8")

import tempfile
import pyrtma.parser
import textwrap
import pathlib
from pathlib import Path
import logging
import unittest


class TempDefFile:
    def __init__(self):
        self.compiler_file = tempfile.NamedTemporaryFile(
            "w", suffix=".defs", delete=False
        )
        self.compiler_file.close()
        self.compiler_path = pathlib.Path(self.compiler_file.name)

        self.msg_file = tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False)
        self.msg_file.close()
        self.msg_path = pathlib.Path(self.msg_file.name)

    @property
    def path(self) -> pathlib.Path:
        return self.compiler_path

    def __del__(self):
        if not self.compiler_file.closed:
            self.compiler_file.close()
        if self.compiler_path.exists():
            self.compiler_path.unlink()

        if not self.msg_file.closed:
            self.msg_file.close()
        if self.msg_path.exists():
            self.msg_path.unlink()

    def write(self, text: str):
        if not self.compiler_file.closed:
            self.compiler_file.close()

        if not self.msg_file.closed:
            self.msg_file.close()

        with open(self.compiler_path, "w") as f:
            f.write("index:\n")
            f.write(f"  test: {self.msg_path.absolute()}\n")

        with open(self.msg_path, "w") as f:
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
        dup_host_id = textwrap.dedent("""
            host_ids:
                A: 10
                B: 10
            """)

        self.tmp.write(dup_host_id)

        with self.assertRaises(pyrtma.parser.HostIDError):
            self.parser.parse(self.tmp.path)

    def test_module_id_conflicts(self):
        dup_mod_id = textwrap.dedent("""
            module_ids:
                A: 10
                B: 10
            """)

        self.tmp.write(dup_mod_id)

        with self.assertRaises(pyrtma.parser.ModuleIDError):
            self.parser.parse(self.tmp.path)

    def test_signal_id_conflicts(self):
        # Duplicate Signal
        dup_msg_id = textwrap.dedent("""
            message_defs:
                A:
                    id: 100
                    fields: null
                B:
                    id: 100
                    fields: null
            """)

        self.tmp.write(dup_msg_id)

        with self.assertRaises(pyrtma.parser.MessageIDError):
            self.parser.parse(self.tmp.path)

    def test_message_id_conflicts(self):
        # Duplicate Message
        dup_msg_id = textwrap.dedent("""
            message_defs:
                A:
                    id: 100
                    fields:
                        i: int
                B:
                    id: 100
                    fields:
                        i: int
            """)

        self.tmp.write(dup_msg_id)

        with self.assertRaises(pyrtma.parser.MessageIDError):
            self.parser.parse(self.tmp.path)

    def test_duplicate_message(self):
        dup_msg = textwrap.dedent("""
            message_defs:
                A:
                    id: 100
                    fields:
                        i: int
            """)

        self.tmp.write(dup_msg)
        self.parser.parse(self.tmp.path)
        self.tmp2.write(dup_msg)

        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp2.path)

    def test_duplicate_module(self):
        dup_msg = textwrap.dedent("""
            module_ids:
                A: 1000
            """)

        self.tmp.write(dup_msg)
        self.parser.parse(self.tmp.path)
        self.tmp2.write(dup_msg)

        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp2.path)

    def test_duplicate_host(self):
        dup_msg = textwrap.dedent("""
            host_ids:
                A: 80
            """)

        self.tmp.write(dup_msg)
        self.parser.parse(self.tmp.path)
        self.tmp2.write(dup_msg)

        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp2.path)

    def test_duplicate_constant(self):
        dup_msg = textwrap.dedent("""
            constants:
                A: 80
            """)

        self.tmp.write(dup_msg)
        self.parser.parse(self.tmp.path)
        self.tmp2.write(dup_msg)

        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp2.path)

    def test_constant_name_conflicts(self):
        text = textwrap.dedent("""
            constants:
                A: 80
            string_constants:
                A: "abc"
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent("""
            constants:
                A: 80
            string_constants:
                A: "abc"
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent("""
            constants:
                A: 80
            aliases:
                A: int
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent("""
            constants:
                A: 80
            struct_defs:
                A:
                    id: 1000
                    fields: null
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent("""
            constants:
                A: 80
            message_defs:
                A:
                    id: 1000
                    fields: null
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

    def test_string_constant_name_conflicts(self):
        text = textwrap.dedent("""
            constants:
                A: 80
            string_constants:
                A: "abc"
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent("""
            string_constants:
                A: "abc"
            aliases:
                A: int
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent("""
            string_constants:
                A: "abc"
            struct_defs:
                A:
                    id: 1000
                    fields: null
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent("""
            string_constants:
                A: "abc"
            message_defs:
                A:
                    id: 1000
                    fields: null
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

    def test_alias_name_conflicts(self):
        text = textwrap.dedent("""
            constants:
                A: 80
            aliases:
                A: int
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent("""
            string_constants:
                A: "abc"
            aliases:
                A: int
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent("""
            aliases:
                A: int
            struct_defs:
                A:
                    fields:
                        i: int
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent("""
            aliases:
                A: int
            message_defs:
                A:
                    id: 1000
                    fields: null
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

    def test_struct_name_conflicts(self):
        text = textwrap.dedent("""
            constants:
                A: 80
            struct_defs:
                A:
                    fields:
                        i: int
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent("""
            string_constants:
                A: "abc"
            struct_defs:
                A:
                    fields:
                        i: int
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent("""
            aliases:
                A: int
            struct_defs:
                A:
                    fields:
                        i: int
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent("""
            struct_defs:
                A:
                    fields:
                        i: int
            message_defs:
                A:
                    id: 1000
                    fields: null
            """)

        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

    def test_message_name_conflicts(self):
        text = textwrap.dedent("""
            constants:
                A: 80
            message_defs:
                A:
                    id: 1000
                    fields:
                        i: int
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent("""
            string_constants:
                A: "abc"
            message_defs:
                A:
                    id: 1000
                    fields:
                        i: int
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent("""
            aliases:
                A: int
            message_defs:
                A:
                    id: 1000
                    fields:
                        i: int
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent("""
            struct_defs:
                A:
                    fields:
                        i: int
            message_defs:
                A:
                    id: 1000
                    fields: null
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.DuplicateNameError):
            self.parser.parse(self.tmp.path)

    def test_yaml_syntax(self):
        # Duplicate Key
        text = textwrap.dedent("""
            struct_defs:
                A:
                    fields:
                        i: int
            struct_defs:
                A:
                    fields:
                        i: int
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.YAMLSyntaxError):
            self.parser.parse(self.tmp.path)

    def test_rtma_syntax(self):
        # Bad Name
        text = textwrap.dedent("""
            struct_defs:
                _A:
                    fields:
                        i: int
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.RTMASyntaxError):
            self.parser.parse(self.tmp.path)

        # Bad Name
        text = textwrap.dedent("""
            message_defs:
                _A:
                    fields:
                        i: int
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.RTMASyntaxError):
            self.parser.parse(self.tmp.path)

        # Bad Name
        text = textwrap.dedent("""
            constants:
                _A: 10
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.RTMASyntaxError):
            self.parser.parse(self.tmp.path)

        # Bad Name
        text = textwrap.dedent("""
            aliases:
                _A: int
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.RTMASyntaxError):
            self.parser.parse(self.tmp.path)

        # Illegal field name
        text = textwrap.dedent("""
            message_defs:
                A:
                    id:  1000
                    fields:
                        type_name: int
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.RTMASyntaxError):
            self.parser.parse(self.tmp.path)

        # Bad Indentation
        text = textwrap.dedent("""
            struct_defs:
            A:
                fields:
                    i: int
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.RTMASyntaxError):
            self.parser.parse(self.tmp.path)

        # Wrong Type for imports
        text = textwrap.dedent("""
            imports:
                A: abc
            """)

        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.RTMASyntaxError):
            self.parser.parse(self.tmp.path)

    def test_type_error(self):
        # Wrong Type for host_id
        text = textwrap.dedent("""
            host_ids:
                A: abc
            """)

        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.InvalidTypeError):
            self.parser.parse(self.tmp.path)

        # Wrong Type for module_id
        text = textwrap.dedent("""
            module_ids:
                A: abc
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.InvalidTypeError):
            self.parser.parse(self.tmp.path)

    def test_reserve_syntax(self):
        text = textwrap.dedent("""
            message_defs:
                _RESERVED_:
                    fields:
                        i: int
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.RTMASyntaxError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent("""
            message_defs:
                _RESERVED_: 1
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.InvalidTypeError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent("""
            message_defs:
                _RESERVED_: [1:2:10]
            """)
        self.tmp.write(text)
        with self.assertRaises(
            (pyrtma.parser.YAMLSyntaxError, pyrtma.parser.InvalidTypeError)
        ):
            # YAMLSyntaxError does not happen on 3.13 (expression is read as string instead)
            # InvalidTypeError will happen if not caught by yaml loader
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent("""
            message_defs:
                _RESERVED_: [1-2-10]
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.InvalidTypeError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent("""
            message_defs:
                _RESERVED_:
                    id: 1
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.InvalidTypeError):
            self.parser.parse(self.tmp.path)

    def test_auto_padding(self):
        text = textwrap.dedent("""
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

            """)

        self.tmp.write(text)
        self.parser.parse(self.tmp.path)

    def test_reserved_fields(self):
        text = textwrap.dedent("""
            message_defs:
                _RESERVED_:
                    fields:
                        auto: int
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.RTMASyntaxError):
            self.parser.parse(self.tmp.path)

    def test_prefix_fields(self):
        text = textwrap.dedent("""
            message_defs:
                A:
                    id: 1001
                    fields:
                        _bad_prefix: int
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.RTMASyntaxError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent("""
            message_defs:
                A:
                    id: 1001
                    fields:
                        9bad_prefix: int
            """)
        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.RTMASyntaxError):
            self.parser.parse(self.tmp.path)

        text = textwrap.dedent("""
            constants:
                _bad_prefix: 10
            """)

        self.tmp.write(text)
        with self.assertRaises(pyrtma.parser.RTMASyntaxError):
            self.parser.parse(self.tmp.path)


# The tests below are pytest tests, written in Phase 8. Each writes its
# definitions to ``tmp_path`` and parses them with a parser whose log is
# recorded rather than printed.

import pytest

from pyrtma.parser import (
    CircularRefError,
    ExpressionExpansionError,
    ParserError,
    RecurisionError,
    RTMASyntaxError,
)

from .helpers import parse_definitions, write_definitions


def message(field_spec: str, *, constants: str = "") -> str:
    """YAML for one message, ``M``, with one field, ``a``.

    Args:
        field_spec: The field's type, such as ``int32[4]``.
        constants: Lines for a ``constants`` section, if any.

    Returns:
        The YAML text.
    """
    text = ""
    if constants:
        text += "constants:\n" + "".join(
            f"  {line}\n" for line in constants.splitlines()
        )
    text += f"message_defs:\n  M:\n    id: 7000\n    fields:\n      a: {field_spec}\n"
    return text


def chain(depth: int) -> str:
    """Constants ``C0`` to ``C<depth>``, each one more than the one before.

    Args:
        depth: How deeply the last constant is nested.

    Returns:
        Lines for a ``constants`` section.
    """
    lines = ["C0: 1"] + [f"C{n}: C{n - 1} + 1" for n in range(1, depth + 1)]
    return "\n".join(lines)


class TestArrayLengths:
    @pytest.mark.parametrize(
        ("spec", "constants"),
        [("int32[0]", ""), ("int32[N]", "N: 0"), ("int32[N - 4]", "N: 4")],
    )
    def test_zero_length_is_rejected(
        self, tmp_path: Path, spec: str, constants: str
    ) -> None:
        defs = write_definitions(tmp_path, {"m": message(spec, constants=constants)})

        with pytest.raises(RTMASyntaxError, match="M.a"):
            parse_definitions(defs)

    def test_fractional_length_is_rejected(self, tmp_path: Path) -> None:
        defs = write_definitions(
            tmp_path, {"m": message("int32[N / 3]", constants="N: 8")}
        )

        with pytest.raises(RTMASyntaxError, match="whole number"):
            parse_definitions(defs)

    def test_whole_float_length_is_accepted(self, tmp_path: Path) -> None:
        defs = write_definitions(
            tmp_path, {"m": message("int32[N / 2]", constants="N: 8")}
        )

        parser, _ = parse_definitions(defs)

        field = parser.message_defs["M"].fields[0]
        assert (field.length, field.size) == (4, 16)

    def test_negative_length_is_rejected(self, tmp_path: Path) -> None:
        defs = write_definitions(tmp_path, {"m": message("int32[-2]")})

        with pytest.raises(RTMASyntaxError, match="-2"):
            parse_definitions(defs)

    @pytest.mark.parametrize("spec", ["int32[4] junk", "int32[4]junk", "int32[4]]"])
    def test_trailing_text_is_rejected(self, tmp_path: Path, spec: str) -> None:
        defs = write_definitions(tmp_path, {"m": message(spec)})

        with pytest.raises(ParserError):
            parse_definitions(defs)

    def test_spaces_around_a_field_spec_are_accepted(self, tmp_path: Path) -> None:
        defs = write_definitions(tmp_path, {"m": message("' int32 [ 4 ] '")})

        parser, _ = parse_definitions(defs)

        field = parser.message_defs["M"].fields[0]
        assert (field.type_name, field.length) == ("int32", 4)


class TestConstantExpressions:
    def test_many_symbols_are_accepted(self, tmp_path: Path) -> None:
        names = [f"S{n}" for n in range(12)]
        constants = "\n".join(f"{name}: 1" for name in names)
        constants += "\nTOTAL: " + " + ".join(names)
        defs = write_definitions(
            tmp_path,
            {
                "m": f"constants:\n"
                + "".join(f"  {line}\n" for line in constants.splitlines())
            },
        )

        parser, _ = parse_definitions(defs)

        assert parser.constants["TOTAL"].value == 12

    def test_nesting_up_to_the_limit_is_accepted(self, tmp_path: Path) -> None:
        depth = pyrtma.parser.MAX_REFERENCE_DEPTH
        defs = write_definitions(
            tmp_path, {"m": message(f"int32[C{depth}]", constants=chain(depth))}
        )

        parser, _ = parse_definitions(defs)

        assert parser.message_defs["M"].fields[0].length == depth + 1

    def test_nesting_past_the_limit_is_rejected(self, tmp_path: Path) -> None:
        depth = pyrtma.parser.MAX_REFERENCE_DEPTH + 1
        defs = write_definitions(
            tmp_path, {"m": message("int32", constants=chain(depth))}
        )

        with pytest.raises(RecurisionError, match=f"C{depth}") as caught:
            parse_definitions(defs)
        # It is also a RecursionError, as the parser raised before.
        assert isinstance(caught.value, RecursionError)

    def test_self_reference_is_rejected(self, tmp_path: Path) -> None:
        defs = write_definitions(
            tmp_path, {"m": message("int32", constants="A: A + 1")}
        )

        with pytest.raises(CircularRefError, match="A"):
            parse_definitions(defs)

    def test_reference_to_a_later_constant_is_rejected(self, tmp_path: Path) -> None:
        defs = write_definitions(
            tmp_path, {"m": message("int32", constants="A: B + 1\nB: A + 1")}
        )

        with pytest.raises(ExpressionExpansionError, match="B"):
            parse_definitions(defs)

    @pytest.mark.parametrize("expression", ["1 +", "1 / 0", "(2"])
    def test_invalid_expression_raises_a_parser_error(
        self, tmp_path: Path, expression: str
    ) -> None:
        defs = write_definitions(
            tmp_path, {"m": message("int32", constants=f"A: '{expression}'")}
        )

        with pytest.raises(ExpressionExpansionError, match="A"):
            parse_definitions(defs)


POINT = """\
struct_defs:
  POINT:
    fields:
      x: double
      y: double
"""


class TestAliases:
    def test_alias_to_a_struct_in_an_imported_file(self, tmp_path: Path) -> None:
        user = """\
            imports: [a]
            aliases:
              PT: POINT
              PT2: PT
            message_defs:
              M:
                id: 7000
                fields:
                  p: PT
                  ps: PT2[3]
            """
        defs = write_definitions(tmp_path, {"a": POINT, "b": user})

        parser, _ = parse_definitions(defs)

        fields = parser.message_defs["M"].fields
        assert [(f.name, f.offset, f.size) for f in fields] == [
            ("p", 0, 16),
            ("ps", 16, 48),
        ]
        assert parser.aliases["PT2"].type_obj is parser.struct_defs["POINT"]

    def test_alias_to_a_struct_in_the_same_file(self, tmp_path: Path) -> None:
        text = """\
            aliases:
              PT: POINT
            struct_defs:
              POINT:
                fields:
                  x: double
                  y: double
              LINE:
                fields:
                  start: PT
                  end: PT
            message_defs:
              M:
                id: 7000
                fields:
                  line: LINE
                  p: PT
            """
        defs = write_definitions(tmp_path, {"m": text})

        parser, _ = parse_definitions(defs)

        assert parser.struct_defs["LINE"].size == 32
        assert parser.message_defs["M"].size == 48

    def test_struct_using_an_alias_before_its_struct_is_rejected(
        self, tmp_path: Path
    ) -> None:
        text = """\
            aliases:
              PT: POINT
            struct_defs:
              LINE:
                fields:
                  start: PT
              POINT:
                fields:
                  x: double
            """
        defs = write_definitions(tmp_path, {"m": text})

        with pytest.raises(RTMASyntaxError, match="PT"):
            parse_definitions(defs)

    def test_alias_to_an_unknown_type_is_rejected(self, tmp_path: Path) -> None:
        defs = write_definitions(tmp_path, {"m": "aliases:\n  PT: NOPE\n"})

        with pytest.raises(RTMASyntaxError, match="PT"):
            parse_definitions(defs)

    def test_alias_to_itself_is_rejected(self, tmp_path: Path) -> None:
        defs = write_definitions(tmp_path, {"m": "aliases:\n  PT: PT\n"})

        with pytest.raises(CircularRefError, match="PT"):
            parse_definitions(defs)

    def test_alias_chain_past_the_limit_is_rejected(self, tmp_path: Path) -> None:
        depth = pyrtma.parser.MAX_REFERENCE_DEPTH + 1
        lines = ["A1: int32"] + [f"A{n}: A{n - 1}" for n in range(2, depth + 1)]
        text = "aliases:\n" + "".join(f"  {line}\n" for line in lines)
        defs = write_definitions(tmp_path, {"m": text})

        with pytest.raises(RecurisionError, match=f"A{depth}"):
            parse_definitions(defs)

    def test_alias_chain_resolves_to_its_final_type(self, tmp_path: Path) -> None:
        defs = write_definitions(tmp_path, {"m": "aliases:\n  A: int32\n  B: A\n"})

        parser, _ = parse_definitions(defs)

        assert parser.aliases["B"].type_name == "int32"


class TestStringConstants:
    def test_value_is_an_escaped_literal(self, tmp_path: Path) -> None:
        text = """\
            string_constants:
              PATH: 'C:\\data\\new'
              QUOTE: 'say "hi"'
            """
        defs = write_definitions(tmp_path, {"m": text})

        parser, _ = parse_definitions(defs)

        path = parser.string_constants["PATH"]
        quote = parser.string_constants["QUOTE"]
        assert path.text == "C:\\data\\new"
        assert path.value == '"C:\\\\data\\\\new"'
        assert quote.value == '"say \\"hi\\""'
        # The literal means the same text in Python, as it does in C and JS.
        assert eval(path.value) == path.text
        assert eval(quote.value) == quote.text

    @pytest.mark.parametrize("value", ["tab\\there", "line\\nbreak", "caf\\u00e9"])
    def test_unprintable_text_is_rejected(self, tmp_path: Path, value: str) -> None:
        defs = write_definitions(
            tmp_path, {"m": f'string_constants:\n  S: "{value}"\n'}
        )

        with pytest.raises(RTMASyntaxError, match="S"):
            parse_definitions(defs)


class TestNativeTypes:
    def test_signed_char_is_a_one_byte_integer(self, tmp_path: Path) -> None:
        text = """\
            message_defs:
              M:
                id: 7000
                fields:
                  one: signed char
                  many: signed char[7]
            """
        defs = write_definitions(tmp_path, {"m": text})

        parser, _ = parse_definitions(defs)

        fields = parser.message_defs["M"].fields
        assert [(f.name, f.size, f.type_obj.format) for f in fields] == [
            ("one", 1, "b"),
            ("many", 7, "b"),
        ]


class TestIds:
    @pytest.mark.parametrize("value", [10000, 20000, 40000])
    def test_module_id_in_the_dynamic_range_is_rejected(
        self, tmp_path: Path, value: int
    ) -> None:
        defs = write_definitions(tmp_path, {"m": f"module_ids:\n  X: {value}\n"})

        with pytest.raises(RTMASyntaxError, match="9999"):
            parse_definitions(defs)

    @pytest.mark.parametrize("value", [10, 99, 200, 9999])
    def test_module_ids_in_range_are_accepted(self, tmp_path: Path, value: int) -> None:
        defs = write_definitions(tmp_path, {"m": f"module_ids:\n  X: {value}\n"})

        parser, _ = parse_definitions(defs)

        assert parser.module_ids["X"].value == value

    def test_host_id_above_max_hosts_warns(self, tmp_path: Path) -> None:
        defs = write_definitions(tmp_path, {"m": "host_ids:\n  FAR: 6\n"})

        parser, log = parse_definitions(defs)

        assert parser.host_ids["FAR"].value == 6
        assert any("FAR" in w and "MAX_HOSTS" in w for w in log.warnings)

    def test_host_id_within_max_hosts_does_not_warn(self, tmp_path: Path) -> None:
        defs = write_definitions(tmp_path, {"m": "host_ids:\n  NEAR: 5\n"})

        _, log = parse_definitions(defs)

        assert log.warnings == []


class TestCompilerOptions:
    def test_unknown_option_is_rejected(self, tmp_path: Path) -> None:
        defs = write_definitions(
            tmp_path, {"m": message("int32")}, options="IMPORT_COREDEFS: false"
        )

        with pytest.raises(RTMASyntaxError, match="IMPORT_COREDEFS"):
            parse_definitions(defs)

    def test_known_options_are_applied(self, tmp_path: Path) -> None:
        defs = write_definitions(
            tmp_path,
            {"m": message("int32")},
            options="import_coredefs: false\nauto_pad: false",
        )

        parser, _ = parse_definitions(defs)

        assert not parser.import_coredefs
        assert not parser.auto_pad
        assert "EXIT" not in parser.message_defs


class TestImports:
    def test_yml_import_warns_without_prompting(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def no_prompt(prompt: str = "") -> str:
            raise AssertionError("the parser prompted for input")

        monkeypatch.setattr("builtins.input", no_prompt)
        (tmp_path / "a.yml").write_text("constants:\n  X: 1\n", encoding="utf-8")
        user = write_definitions(tmp_path, {"b": "imports: [a]\n"})
        index = user.read_text(encoding="utf-8").replace(
            "index:\n", "index:\n  a: a.yml\n"
        )
        user.write_text(index, encoding="utf-8")

        parser, log = parse_definitions(user)

        assert parser.constants["X"].value == 1
        assert any("a.yml" in w for w in log.warnings)
