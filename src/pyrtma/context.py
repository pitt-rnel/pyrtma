import sys
import copy

from functools import cache
from typing import Dict, Any
from .message_base import MessageBase
from .message_data import MessageData


def _create_context() -> Dict[str, Dict[str, Any]]:
    ctx: Dict[str, Dict[str, Any]] = dict(
        constants={}, typedefs={}, mid={}, sdf={}, mt={}, mdf={}
    )

    return ctx


_ctx = _create_context()
_ctx_copy = _ctx.copy()


def update_context(module_name: str) -> Dict[str, Dict[str, Any]]:
    mod = sys.modules[module_name]

    for k, v in mod.__dict__.items():
        if k.startswith("_"):
            continue

        if k.startswith("MT_"):
            _ctx["mt"][k[3:]] = v
        elif k.startswith("MID_"):
            _ctx["mid"][k[4:]] = v
        elif k.startswith("MDF_"):
            _ctx["mdf"][k[4:]] = v
        elif k.isupper():
            if isinstance(v, (int, float, str)):
                _ctx["constants"][k] = v
            elif v.__name__ is not k:
                _ctx["typedefs"][k] = v
            elif issubclass(v, MessageBase):
                _ctx["sdf"][k] = v
            else:
                raise ValueError(f"Unknown object in {__name__}: {k}:{v}")
        else:
            pass

    _ctx_copy = copy.deepcopy(_ctx)
    return _ctx_copy


def get_context() -> Dict[str, Dict[str, Any]]:
    return _ctx_copy


@cache
def get_core_defs() -> Dict[int, type[MessageData]]:
    mod = sys.modules["pyrtma.core_defs"]

    core_defs: Dict[int, type[MessageData]] = {}
    for k, v in mod.__dict__.items():
        if k.startswith("MDF_"):
            core_defs[v.type_id] = v
        else:
            pass

    return core_defs
