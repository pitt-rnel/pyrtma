import ctypes
from json import JSONEncoder
from typing import Any

from ._core import MessageData


class RTMAJSONEncoder(JSONEncoder):
    """JSONEncoder object used to convert MessageData to json

    Example:
        data = json.dumps(msg, cls=pyrtma.encoding.RTMAJSONEncoder)
    """

    def default(self, o: Any) -> Any:

        if isinstance(o, MessageData):
            return {k: o.__getattribute__(k) for k, _ in o.__getattribute__("_fields_")}

        if isinstance(o, ctypes.Array):
            return list(o)

        # Object is a MessageData type
        return super().default(o)
