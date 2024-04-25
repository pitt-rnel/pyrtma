import logging
import logging.handlers
import pyrtma.core_defs as cd
import pathlib
import weakref

from .message import MessageData
from .exceptions import ClientError

from typing import Union, Type, Dict, Optional, Protocol
from rich.logging import RichHandler
from rich.markup import escape


class ClientLike(Protocol):
    def send_message(
        self,
        msg_data: MessageData,
        dest_mod_id: int = 0,
        dest_host_id: int = 0,
        timeout: float = -1,
    ) -> None: ...

    @property
    def connected(self) -> bool: ...

    @property
    def logger(self) -> "RTMALogger": ...


RTMA_LOG_MSG = Union[
    cd.MDF_RTMA_LOG,
    cd.MDF_RTMA_LOG_DEBUG,
    cd.MDF_RTMA_LOG_INFO,
    cd.MDF_RTMA_LOG_WARNING,
    cd.MDF_RTMA_LOG_ERROR,
    cd.MDF_RTMA_LOG_CRITICAL,
]


class RTMALogHandler(logging.Handler):
    """Logging handler class that writes logs as rtma messages"""

    log_map: Dict[int, Type[RTMA_LOG_MSG]] = {
        10: cd.MDF_RTMA_LOG_DEBUG,
        20: cd.MDF_RTMA_LOG_INFO,
        30: cd.MDF_RTMA_LOG_WARNING,
        40: cd.MDF_RTMA_LOG_ERROR,
        50: cd.MDF_RTMA_LOG_CRITICAL,
    }

    def __init__(self, client_ref: weakref.ReferenceType[ClientLike]):
        logging.Handler.__init__(self)
        self.client_ref = client_ref

    def close(self):
        logging.Handler.close(self)

    def get_log_msg_cls(self, level) -> Type[RTMA_LOG_MSG]:
        return RTMALogHandler.log_map.get(level) or cd.MDF_RTMA_LOG

    def gen_log_msg(self, record: logging.LogRecord) -> RTMA_LOG_MSG:
        # See https://docs.python.org/3/library/logging.html#logrecord-attributes
        # for LogRecord attributes that could be added
        msg = self.get_log_msg_cls(record.levelno)()
        msg.name = record.name
        msg.time = record.created
        msg.level = record.levelno
        msg.lineno = record.lineno
        msg.pathname = record.pathname
        msg.funcname = record.funcName
        msg.message = record.getMessage()
        return msg

    def emit(self, record: logging.LogRecord):
        client = self.client_ref()
        if client:
            try:
                if client.connected:
                    msg = self.gen_log_msg(record)
                    client.send_message(msg)
            except ClientError:
                if client:
                    client.logger.enable_rtma = False
            except Exception:
                if client:
                    client.logger.enable_rtma = False
                self.handleError(record)


class RichLogFormatter(logging.Formatter):
    """Custom Formatter that calls rich.markup.escape on record.msg so
    that rich formatting can be applied to formatting ONLY
    """

    def format(self, record: logging.LogRecord, *args):
        record.msg = escape(record.msg)
        return super().format(record, *args)


