"""The wire format is frozen: check it against a recorded snapshot.

``wire_format_snapshot.json`` records the message header layouts and, for every
core message and struct, its ID, type hash, size, and field layout, together
with the core module and host IDs, as they were in pyrtma 4.0.0. A failure
here means a change would break existing C, MATLAB, and JavaScript clients, or
existing recordings. Fix the change; never edit the snapshot to make it pass.

Layouts name field types by kind and size, such as ``int64``, rather than by
ctypes class, because ctypes aliases differ between platforms: ``c_int64`` is
``c_long`` on Linux and ``c_longlong`` on Windows.
"""

from __future__ import annotations

import ctypes
import json
from pathlib import Path
from typing import Any

import pytest

import pyrtma.core_defs as cd
from pyrtma.header import MessageHeader, get_header_cls

SNAPSHOT_PATH = Path(__file__).with_name("wire_format_snapshot.json")
HOST_ID_NAMES = ("LOCAL_HOST", "ALL_HOSTS")

# ctypes simple-type codes, mapped to a platform-neutral kind.
_KINDS = {
    "b": "int",
    "h": "int",
    "i": "int",
    "l": "int",
    "q": "int",
    "B": "uint",
    "H": "uint",
    "I": "uint",
    "L": "uint",
    "Q": "uint",
    "f": "float",
    "d": "float",
    "?": "bool",
}


def type_name(ctype: Any) -> str:
    """Describe a ctypes field type independently of the platform.

    Args:
        ctype: A ctypes simple type, array type, or structure type.

    Returns:
        ``int32``, ``uint16``, ``float64``, ``char``, a structure's class name,
        or an element description followed by ``[length]`` for arrays.

    Raises:
        TypeError: The type isn't one that message definitions use.
    """
    if isinstance(ctype, type) and issubclass(ctype, ctypes.Structure):
        return ctype.__name__
    if isinstance(ctype, type) and issubclass(ctype, ctypes.Array):
        return f"{type_name(ctype._type_)}[{ctype._length_}]"
    code = getattr(ctype, "_type_", None)
    if code == "c":
        return "char"
    if isinstance(code, str) and code in _KINDS:
        return f"{_KINDS[code]}{ctypes.sizeof(ctype) * 8}"
    raise TypeError(f"Unexpected field type {ctype!r}")


def layout(cls: Any) -> str:
    """Describe a structure's fields as ``name:type@offset`` entries.

    Args:
        cls: A ctypes structure class, such as a message or header class.

    Returns:
        The fields in order, base-class fields first, separated by spaces.
        Leading underscores, which the descriptors add to ctypes field names,
        are removed.
    """
    # A ctypes subclass lists only its own fields; its bases' fields come first.
    fields = [
        field
        for klass in reversed(cls.__mro__)
        for field in vars(klass).get("_fields_", [])
    ]
    entries: list[str] = []
    for field_name, ctype, *_ in fields:
        offset = getattr(cls, field_name).offset
        entries.append(f"{field_name.lstrip('_')}:{type_name(ctype)}@{offset}")
    return " ".join(entries)


def type_hash(cls: Any) -> str:
    """Format a definition's type hash as it appears in the snapshot.

    Args:
        cls: A compiled message or struct class.

    Returns:
        The hash as eight upper-case hex digits after ``0x``.
    """
    return f"0x{cls.type_hash:08X}"


def current_wire_format() -> dict[str, Any]:
    """Describe the wire format of the installed pyrtma.

    Returns:
        A dictionary with the same shape as the snapshot file.
    """
    defs = cd.get_message_definitions()
    headers: dict[str, Any] = {
        MessageHeader.__name__: {
            "size": ctypes.sizeof(MessageHeader),
            "layout": layout(MessageHeader),
        }
    }
    structs = {
        name: {
            "hash": type_hash(cls),
            "size": ctypes.sizeof(cls),
            "layout": layout(cls),
        }
        for name, cls in sorted(defs.SDF.items())
        # SDF also holds the imported base classes; keep the compiled structs.
        if cls.__module__ == cd.__name__
    }
    messages = {
        name: {
            "id": cls.type_id,
            "hash": type_hash(cls),
            "size": ctypes.sizeof(cls),
            "layout": layout(cls),
        }
        for name, cls in sorted(defs.MDF.items())
    }
    module_ids = {
        name: value
        for name, value in sorted(vars(cd).items())
        if name.startswith("MID_")
    }
    host_ids = {name: getattr(cd, name) for name in HOST_ID_NAMES}
    return {
        "headers": headers,
        "structs": structs,
        "messages": messages,
        "module_ids": module_ids,
        "host_ids": host_ids,
    }


def differences(
    section: str, expected: dict[str, Any], actual: dict[str, Any]
) -> list[str]:
    """List the entries of one snapshot section that differ.

    Args:
        section: The section's name, used in the messages.
        expected: The section from the snapshot.
        actual: The same section from the installed pyrtma.

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


@pytest.fixture(scope="module")
def snapshot() -> dict[str, Any]:
    """The recorded wire format.

    Returns:
        The parsed snapshot file.
    """
    return json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def current() -> dict[str, Any]:
    """The wire format of the installed pyrtma.

    Returns:
        The current description, shaped like the snapshot.
    """
    return current_wire_format()


def test_get_header_cls_returns_the_only_header() -> None:
    assert get_header_cls() is MessageHeader


def test_header_matches_snapshot(
    snapshot: dict[str, Any], current: dict[str, Any]
) -> None:
    assert current["headers"] == snapshot["headers"]


@pytest.mark.parametrize("section", ["structs", "messages", "module_ids", "host_ids"])
def test_core_definitions_match_snapshot(
    snapshot: dict[str, Any], current: dict[str, Any], section: str
) -> None:
    changed = differences(section, snapshot[section], current[section])

    assert not changed, "\n".join(changed)


def test_layout_names_types_by_size() -> None:
    class Sample(ctypes.Structure):
        _fields_ = [
            ("_a", ctypes.c_int64),
            ("_b", ctypes.c_longlong),
            ("_c", ctypes.c_uint32),
            ("_d", ctypes.c_char * 4),
            ("_e", ctypes.c_double * 2),
        ]

    expected = "a:int64@0 b:int64@8 c:uint32@16 d:char[4]@20 e:float64[2]@24"

    description = layout(Sample)

    assert description == expected
