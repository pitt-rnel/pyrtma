import copy
import itertools
import logging
import logging.handlers
import pyrtma.core_defs as cd
import pathlib
import weakref

from .message import MessageData
from abc import ABC, abstractmethod
from .exceptions import ClientError, LoggingConfigurationError

from contextlib import contextmanager
import traceback
from rich.logging import RichHandler
from rich.markup import escape


class ClientLike(ABC):
    """Abstract base class for ClientLike classes such as Client and MessageManager

    Alternative to typing.Protocol for older python versions"""

    @property
    @abstractmethod
    def connected(self) -> bool: ...

    @property
    @abstractmethod
    def logger(self) -> "RTMALogger": ...

    @abstractmethod
    def send_message(
        self,
        msg_data: MessageData,
        dest_mod_id: int = 0,
        dest_host_id: int = 0,
        timeout: float = -1,
    ) -> None: ...


# TODO after dropping support for py3.7, switch to Protocol and remove abstract base class from Client and MessageManager
# class ClientLike(Protocol):
#     def send_message(
#         self,
#         msg_data: MessageData,
#         dest_mod_id: int = 0,
#         dest_host_id: int = 0,
#         timeout: float = -1,
#     ) -> None: ...

#     @property
#     def connected(self) -> bool: ...

#     @property
#     def logger(self) -> "RTMALogger": ...


# Each RTMALogger gets its own logger name. Names built from id() were reused
# after garbage collection, and logging never frees a logger, so a new client
# inherited an old client's handlers.
_logger_ids = itertools.count(1)

#: Prefix of the names of the loggers that RTMALogger creates.
LOGGER_NAME_PREFIX: str = "pyrtma.logger"

TRUNCATED_MARKER: str = "[TRUNCATED]"
PATH_ELLIPSIS: str = "..."


def _ascii_field(
    text: str, size: int, *, marker: str = "", keep_end: bool = False
) -> str:
    """Make text fit a char field of an RTMA log message.

    Characters that aren't ASCII become "?", one for one, so the wire format
    and the field size are unchanged. Text that is still too long is cut to
    ``size - 1`` characters, leaving room for the null terminator.

    Args:
        text: The text to store.
        size: The size of the char field, including the null terminator.
        marker: Text that shows a cut: appended when the start is kept,
            prepended when the end is kept.
        keep_end: Keep the end of the text instead of the start, as for a
            path, whose file name is at the end.

    Returns:
        ASCII text of at most ``size - 1`` characters.
    """
    text = text.encode("ascii", "replace").decode("ascii")
    limit = size - 1
    if len(text) <= limit:
        return text
    room = limit - len(marker)
    if keep_end:
        return marker + text[len(text) - room :]
    return text[:room] + marker


def _field_size(msg: object, field: str) -> int:
    """Return the size in bytes of a message's char field.

    Args:
        msg: The message.
        field: The field name.

    Returns:
        The field's size, including the null terminator.
    """
    # The ctypes field behind each descriptor is the name with a leading "_".
    return getattr(type(msg), f"_{field}").size


RTMA_LOG_MSG = (
    cd.MDF_RTMA_LOG
    | cd.MDF_RTMA_LOG_DEBUG
    | cd.MDF_RTMA_LOG_INFO
    | cd.MDF_RTMA_LOG_WARNING
    | cd.MDF_RTMA_LOG_ERROR
    | cd.MDF_RTMA_LOG_CRITICAL
)


