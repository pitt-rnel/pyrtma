"""The message definition compilers and the layouts they are built from.

``compiled_layouts_snapshot.json`` records, for the core, test and example
definitions, every message's ID and every message's and struct's type hash,
size and field layout, as the parser computed them before Phase 8. Every
target's generated code follows these, so a change to them would break
existing clients and recordings. Fix the change; never edit the snapshot to
make it pass.
"""

from __future__ import annotations

import ctypes
import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import pytest

import pyrtma.compile
import pyrtma.compilers.python
from pyrtma.compilers.python import PyDefCompiler
from pyrtma.loader import load_message_definitions
from pyrtma.parser import (
    MDF,
    SDF,
    Field,
    GeneratedSourceError,
    NativeType,
    Parser,
    TypeAlias,
)

from .helpers import parse_definitions, quiet_parser

REPO = Path(__file__).resolve().parents[1]
SNAPSHOT_PATH = Path(__file__).with_name("compiled_layouts_snapshot.json")

# The compiler index files whose layouts the snapshot records.
DEFINITIONS = {
    "core": REPO / "src" / "pyrtma" / "core_defs" / "rtma.defs",
    "test": REPO / "tests" / "test_msg_defs" / "test_defs.yaml",
    "examples": REPO / "examples" / "msg_defs" / "example.defs",
}


def field_type(field: Field) -> str:
    """Describe a field's type as the layout resolves it.

    Args:
        field: A parsed field.

    Returns:
        The native type or struct name that the field's type resolves to,
        followed by ``[length]`` for arrays.
    """
    type_obj: Any = field.type_obj
    if isinstance(type_obj, TypeAlias):
        type_obj = type_obj.type_obj
    if isinstance(type_obj, NativeType):
        name = type_obj.name
    else:
        name = type_obj.name
    return f"{name}[{field.length}]" if field.length else name


def describe(definition: MDF | SDF) -> dict[str, Any]:
    """Describe one parsed definition for the snapshot.

    Args:
        definition: A parsed message or struct.

    Returns:
        Its hash, size and layout, and its ID for a message.
    """
    entry: dict[str, Any] = {}
    if isinstance(definition, MDF):
        entry["id"] = definition.type_id
    entry["hash"] = f"0x{definition.hash[:8].upper()}"
    entry["size"] = definition.size
    entry["layout"] = " ".join(
        f"{f.name}:{field_type(f)}@{f.offset}" for f in definition.fields
    )
    return entry


def parsed_layouts(parser: Parser) -> dict[str, Any]:
    """Describe every struct and message a parser holds.

    Args:
        parser: A parser that has parsed a compiler index.

    Returns:
        ``structs`` and ``messages``, each a dictionary by name.
    """
    return {
        "structs": {n: describe(s) for n, s in sorted(parser.struct_defs.items())},
        "messages": {n: describe(m) for n, m in sorted(parser.message_defs.items())},
    }


def current_layouts() -> dict[str, Any]:
    """Describe the layouts of every set of definitions in the snapshot.

    Returns:
        A dictionary shaped like the snapshot file, without its note.
    """
    return {
        name: parsed_layouts(parse_definitions(path)[0])
        for name, path in DEFINITIONS.items()
    }


def differences(
    expected: dict[str, Any], actual: dict[str, Any], section: str
) -> list[str]:
    """List the entries of one section that differ.

    Args:
        expected: The section from the snapshot.
        actual: The same section as parsed now.
        section: The section's name, used in the messages.

    Returns:
        One line per added, removed, or changed entry; empty when they match.
    """
    lines: list[str] = []
    for name in sorted(expected.keys() | actual.keys()):
        if name not in actual:
            lines.append(f"{section}: {name} was removed")
        elif name not in expected:
            lines.append(f"{section}: {name} was added")
        elif expected[name] != actual[name]:
            lines.append(
                f"{section}: {name} changed\n"
                f"  snapshot: {expected[name]}\n"
                f"  current:  {actual[name]}"
            )
    return lines


@pytest.mark.parametrize("definitions", sorted(DEFINITIONS))
def test_definitions_keep_their_layouts(definitions: str) -> None:
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))[definitions]

    current = parsed_layouts(parse_definitions(DEFINITIONS[definitions])[0])

    lines = differences(snapshot["structs"], current["structs"], "structs")
    lines += differences(snapshot["messages"], current["messages"], "messages")
    assert not lines, "\n".join(lines)


