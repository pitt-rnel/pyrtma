"""Check that ``docs/TEST_DETAILS.md`` catalogues every test.

A test is named by its file, its class when it has one, and its function, as
in ``test_cli.py::TestHelp::test_lists_commands``. The catalogue names its
rows the same way: by the ``## test_<module>.py`` heading above them, plus
the ``### ClassName`` heading when there is one.
"""

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOGUE = ROOT / "docs" / "TEST_DETAILS.md"
_FILE_HEADING = re.compile(r"## (test_\w+\.py)\b.*")
_CLASS_HEADING = re.compile(r"### (\w+)")
_ROW = re.compile(r"\|\s*`(test_\w+)`\s*\|.*")


def _test_name(node: ast.stmt) -> str | None:
    """Return the name of a test function.

    Args:
        node: A statement from a module or class body.

    Returns:
        The name of a function or async function that starts with ``test_``,
        or None for any other statement.
    """
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    return node.name if node.name.startswith("test_") else None


def collected_tests(tests_dir: Path) -> set[str]:
    """Find the test functions that pytest would collect.

    Args:
        tests_dir: The folder holding the ``test_*.py`` files.

    Returns:
        Names like ``test_a.py::test_one`` for module-level tests and
        ``test_a.py::TestThing::test_two`` for tests in ``Test`` classes.
    """
    names: set[str] = set()
    for path in sorted(tests_dir.glob("test_*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if (name := _test_name(node)) is not None:
                names.add(f"{path.name}::{name}")
            elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
                for item in node.body:
                    if (name := _test_name(item)) is not None:
                        names.add(f"{path.name}::{node.name}::{name}")
    return names


def catalogued_tests(text: str) -> set[str]:
    """Find the tests that the catalogue lists.

    Args:
        text: The catalogue's Markdown.

    Returns:
        Names in the same form as ``collected_tests``. Rows outside a
        ``## test_<module>.py`` section aren't tests and are left out.
    """
    names: set[str] = set()
    file_name: str | None = None
    class_name: str | None = None
    for line in text.splitlines():
        line = line.strip()
        if match := _FILE_HEADING.fullmatch(line):
            file_name, class_name = match.group(1), None
        elif line.startswith("## "):
            file_name, class_name = None, None
        elif match := _CLASS_HEADING.fullmatch(line):
            class_name = match.group(1)
        elif file_name is not None and (match := _ROW.fullmatch(line)):
            parts = [file_name, class_name, match.group(1)]
            names.add("::".join(part for part in parts if part is not None))
    return names


def test_every_test_is_catalogued() -> None:
    collected = collected_tests(ROOT / "tests")
    catalogued = catalogued_tests(CATALOGUE.read_text(encoding="utf-8"))

    missing = sorted(collected - catalogued)
    stale = sorted(catalogued - collected)

    problems = [f"not in {CATALOGUE.name}: {name}" for name in missing]
    problems += [f"in {CATALOGUE.name} but not a test: {name}" for name in stale]
    assert not problems, "\n".join(problems)


def test_catalogue_names_follow_headings() -> None:
    text = "\n".join(
        [
            "# Catalogue",
            "| Test | Purpose | Approach |",
            "| `test_outside` | Not in a test file's section. | - |",
            "## test_a.py — things (needs: none)",
            "| Test | Purpose | Approach |",
            "|---|---|---|",
            "| `test_one` | A module-level test. | - |",
            "### TestThing",
            "| `test_two` | A test in a class. | - |",
            "## Notes",
            "| `test_three` | Not in a test file's section. | - |",
        ]
    )

    names = catalogued_tests(text)

    assert names == {"test_a.py::test_one", "test_a.py::TestThing::test_two"}


def test_collected_tests_include_class_methods(tmp_path: Path) -> None:
    source = "\n".join(
        [
            "def helper(): pass",
            "def test_one(): pass",
            "async def test_async(): pass",
            "class TestThing:",
            "    def test_two(self): pass",
            "    def helper(self): pass",
            "class Helper:",
            "    def test_not_collected(self): pass",
        ]
    )
    (tmp_path / "test_a.py").write_text(source + "\n", encoding="utf-8")
    (tmp_path / "helpers.py").write_text("def test_elsewhere(): pass\n", "utf-8")

    names = collected_tests(tmp_path)

    assert names == {
        "test_a.py::test_one",
        "test_a.py::test_async",
        "test_a.py::TestThing::test_two",
    }