class RTMALogHandler(logging.Handler):
    """Logging handler class that writes logs as rtma messages"""

    log_map: dict[int, type[RTMA_LOG_MSG]] = {
        10: cd.MDF_RTMA_LOG_DEBUG,
        20: cd.MDF_RTMA_LOG_INFO,
        30: cd.MDF_RTMA_LOG_WARNING,
        40: cd.MDF_RTMA_LOG_ERROR,
        50: cd.MDF_RTMA_LOG_CRITICAL,
    }

    def __init__(self, client_ref: "weakref.ReferenceType[ClientLike]"):
        logging.Handler.__init__(self)
        self.client_ref = client_ref

    def close(self):
        logging.Handler.close(self)

    def get_log_msg_cls(self, level) -> type[RTMA_LOG_MSG]:
        return RTMALogHandler.log_map.get(level) or cd.MDF_RTMA_LOG

    def gen_log_msg(self, record: logging.LogRecord) -> RTMA_LOG_MSG:
        # See https://docs.python.org/3/library/logging.html#logrecord-attributes
        # for LogRecord attributes that could be added
        msg = self.get_log_msg_cls(record.levelno)()
        name = str(getattr(record, "log_name", record.name))
        msg.name = _ascii_field(name, _field_size(msg, "name"))
        msg.time = record.created
        msg.level = record.levelno
        msg.lineno = record.lineno
        msg.pathname = _ascii_field(
            str(record.pathname),
            _field_size(msg, "pathname"),
            marker=PATH_ELLIPSIS,
            keep_end=True,
        )
        msg.funcname = _ascii_field(str(record.funcName), _field_size(msg, "funcname"))
        msg.message = _ascii_field(
            record.getMessage(), cd.MAX_LOG_LENGTH, marker=TRUNCATED_MARKER
        )
        return msg

    def emit(self, record: logging.LogRecord) -> None:
        """Send a record to the message manager as an RTMA log message.

        Nothing is sent while the client is disconnected. A record whose send
        fails with a ``ClientError``, such as ``ConnectionLost``, is dropped;
        the client marks itself disconnected, and sending resumes when it
        reconnects. Other errors are reported by ``handleError``. Neither
        changes ``RTMALogger.enable_rtma``, which only the user sets.

        Args:
            record: The record to send.
        """
        client = self.client_ref()
        if client is None or not client.connected:
            return
        try:
            msg = self.gen_log_msg(record)
            client.send_message(msg)
        except ClientError:
            return
        except Exception:
            self.handleError(record)


class RichLogFormatter(logging.Formatter):
    """Custom Formatter that calls rich.markup.escape on record.msg so
    that rich formatting can be applied to formatting ONLY
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format a copy of the record with its message text escaped.

        The record itself is shared with the logger's other handlers, so it
        is left unchanged. The message is escaped after its arguments are
        merged, so markup in the arguments is escaped too.

        Args:
            record: The record to format.

        Returns:
            The formatted text.
        """
        escaped = copy.copy(record)
        escaped.msg = escape(record.getMessage())
        escaped.args = None
        return super().format(escaped)


class RtmaLogFilter(logging.Filter):

    def __init__(self, log_name: str):
        self.log_name = log_name

    def filter(self, record: logging.LogRecord):
        record.log_name = self.log_name
        return True


