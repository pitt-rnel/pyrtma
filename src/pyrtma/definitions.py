from __future__ import annotations

import sys
from dataclasses import dataclass
from types import MappingProxyType, ModuleType
from collections.abc import Iterable, Mapping
from typing import Any

from .exceptions import UnknownMessageType, MessageDefinitionsLoadError
from .message_base import MessageBase
from .message_data import MessageData


@dataclass(frozen=True)
class MessageDefinitions:
    """Immutable container for compiled message definitions and related context maps."""

    compiled_version: str | None
    msg_defs: Mapping[int, type[MessageData]]
    constants: Mapping[str, int | float | str]
    typedefs: Mapping[str, Any]
    MID: Mapping[str, int]
    MON: Mapping[int, str]
    SDF: Mapping[str, type[MessageBase]]
    MT: Mapping[str, int]
    MTN: Mapping[int, str]
    MDF: Mapping[str, type[MessageData]]

    @classmethod
    def create(
        cls,
        *,
        compiled_version: str | None,
        msg_defs: Mapping[int, type[MessageData]],
        constants: Mapping[str, int | float | str],
        typedefs: Mapping[str, Any],
        MID: Mapping[str, int],
        MON: Mapping[int, str],
        SDF: Mapping[str, type[MessageBase]],
        MT: Mapping[str, int],
        MTN: Mapping[int, str],
        MDF: Mapping[str, type[MessageData]],
    ) -> MessageDefinitions:
        """Build definitions, with read-only copies of the mappings given.

        Raises:
            MessageDefinitionsLoadError: A message class has no ``type_hash``
                or ``type_size``, as v1 definitions compiled from C headers
                don't.
        """
        _check_message_classes([*msg_defs.values(), *MDF.values()])
        return cls(
            compiled_version=compiled_version,
            msg_defs=MappingProxyType(dict(msg_defs)),
            constants=MappingProxyType(dict(constants)),
            typedefs=MappingProxyType(dict(typedefs)),
            MID=MappingProxyType(dict(MID)),
            MON=MappingProxyType(dict(MON)),
            SDF=MappingProxyType(dict(SDF)),
            MT=MappingProxyType(dict(MT)),
            MTN=MappingProxyType(dict(MTN)),
            MDF=MappingProxyType(dict(MDF)),
        )

    def get_msg_cls(self, msg_type: int) -> type[MessageData]:
        try:
            return self.msg_defs[msg_type]
        except KeyError as e:
            raise UnknownMessageType(
                f"There is no message definition associated with id: {msg_type}"
            ) from e

    def get_message_cls(self, msg_type: int) -> type[MessageData]:
        return self.get_msg_cls(msg_type)

    def message_name_from_id(self, message_id: int) -> str | None:
        return self.MTN.get(message_id)

    def message_id_from_name(self, message_name: str) -> int | None:
        return self.MT.get(message_name)

    def module_name_from_id(self, module_id: int) -> str | None:
        return self.MON.get(module_id)

    def module_id_from_name(self, module_name: str) -> int | None:
        return self.MID.get(module_name)


def _check_message_classes(classes: Iterable[type[MessageData]]) -> None:
    """Refuse message classes that lack what compiled definitions always have.

    Every class the compiler writes has a ``type_hash`` and a ``type_size``.
    Classes from v1 definitions, compiled from C headers, have neither, and
    pyrtma no longer supports them.

    Args:
        classes: The message classes, possibly with repeats.

    Raises:
        MessageDefinitionsLoadError: One or more classes lack them; the error
            names each.
    """
    missing = sorted(
        {
            msg_cls.type_name or msg_cls.__name__
            for msg_cls in classes
            if not isinstance(getattr(msg_cls, "type_hash", None), int)
            or msg_cls.type_size < 0
        }
    )
    if missing:
        raise MessageDefinitionsLoadError(
            f"Message classes without type_hash or type_size: {', '.join(missing)}. "
            "They look like v1 definitions compiled from C headers, which pyrtma "
            "no longer supports. Write the definitions in YAML and compile them "
            "with python -m pyrtma.compile."
        )


def build_message_definitions(module_name: str) -> MessageDefinitions:
    """Build MessageDefinitions from a compiled definitions module name."""

    mod = sys.modules[module_name]

    constants: dict[str, int | float | str] = {}
    typedefs: dict[str, Any] = {}
    mid: dict[str, int] = {}
    mon: dict[int, str] = {}
    sdf: dict[str, type[MessageBase]] = {}
    mt: dict[str, int] = {}
    mtn: dict[int, str] = {}
    mdf: dict[str, type[MessageData]] = {}

    for k, v in mod.__dict__.items():
        if k.startswith("_"):
            continue

        if k.startswith("MT_"):
            mt[k[3:]] = v
            mtn[v] = k[3:]
        elif k.startswith("MID_"):
            mid[k[4:]] = v
            mon[v] = k[4:]
        elif (
            k.startswith("MDF_") and isinstance(v, type) and issubclass(v, MessageData)
        ):
            mdf[k[4:]] = v
        elif isinstance(v, type) and issubclass(v, MessageBase):
            # Collect struct definitions that are not message definitions.
            if not (k.startswith("MDF_") and issubclass(v, MessageData)):
                sdf[k] = v
        elif k.isupper():
            if isinstance(v, (int, float, str)):
                constants[k] = v
            elif hasattr(v, "__name__") and v.__name__ != k:
                typedefs[k] = v

    msg_defs: dict[int, type[MessageData]] = {}
    for msg_cls in mdf.values():
        msg_defs[msg_cls.type_id] = msg_cls

    compiled_version = getattr(mod, "COMPILED_PYRTMA_VERSION", None)

    return MessageDefinitions.create(
        compiled_version=compiled_version,
        msg_defs=msg_defs,
        constants=constants,
        typedefs=typedefs,
        MID=mid,
        MON=mon,
        SDF=sdf,
        MT=mt,
        MTN=mtn,
        MDF=mdf,
    )


def build_message_definitions_from_module(module: ModuleType) -> MessageDefinitions:
    """Build MessageDefinitions from a loaded module object."""

    sys.modules[module.__name__] = module
    return build_message_definitions(module.__name__)
