import sys
import copy

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, Any, Type, Union
from .message_base import MessageBase
from .message_data import MessageData

__all__ = [
    "RTMAContext",
    "get_context",
    "message_name_from_id",
    "message_id_from_name",
    "module_name_from_id",
    "module_id_from_name",
]


@dataclass
class RTMAContext:
    constants: Dict[str, Union[int, float, str]] = field(default_factory=dict)
    typedefs: Dict[str, Any] = field(default_factory=dict)
    MID: Dict[str, int] = field(default_factory=dict)
    MON: Dict[int, str] = field(default_factory=dict)
    SDF: Dict[str, Type[MessageBase]] = field(default_factory=dict)
    MT: Dict[str, int] = field(default_factory=dict)
    MTN: Dict[int, str] = field(default_factory=dict)
    MDF: Dict[str, Type[MessageData]] = field(default_factory=dict)

    def _clear(self):
        self.constants.clear()
        self.typedefs.clear()
        self.MID.clear()
        self.MON.clear()
        self.SDF.clear()
        self.MT.clear()
        self.MTN.clear()
        self.MDF.clear()


_ctx = RTMAContext()
_ctx_copy = copy.deepcopy(_ctx)


# Note: This private function is called from within the
# compiled message_defs.py file to populate the global
# RTMAContext object stored in the module
def _update_context(module_name: str) -> RTMAContext:
    global _ctx_copy
    mod = sys.modules[module_name]

    for k, v in mod.__dict__.items():
        if k.startswith("_"):
            continue

        if k.startswith("MT_"):
            _ctx.MT[k[3:]] = v
            _ctx.MTN[v] = k[3:]
        elif k.startswith("MID_"):
            _ctx.MID[k[4:]] = v
            _ctx.MON[v] = k[4:]
        elif k.startswith("MDF_"):
            _ctx.MDF[k[4:]] = v
        elif k.isupper():
            if isinstance(v, (int, float, str)):
                _ctx.constants[k] = v
            elif v.__name__ is not k:
                _ctx.typedefs[k] = v
            elif issubclass(v, MessageBase):
                _ctx.typedefs[k] = v
            else:
                raise ValueError(f"Unknown object in {__name__}: {k}:{v}")
        else:
            pass

    _ctx_copy = copy.deepcopy(_ctx)
    return _ctx_copy


def _set_context(ctx: RTMAContext):
    global _ctx
    global _ctx_copy

    _ctx._clear()
    _ctx = ctx
    _ctx_copy = copy.deepcopy(_ctx)


def get_context() -> RTMAContext:
    return _ctx_copy


@lru_cache(maxsize=None)
def _get_core_defs() -> Dict[int, Type[MessageData]]:
    mod = sys.modules["pyrtma.core_defs"]

    core_defs: Dict[int, Type[MessageData]] = {}
    for k, v in mod.__dict__.items():
        if k.startswith("MDF_") and issubclass(v, MessageData):
            core_defs[v.type_id] = v
        else:
            pass

    return core_defs


# Helper functions to access context info indirectly
def message_name_from_id(message_id: int) -> Union[str, None]:
    """Get message name string from numeric ID

    Args:
        message_id (int): Message type ID number

    Returns:
        Union[str, None]: Message name, or None if ID does not exist
    """
    return _ctx.MTN.get(message_id)


def message_id_from_name(message_name: str) -> Union[int, None]:
    """Get message ID number from name

    Args:
        message_name (str): Message type name

    Returns:
        Union[int, None]: Message ID number, or None if name does not exist
    """
    return _ctx.MT.get(message_name)


def module_name_from_id(module_id: int) -> Union[str, None]:
    """Get module name string from numeric ID

    Args:
        module_id (int): Module ID number

    Returns:
        Union[str, None]: Module name, or None if ID does not exist
    """
    return _ctx.MON.get(module_id)


def module_id_from_name(module_name: str) -> Union[int, None]:
    """Get module ID number from name

    Args:
        module_name (str): Module ID name

    Returns:
        Union[int, None]: Module ID number, or None if name does not exist
    """
    return _ctx.MID.get(module_name)