# Compiler output. Each test compiles into tmp_path with pyrtma.compile.compile,
# which prints a line for each target.

FIXTURE = REPO / "tests" / "compiler_defs" / "compiler_defs.defs"
CORE_FOR_C = REPO / "tests" / "compiler_defs" / "core_c.defs"
TEST_DEFS = DEFINITIONS["test"]

# The compiled definitions each target is checked with: the fixture, which
# exercises aliases, struct arrays and escaped strings, and the test
# definitions.
TARGET_DEFINITIONS = {"fixture": FIXTURE, "test": TEST_DEFS}

requires_gcc = pytest.mark.skipif(
    shutil.which("gcc") is None, reason="gcc is not on PATH"
)
requires_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is not on PATH"
)


def compile_defs(defs_file: Path, out_dir: Path, name: str, **targets: bool) -> Path:
    """Compile definitions into a folder.

    Args:
        defs_file: The compiler index to compile.
        out_dir: The output folder.
        name: The output files' base name.
        **targets: The targets to build, as `pyrtma.compile.compile` takes
            them, such as ``python=True``.

    Returns:
        The output folder.
    """
    pyrtma.compile.compile([str(defs_file)], str(out_dir), name, **targets)
    return out_dir


def fixture_parser() -> Parser:
    """The fixture definitions, parsed.

    Returns:
        A parser holding them.
    """
    return parse_definitions(FIXTURE)[0]


