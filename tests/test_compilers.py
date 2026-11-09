"""The message definition compilers and the layouts they are built from.

``compiled_layouts_snapshot.json`` records, for the core, test and example
definitions, every message's ID and every message's and struct's type hash,
size and field layout, as the parser computed them before Phase 8. Every
target's generated code follows these, so a change to them would break
existing clients and recordings. Fix the change; never edit the snapshot to
make it pass.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from pyrtma.parser import MDF, SDF, Field, NativeType, Parser, TypeAlias

from .helpers import parse_definitions

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
