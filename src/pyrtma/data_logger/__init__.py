import sys

if sys.version_info.major < 3:
    raise ImportError("DataLogger requires python 3.10 or greater")

if sys.version_info.minor < 10:
    raise ImportError("DataLogger requires python 3.10 or greater")

from .data_logger import DataLogger


def _load_default_formatters():
    from .formatters.quicklogger import QLFormatter
    from .formatters.raw import RawFormatter
    from .formatters.json import JsonFormatter
    from .formatters.msg_headers import MsgHeaderFormatter
    from .data_formatter import add_formatter

    # Add Builtin Formatters
    add_formatter(QLFormatter)
    add_formatter(RawFormatter)
    add_formatter(JsonFormatter)
    add_formatter(MsgHeaderFormatter)


_load_default_formatters()