class RTMALogger(object):
    def __init__(
        self,
        log_name: str,
        rtma_client: ClientLike,
        level: int = logging.NOTSET,
    ):
        # default formatter
        self._default_fmt = "{levelname:<8} - {asctime} - {name:<16} - {message}"
        self._rich_fmt = "[bold yellow]{name:<16}[/]   {message}"
        self._default_formatter = logging.Formatter(self._default_fmt, style="{")
        self._console_formatter = RichLogFormatter(self._rich_fmt, style="{")
        self._file_formatter = self._default_formatter

        # initialize private attributes
        self._logger = logging.getLogger(hex(id(rtma_client)))
        self._logger.name = log_name
        self._logger.propagate = True
        self.level = level
        self._console_level = level
        self._rtma_level = level
        self._file_level = level
        self._rtma_client_ref = weakref.ref(rtma_client)
        self._rtma_handler = self.init_rtma_handler()
        self._file_handler = None
        self._console_handler = self.init_console_handler()

        # default values for which handlers will be enabled
        self._enable_rtma = True
        self._logger.addHandler(self._rtma_handler)

        self._enable_console = True
        self._logger.addHandler(self._console_handler)

        self._enable_file = False
        self._log_filename: Union[str, pathlib.Path] = ""

        # alias logger methods
        self.debug = self.logger.debug
        self.info = self.logger.info
        self.warning = self.logger.warning
        self.warn = self.logger.warn
        self.error = self.logger.error
        self.exception = self.logger.exception
        self.critical = self.logger.critical

    def __del__(self):
        if self._console_handler:
            self._logger.removeHandler(self._console_handler)

        if self._file_handler:
            self._logger.removeHandler(self._file_handler)
            self._file_handler = None

        if self._rtma_handler:
            self._logger.removeHandler(self._rtma_handler)

        # remove any other handlers
        for handler in self._logger.handlers:
            self._logger.removeHandler(handler)

    @property
    def logger(self) -> logging.Logger:  # read only
        return self._logger

    @property
    def log_name(self) -> str:  # read only
        return self.logger.name

    @property
    def console_handler(self) -> Optional[logging.Handler]:  # read only
        if self._enable_console:
            for handler in self._logger.handlers:
                if handler is self._console_handler:
                    return self._console_handler
        return None

    @property
    def rtma_handler(self) -> Optional[RTMALogHandler]:  # read only
        if self._enable_rtma:
            for handler in self._logger.handlers:
                if handler is self._rtma_handler:
                    return self._rtma_handler

    @property
    def file_handler(self) -> Optional[logging.FileHandler]:  # read only
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
            if self.console_handler:
                if bool(value):
                    # add handler
                    self.logger.addHandler(self.console_handler)
                else:
                    # disable handler
                    self.logger.removeHandler(self.console_handler)
            self._enable_console = bool(value)

    @property
    def enable_rtma(self) -> bool:
        return self._enable_rtma

    @enable_rtma.setter
    def enable_rtma(self, value: bool):
        if self._enable_rtma != bool(value):  # value changed
            if self.rtma_handler:
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
        return self.logger.level

    @level.setter
    def level(self, value: int):
        self._logger.setLevel(value)

    def add_child(self, child_name: str) -> logging.Logger:
        child_logger = self._logger.getChild(child_name)
        child_logger.setLevel(self.level)
        return child_logger

    def set_all_levels(self, value: int):
        """Set the log level as well as the level for each handler"""
        # set main level
        self.level = value
        # set all handlers
        for handler in self._logger.handlers:
            handler.setLevel(value)

        for child in self._logger.getChildren():
            for handler in child.handlers:
                handler.setLevel(value)

        # set private values
        self._console_level = value
        self._rtma_level = value
        self._file_level = value

    @property
    def log_filename(self) -> Union[str, pathlib.Path]:
        if self.file_handler:
            return self.file_handler.baseFilename
        else:
            return self._log_filename

    @log_filename.setter
    def log_filename(self, value: Union[str, pathlib.Path]):
        self._log_filename = value

    @property
    def console_level(self) -> int:
        if self.console_handler:
            self._console_level = self.console_handler.level
        return self._console_level

    @console_level.setter
    def console_level(self, value: int):
        if self.console_handler:
            self.console_handler.level = value
        self._console_level = value

    @property
    def rtma_level(self) -> int:
        if self.rtma_handler:
            self._rtma_level = self.rtma_handler.level
        return self._rtma_level

    @rtma_level.setter
    def rtma_level(self, value: int):
        if self.rtma_handler:
            self.rtma_handler.level = value
        self._rtma_level = value

    @property
    def file_level(self) -> int:
        if self.file_handler:
            self._file_level = self.file_handler.level
        return self._file_level

    @file_level.setter
    def file_level(self, value: int):
        if self.file_handler:
            self.file_handler.level = value
        self._file_level = value

    @property
    def console_formatter(self) -> Optional[logging.Formatter]:
        if self.console_handler:
            self._console_formatter = self.console_handler.formatter
        return self._console_formatter

    @console_formatter.setter
    def console_formatter(self, value: Optional[logging.Formatter]):
        if self.console_handler:
            self.console_handler.setFormatter(value)
        self._console_formatter = value

    @property
    def file_formatter(self) -> Optional[logging.Formatter]:
        if self.file_handler:
            self._file_formatter = self.file_handler.formatter
        return self._file_formatter

    @file_formatter.setter
    def file_formatter(self, value: Optional[logging.Formatter]):
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

    def __repr__(self):
        level = logging.getLevelName(self.logger.getEffectiveLevel())
        return "<%s %s (%s)>" % (self.__class__.__name__, self.log_name, level)
