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