def run_node(script: str, cwd: Path) -> Any:
    """Run a JavaScript module with node and parse what it prints as JSON.

    Args:
        script: The module's source.
        cwd: The folder to run it in.

    Returns:
        The parsed output.
    """
    path = cwd / "check.mjs"
    path.write_text(script, encoding="utf-8")
    result = subprocess.run(
        ["node", str(path)], cwd=cwd, capture_output=True, text=True, timeout=30
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


class TestPython:
    @pytest.mark.parametrize("definitions", sorted(TARGET_DEFINITIONS))
    def test_classes_match_the_parser(self, tmp_path: Path, definitions: str) -> None:
        parser = parse_definitions(TARGET_DEFINITIONS[definitions])[0]
        compile_defs(TARGET_DEFINITIONS[definitions], tmp_path, "out", python=True)

        defs = load_message_definitions(tmp_path / "out.py")

        for name, mdf in parser.message_defs.items():
            cls = defs.MDF[name]
            assert (ctypes.sizeof(cls), cls.type_size) == (mdf.size, mdf.size), name
            assert cls.type_hash == int(mdf.hash[:8], 16), name
        for name, sdf in parser.struct_defs.items():
            assert ctypes.sizeof(defs.SDF[name]) == sdf.size, name

    def test_struct_aliases_name_their_struct(self, tmp_path: Path) -> None:
        compile_defs(FIXTURE, tmp_path, "out", python=True)

        defs = load_message_definitions(tmp_path / "out.py")

        assert defs.SDF["PT"] is defs.SDF["POINT"]
        assert defs.SDF["PTS"] is defs.SDF["POINT"]
        assert defs.SDF["LINE_ALIAS"] is defs.SDF["LINE"]

    def test_string_constants_keep_their_text(self, tmp_path: Path) -> None:
        compile_defs(FIXTURE, tmp_path, "out", python=True)

        defs = load_message_definitions(tmp_path / "out.py")

        assert defs.constants["PATH"] == "C:\\data\\new"
        assert defs.constants["QUOTE"] == 'say "hi"'

    def test_type_def_is_the_definition_text(self, tmp_path: Path) -> None:
        parser = fixture_parser()
        compile_defs(FIXTURE, tmp_path, "out", python=True)

        defs = load_message_definitions(tmp_path / "out.py")

        assert defs.MDF["SHAPES"].type_def == parser.message_defs["SHAPES"].raw
        assert defs.SDF["POINT"].type_def == parser.struct_defs["POINT"].raw

    def test_invalid_output_raises_and_writes_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def broken(self: PyDefCompiler, c: Any) -> str:
            return f"{c.name}: int = = 1\n"

        monkeypatch.setattr(PyDefCompiler, "generate_constant", broken)

        with pytest.raises(GeneratedSourceError, match="out.py"):
            compile_defs(FIXTURE, tmp_path, "out", python=True)
        assert not (tmp_path / "out.py").exists()

    def test_formatter_failure_warns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def failing_black(args: list[str], **kwargs: Any) -> Any:
            return subprocess.CompletedProcess(args, 123, "", "error: cannot format")

        monkeypatch.setattr(pyrtma.compilers.python.subprocess, "run", failing_black)
        parser, log = quiet_parser()
        parser.parse(FIXTURE)
        out = tmp_path / "out.py"

        PyDefCompiler(parser).generate(out)

        assert any("cannot format" in w and "out.py" in w for w in log.warnings)
        assert load_message_definitions(out).MDF["SHAPES"].type_size == 272


@pytest.mark.toolchain
@requires_gcc
class TestC:
    @pytest.mark.parametrize("definitions", sorted(TARGET_DEFINITIONS))
    def test_header_compiles_with_the_parser_layouts(
        self, tmp_path: Path, definitions: str
    ) -> None:
        compile_defs(CORE_FOR_C, tmp_path, "core", c_lang=True)
        compile_defs(TARGET_DEFINITIONS[definitions], tmp_path, "defs", c_lang=True)
        core = parse_definitions(CORE_FOR_C)[0]
        user = parse_definitions(TARGET_DEFINITIONS[definitions])[0]
        lines = ["#include <stddef.h>", '#include "core.h"', '#include "defs.h"']
        # The layouts the header must have, checked at compile time.
        for parser in (core, user):
            for prefix, table in (
                ("", parser.struct_defs),
                ("MDF_", parser.message_defs),
            ):
                for name, d in table.items():
                    if not d.fields:
                        continue  # a signal has no struct
                    lines.append(
                        f'_Static_assert(sizeof({prefix}{name}) == {d.size}, "{name}");'
                    )
                    for f in d.fields:
                        lines.append(
                            f'_Static_assert(offsetof({prefix}{name}, {f.name}) == {f.offset}, "{name}.{f.name}");'
                        )
        for c in user.string_constants.values():
            lines.append(
                f'_Static_assert(sizeof({c.name}) == {len(c.text) + 1}, "{c.name}");'
            )
        source = tmp_path / "check.c"
        source.write_text("\n".join(lines) + "\n", encoding="utf-8")

        result = subprocess.run(
            ["gcc", "-fsyntax-only", "-std=c11", "-Wall", "-Werror", str(source)],
            cwd=tmp_path,
            capture_output=True,
            text=True,
        )

        assert result.returncode == 0, result.stderr


@pytest.mark.toolchain
@requires_node
class TestJavaScript:
    @pytest.mark.parametrize("definitions", sorted(TARGET_DEFINITIONS))
    def test_every_definition_constructs(
        self, tmp_path: Path, definitions: str
    ) -> None:
        parser = parse_definitions(TARGET_DEFINITIONS[definitions])[0]
        compile_defs(TARGET_DEFINITIONS[definitions], tmp_path, "defs", javascript=True)
        # Copied to .mjs, so node loads it as the ES module it is.
        shutil.copy(tmp_path / "defs.js", tmp_path / "defs.mjs")
        script = """\
            import { RTMA } from "./defs.mjs";
            const out = { errors: {}, fields: {} };
            for (const kind of ["SDF", "MDF"]) {
              for (const [name, make] of Object.entries(RTMA[kind])) {
                try {
                  out.fields[`${kind}.${name}`] = Object.keys(make());
                } catch (e) {
                  out.errors[`${kind}.${name}`] = String(e);
                }
              }
            }
            console.log(JSON.stringify(out));
            """

        out = run_node(textwrap.dedent(script), tmp_path)

        assert out["errors"] == {}
        expected = {
            f"SDF.{n}": [f.name for f in s.fields]
            for n, s in parser.struct_defs.items()
        }
        expected.update(
            {
                f"MDF.{n}": [f.name for f in m.fields]
                for n, m in parser.message_defs.items()
            }
        )
        assert out["fields"] == expected

    def test_field_values_are_distinct_and_typed(self, tmp_path: Path) -> None:
        compile_defs(FIXTURE, tmp_path, "defs", javascript=True)
        shutil.copy(tmp_path / "defs.js", tmp_path / "defs.mjs")
        script = """\
            import { RTMA } from "./defs.mjs";
            const m = RTMA.MDF.SHAPES();
            const n = RTMA.MDF.NESTED();
            m.lines[0].start.x = 1;
            m.pts[0].x = 2;
            n.many[0].count = 3;
            console.log(JSON.stringify({
              lines: m.lines.map((l) => l.start.x),
              pts: m.pts.map((p) => p.x),
              many: n.many.map((s) => s.count),
              fresh: RTMA.MDF.SHAPES().line !== m.line,
              count: m.count,
              src: m.src,
              name: m.name,
              smalls: m.smalls,
              corners: m.polygon.corners.length,
              path: RTMA.constants.PATH,
              quote: RTMA.constants.QUOTE,
            }));
            """

        out = run_node(textwrap.dedent(script), tmp_path)

        assert out == {
            "lines": [1, 0],
            "pts": [2, 0, 0],
            "many": [3, 0],
            "fresh": True,
            "count": 0,
            "src": 0,
            "name": "",
            "smalls": [0, 0, 0],
            "corners": 3,
            "path": "C:\\data\\new",
            "quote": 'say "hi"',
        }


class TestMatlab:
    def test_struct_aliases_follow_their_struct(self, tmp_path: Path) -> None:
        compile_defs(FIXTURE, tmp_path, "defs", matlab=True)

        lines = (tmp_path / "defs.m").read_text(encoding="utf-8").splitlines()

        def last(prefix: str) -> int:
            return max(i for i, line in enumerate(lines) if line.startswith(prefix))

        assert last("RTMA.typedefs.PT = RTMA.typedefs.POINT;") > last(
            "RTMA.typedefs.POINT."
        )
        assert last("RTMA.typedefs.PTS = RTMA.typedefs.POINT;") > last(
            "RTMA.typedefs.POINT."
        )
        assert last("RTMA.typedefs.LINE_ALIAS = RTMA.typedefs.LINE;") > last(
            "RTMA.typedefs.LINE."
        )
        # Each alias is defined before the first definition that uses it.
        assert last("RTMA.typedefs.PT = ") < min(
            i for i, line in enumerate(lines) if "= RTMA.typedefs.PT;" in line
        )

    def test_string_constants_are_escaped(self, tmp_path: Path) -> None:
        compile_defs(FIXTURE, tmp_path, "defs", matlab=True)

        text = (tmp_path / "defs.m").read_text(encoding="utf-8")

        # MATLAB doubles a quote inside a string, and takes backslashes as is.
        assert 'RTMA.defines.PATH = "C:\\data\\new";\n' in text
        assert 'RTMA.defines.QUOTE = "say ""hi""";\n' in text


class TestCombined:
    @pytest.mark.parametrize("definitions", sorted(TARGET_DEFINITIONS))
    def test_combined_output_reads_back(self, tmp_path: Path, definitions: str) -> None:
        original = parsed_layouts(parse_definitions(TARGET_DEFINITIONS[definitions])[0])
        compile_defs(TARGET_DEFINITIONS[definitions], tmp_path, "all", combined=True)

        parser, _ = parse_definitions(tmp_path / "all_combined.defs")

        assert parsed_layouts(parser) == original

    def test_combined_yaml_has_only_definitions_sections(self, tmp_path: Path) -> None:
        compile_defs(FIXTURE, tmp_path, "all", combined=True)

        text = (tmp_path / "all_combined.yaml").read_text(encoding="utf-8")

        assert "compiler_options" not in text
        assert "RESERVED_007200" not in text  # kept as _RESERVED_ entries
        parser, _ = parse_definitions(tmp_path / "all_combined.defs")
        reserved = sorted(n for n in parser.message_defs if n.startswith("RESERVED_"))
        assert reserved == ["RESERVED_007200", "RESERVED_007201", "RESERVED_007202"]


class TestCompileCommand:
    def test_missing_output_folder_is_created(self, tmp_path: Path) -> None:
        out = tmp_path / "new"

        compile_defs(FIXTURE, out, "out", python=True)

        assert (out / "out.py").is_file()

    def test_output_path_that_is_a_file_is_rejected(self, tmp_path: Path) -> None:
        out = tmp_path / "file"
        out.write_text("", encoding="utf-8")

        with pytest.raises(FileExistsError, match="directory"):
            compile_defs(FIXTURE, out, "out", python=True)

    def test_import_leaves_the_exception_hook_alone(self) -> None:
        code = (
            "import sys; hook = sys.excepthook; import pyrtma.compile; "
            "print(sys.excepthook is hook)"
        )

        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True, timeout=60
        )

        assert result.stdout.strip() == "True", result.stderr