class RTMALogger(object):
    def __init__(
        self,
        log_name: str,
        rtma_client: ClientLike,
        level: int = logging.INFO,
    ):
        # default formatter
        self._default_fmt = "{levelname:<8} - {asctime} - {log_name:<16} - {message} - {funcName}:{lineno}"
        self._rich_fmt = "[bold yellow]{log_name:<16}[/]   {message}"
        self._default_formatter: logging.Formatter | None = logging.Formatter(
            self._default_fmt, style="{"
        )
        self._console_formatter: logging.Formatter | None = RichLogFormatter(
            self._rich_fmt, style="{"
        )
        self._file_formatter: logging.Formatter | None = self._default_formatter

        # initialize private attributes
        self._log_name = log_name
        self.children: list[logging.Logger] = []
        self._logger = logging.getLogger(f"{LOGGER_NAME_PREFIX}.{next(_logger_ids)}")
        self._logger.propagate = True
        self.set_all_levels(level)
        self._filter = RtmaLogFilter(self._log_name)
        self._logger.addFilter(self._filter)
        self._rtma_client_ref = weakref.ref(rtma_client)
        self._rtma_handler: RTMALogHandler | None = self.init_rtma_handler()
        self._file_handler: logging.FileHandler | None = None
        self._console_handler: logging.Handler | None = self.init_console_handler()

        # default values for which handlers will be enabled
        if self._rtma_handler:
            self._logger.addHandler(self._rtma_handler)
        self._enable_rtma = self._rtma_handler is not None

        if self._console_handler:
            self._logger.addHandler(self._console_handler)
        self._enable_console = self._console_formatter is not None

        self._enable_file = False
        self._log_filename: str | pathlib.Path = ""

        # alias logger methods
        self.debug = self.logger.debug
        self.info = self.logger.info
        self.warning = self.logger.warning
        self.warn = self.logger.warn
        self.error = self.logger.error
        self.exception = self.logger.exception
        self.critical = self.logger.critical

        # Release the handlers when the client is garbage collected. The
        # finalizer holds this logger, not the client. At interpreter exit,
        # logging.shutdown() flushes and closes the handlers instead.
        self._finalizer = weakref.finalize(rtma_client, self.close)
        self._finalizer.atexit = False

    def close(self) -> None:
        """Remove and close this logger's handlers.

        Called when the client is garbage collected, and safe to call more
        than once. Records logged afterwards reach only handlers further up
        the logger hierarchy. A closed logger isn't meant to be used again.
        """
        handlers = [self._rtma_handler, self._console_handler, self._file_handler]
        for handler in handlers:
            if handler is not None:
                self._logger.removeHandler(handler)
                handler.close()
        self._file_handler = None
        self._enable_rtma = False
        self._enable_console = False
        self._enable_file = False

    @property
    def logger(self) -> logging.Logger:  # read only
        return self._logger

    @property
    def log_name(self) -> str:  # read only
        return self._log_name  # self.logger.name #

    @log_name.setter
    def log_name(self, log_name: str):
        old_name = self._log_name
        self._log_name = log_name
        self._filter.log_name = log_name
        for child in self.children:
            for filter in child.filters:
                if isinstance(filter, RtmaLogFilter):
                    filter.log_name = filter.log_name.replace(old_name, log_name, 1)

    @property
    def console_handler(self) -> logging.Handler | None:  # read only
        if self._enable_console:
            for handler in self._logger.handlers:
                if handler is self._console_handler:
                    return self._console_handler
        return None

    @property
    def rtma_handler(self) -> RTMALogHandler | None:  # read only
        if self._enable_rtma:
            for handler in self._logger.handlers:
                if handler is self._rtma_handler:
                    return self._rtma_handler
        return None

    @property
    def file_handler(self) -> logging.FileHandler | None:  # read only
        if self._enable_file and self._file_handler is not None:
            for handler in self._logger.handlers:
                if handler is self._file_handler:
                    return self._file_handler
        return None

    @property
    def enable_console(self) -> bool:
        return self._enable_console

    @enable_console.setter
    def enable_console(self, value: bool):
        if self._enable_console != bool(value):  # value changed
            # Use the handler itself: the console_handler property is None
            # while the console is disabled.
            if self._console_handler:
                if bool(value):
                    # add handler
                    self.logger.addHandler(self._console_handler)
                else:
                    # disable handler
                    self.logger.removeHandler(self._console_handler)
            self._enable_console = bool(value)

    @property
    def enable_rtma(self) -> bool:
        return self._enable_rtma

    @enable_rtma.setter
    def enable_rtma(self, value: bool):
        if self._enable_rtma != bool(value):  # value changed
            if self._rtma_handler:
                if bool(value):
                    # add handler
                    self.logger.addHandler(self._rtma_handler)
                else:
                    # disable handler
                    self.logger.removeHandler(self._rtma_handler)
            self._enable_rtma = bool(value)

    @property
    def enable_file(self) -> bool:
        return self._enable_file

    @enable_file.setter
    def enable_file(self, value: bool):
        if self._enable_file != bool(value):  # value changed
            if bool(value):
                if self._file_handler:
                    self.logger.removeHandler(self._file_handler)
                    self._file_handler = None

                # add handler
                self._file_handler = self.init_file_handler()
                self.logger.addHandler(self._file_handler)
            else:
                # disable handler
                if self._file_handler:
                    self.logger.removeHandler(self._file_handler)
                    self._file_handler = None

            self._enable_file = bool(value)

    @property
    def level(self) -> int:
        return self.logger.getEffectiveLevel()

    @level.setter
    def level(self, value: int):
        self._logger.setLevel(value)

    @property
    def min_handler_level(self) -> int:
        """Minimum level of all handlers"""
        mlevel = None
        for h in self.logger.handlers:
            if h.level:
                mlevel = min(mlevel, h.level) if mlevel else h.level
        return mlevel if mlevel else 0

    def add_child(self, child_name: str) -> logging.Logger:
        child_logger = self._logger.getChild(child_name)
        child_logger.setLevel(self.level)
        full_child_name = f"{self.log_name}.{child_name}"
        filter = RtmaLogFilter(full_child_name)
        child_logger.addFilter(filter)
        self.children.append(child_logger)
        return child_logger

    def set_all_levels(self, value: int):
        """Set the log level as well as the level for each handler"""
        # set main level
        self.level = value
        # set all handlers
        for handler in self._logger.handlers:
            handler.setLevel(value)

        # set private values
        self._console_level = value
        self._rtma_level = value
        self._file_level = value

        # set child levels
        for child in self.children:
            if value < child.getEffectiveLevel():
                child.setLevel(value)

    @property
    def log_filename(self) -> str | pathlib.Path:
        if self.file_handler:
            return self.file_handler.baseFilename
        else:
            return self._log_filename

    @log_filename.setter
    def log_filename(self, value: str | pathlib.Path):
        if self.file_handler:
            raise LoggingConfigurationError(
                "Filename cannot be changed after file handler is initialized"
            )
        self._log_filename = value

    @property
    def console_level(self) -> int:
        if self.console_handler:
            self._console_level = self.console_handler.level
        return self._console_level

    @console_level.setter
    def console_level(self, value: int):
        if self.console_handler:
            self.console_handler.setLevel(value)
        self._console_level = value
        if value < self.level:
            self.level = value

    @property
    def rtma_level(self) -> int:
        if self.rtma_handler:
            self._rtma_level = self.rtma_handler.level
        return self._rtma_level

    @rtma_level.setter
    def rtma_level(self, value: int):
        if self.rtma_handler:
            self.rtma_handler.setLevel(value)
        self._rtma_level = value
        if value < self.level:
            self.level = value

    @property
    def file_level(self) -> int:
        if self.file_handler:
            self._file_level = self.file_handler.level
        return self._file_level

    @file_level.setter
    def file_level(self, value: int):
        if self.file_handler:
            self.file_handler.setLevel(value)
        self._file_level = value
        if value < self.level:
            self.level = value

    @property
    def console_formatter(self) -> logging.Formatter | None:
        if self.console_handler:
            self._console_formatter = self.console_handler.formatter
        return self._console_formatter

    @console_formatter.setter
    def console_formatter(self, value: logging.Formatter | None):
        if self.console_handler:
            self.console_handler.setFormatter(value)
        self._console_formatter = value

    @property
    def file_formatter(self) -> logging.Formatter | None:
        if self.file_handler:
            self._file_formatter = self.file_handler.formatter
        return self._file_formatter

    @file_formatter.setter
    def file_formatter(self, value: logging.Formatter | None):
        if self._file_handler:
            self._file_handler.setFormatter(value)
        self._file_formatter = value

    def init_console_handler(self) -> logging.Handler:
        # set markup to True if console formatter is RichLogFormatter
        # This will allow rich markup in the format string but NOT in each log message text (for compatibility with other handlers)
        console_handler = RichHandler(
            log_time_format="[%X.%f]",
            markup=isinstance(self._console_formatter, RichLogFormatter),
        )
        console_handler.name = "Console Handler"
        console_handler.setLevel(self._console_level)
        console_handler.setFormatter(self._console_formatter)

        return console_handler

    def init_rtma_handler(self):
        rtma_handler = RTMALogHandler(self._rtma_client_ref)
        rtma_handler.name = "RTMA Handler"
        rtma_handler.setLevel(self._rtma_level)

        return rtma_handler

    def init_file_handler(self) -> logging.FileHandler:
        file_handler = logging.handlers.RotatingFileHandler(
            self._log_filename, maxBytes=3 * (1024**2), backupCount=3
        )
        file_handler.name = "File Handler"
        file_handler.setLevel(self._file_level)
        file_handler.setFormatter(self._file_formatter)

        return file_handler

    @contextmanager
    def exception_logging_context(self):
        try:
            yield
        except Exception as e:
            e_str = str(e)
            e_type = type(e).__name__
            tb = traceback.extract_tb(e.__traceback__)
            tb_line = tb[1].lineno
            tb_fcn_name = tb[1].name
            tb_pathname = tb[1].filename
            tb_filename = pathlib.Path(tb_pathname).name
            if tb_fcn_name != "<module>":
                tb_fcn_name += "()"

            if e.__traceback__:
                exc_info = (type(e), e, e.__traceback__.tb_next)
            else:
                exc_info = (type(e), e, e.__traceback__)

            # there does not appear to be a (simple) way to point the log record to the line raising the exception
            # but exc_info prints it
            self.exception(
                f"{e_type}: {e_str} -- Unhandled exception in {tb_fcn_name} {tb_filename}:{tb_line}",
                exc_info=exc_info,
            )
            raise

    def __repr__(self):
        level = logging.getLevelName(self.logger.getEffectiveLevel())
        return "<%s %s (%s)>" % (self.__class__.__name__, self.log_name, level)
