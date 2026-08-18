from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import sys
import warnings
from types import ModuleType

from .definitions import MessageDefinitions, build_message_definitions_from_module
from .exceptions import (
    MessageDefinitionsContractError,
    MessageDefinitionsLoadError,
)


def _module_name_for_path(path: pathlib.Path) -> str:
    digest = hashlib.sha1(str(path).encode("utf-8")).hexdigest()[:12]
    return f"_pyrtma_defs_{digest}"


def _load_module(path: pathlib.Path) -> ModuleType:
    module_name = _module_name_for_path(path)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise MessageDefinitionsLoadError(
            f"Unable to create import spec for message definitions file: {path}"
        )

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        raise MessageDefinitionsLoadError(
            f"Failed to import message definitions file: {path}"
        ) from e

    return module


def load_message_definitions(path: str | pathlib.Path) -> MessageDefinitions:
    """Load MessageDefinitions from a compiled definitions Python file."""

    defs_path = pathlib.Path(path).expanduser().resolve()
    if not defs_path.exists():
        raise MessageDefinitionsLoadError(
            f"Message definitions file does not exist: {defs_path}"
        )
    if not defs_path.is_file():
        raise MessageDefinitionsLoadError(
            f"Message definitions path is not a file: {defs_path}"
        )

    module = _load_module(defs_path)
    getter = getattr(module, "get_message_definitions", None)
    if getter is None or not callable(getter):
        warnings.warn(
            "Compiled message definitions module does not define get_message_definitions(); "
            "this legacy fallback is deprecated and will be removed in a future major release.",
            DeprecationWarning,
            stacklevel=2,
        )
        return build_message_definitions_from_module(module)

    defs = getter()
    if not isinstance(defs, MessageDefinitions):
        raise MessageDefinitionsContractError(
            "get_message_definitions() did not return a MessageDefinitions instance"
        )

    return defs
