"""Run with `python -m pyrtma.unified_console_log [OPTIONS]` (use -h for help)"""

import argparse
import logging
import os
import threading
from collections.abc import Callable, Sequence
from .client import Client
from . import core_defs as cd
from .client_logging import RTMALogger
from .exceptions import ClientError, ConnectionLost
from typing import Optional, Union, cast

RTMA_LOG_MSG = Union[
    cd.MDF_RTMA_LOG,
    cd.MDF_RTMA_LOG_DEBUG,
    cd.MDF_RTMA_LOG_INFO,
    cd.MDF_RTMA_LOG_WARNING,
    cd.MDF_RTMA_LOG_ERROR,
    cd.MDF_RTMA_LOG_CRITICAL,
]


#: Log level names accepted by ``--log-level``. ``logging.getLevelNamesMapping``
#: would need Python 3.11.
LOG_LEVELS: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARN": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

DEFAULT_SERVER: str = "127.0.0.1:7111"


class RTMA_UnifiedLog(object):
    """Prints the RTMA log messages that every module sends.

    :meth:`start` runs until an ``EXIT`` message, :meth:`stop`, or
    ``KeyboardInterrupt``. While the message manager can't be reached, it
    retries with a delay that doubles after each failure, from
    ``retry_delay`` up to ``max_retry_delay``, and starts again from
    ``retry_delay`` after each successful connection.
    """

    def __init__(
        self,
        log_level: int = logging.INFO,
        server: Optional[str] = None,
        *,
        retry_delay: float = 0.5,
        max_retry_delay: float = 5.0,
        sleep: Optional[Callable[[float], object]] = None,
    ):
        """Create the unified log's client and loggers.

        Args:
            log_level: The lowest level printed.
            server: The message manager's ``host:port``. Defaults to
                ``127.0.0.1:7111``.
            retry_delay: Seconds to wait after the first failed connection.
            max_retry_delay: The longest wait between connection attempts.
            sleep: Waits between connection attempts, for tests. The default
                wait ends early when :meth:`stop` is called.
        """
        self.server = server
        self.log_level = log_level
        self._running = False
        self.retry_delay = retry_delay
        self.max_retry_delay = max_retry_delay
        self._stop_event = threading.Event()
        self._sleep = sleep if sleep is not None else self._stop_event.wait

        self.mod = Client(name="UnifiedLog_Module")
        self.local_log = self.mod.logger
        self.mod.logger.enable_rtma = False
        self.mod.logger.set_all_levels(log_level)

        # The remote logger only prints, so it shares this module's client.
        # A client of its own would be garbage collected at once, and its
        # handlers released with it.
        self.remote_log = RTMALogger(
            log_name="Remote", rtma_client=self.mod, level=log_level
        )
        self.remote_log.enable_console = True
        self.remote_log.enable_rtma = False

    def init_rtma(self) -> None:
        """Connect to the message manager and subscribe to log messages.

        Raises:
            ClientError: The connection failed, for example
                ``MessageManagerNotFound``.
            OSError: The connection failed in a way the client doesn't
                translate yet.
        """
        if self.server is None:
            self.server = DEFAULT_SERVER
        self.mod.info(f"Attempting connection to RTMA @ {self.server}")
        self.mod.connect(self.server)

        self.mod.info("Successfully connected to RTMA")
        self.rtma_subscribe()

    def rtma_subscribe(self):
        msg_list = [cd.MT_EXIT, cd.MT_RTMA_LOG]
        if self.log_level <= logging.DEBUG:
            msg_list.append(cd.MT_RTMA_LOG_DEBUG)

        if self.log_level <= logging.INFO:
            msg_list.append(cd.MT_RTMA_LOG_INFO)

        if self.log_level <= logging.WARNING:
            msg_list.append(cd.MT_RTMA_LOG_WARNING)

        if self.log_level <= logging.ERROR:
            msg_list.append(cd.MT_RTMA_LOG_ERROR)

        if self.log_level <= logging.CRITICAL:
            msg_list.append(cd.MT_RTMA_LOG_CRITICAL)

        self.mod.subscribe(msg_list)
        self.mod.info(f"Subscribed to: {msg_list}")
        self.mod.send_module_ready()

    def disconnect(self):
        if self.mod.connected:
            self.mod.info("Disconnecting from RTMA")
            self.mod.disconnect()

    def make_log_record_dict(self, msg: RTMA_LOG_MSG):
        log_dict = {
            "name": msg.name,
            "log_name": msg.name,
            "msg": msg.message,
            "levelname": logging.getLevelName(msg.level),
            "levelno": msg.level,
            "pathname": msg.pathname,
            "filename": msg.pathname,
            "lineno": msg.lineno,
            "funcName": msg.funcname,
            "created": msg.time,
            "msecs": (msg.time - int(msg.time)) * 1000,
            "relativeCreated": (msg.time - logging._startTime) * 1000,  # type: ignore
        }
        try:
            log_dict["filename"] = os.path.basename(msg.pathname)
            log_dict["module"] = os.path.splitext(log_dict["filename"])[0]
        except (TypeError, ValueError, AttributeError):
            log_dict["filename"] = msg.pathname
            log_dict["module"] = "Unknown module"

        return log_dict

    def process_log_msg(self, msg: RTMA_LOG_MSG):
        if msg.level < self.log_level:
            return
        log_dict = self.make_log_record_dict(msg)
        log_record = logging.makeLogRecord(log_dict)
        if log_record.levelno >= logging.WARNING:
            print("\a", flush=True)
        if self.remote_log.console_handler:
            self.remote_log.console_handler.emit(log_record)

    def stop(self) -> None:
        """Ask :meth:`start` to return, from another thread.

        It returns within about a second, or at once while it waits to retry.
        """
        self._running = False
        self._stop_event.set()

    def _wait_to_retry(self, delay: float) -> float:
        """Wait before the next connection attempt.

        Args:
            delay: Seconds to wait.

        Returns:
            The delay for the attempt after that.
        """
        self._sleep(delay)
        return min(delay * 2, self.max_retry_delay)

    def start(self) -> None:
        """Print log messages until ``EXIT``, :meth:`stop`, or Ctrl+C.

        Connection failures are retried with back-off; see the class
        docstring.
        """
        log_msg_ids = (
            cd.MT_RTMA_LOG,
            cd.MT_RTMA_LOG_DEBUG,
            cd.MT_RTMA_LOG_INFO,
            cd.MT_RTMA_LOG_WARNING,
            cd.MT_RTMA_LOG_ERROR,
            cd.MT_RTMA_LOG_CRITICAL,
        )
        if self.server is None:
            self.server = DEFAULT_SERVER
        self._running = True
        self._stop_event.clear()
        delay = self.retry_delay
        try:
            self.mod.info("Starting main loop")
            while self._running:
                try:
                    self.init_rtma()
                    delay = self.retry_delay
                    while self._running:
                        msg = self.mod.read_message(1)
                        if msg:
                            if msg.type_id == cd.MT_EXIT:
                                self.mod.info("Received EXIT signal")
                                self._running = False
                            elif msg.type_id in log_msg_ids:
                                msg.data = cast(RTMA_LOG_MSG, msg.data)
                                self.process_log_msg(msg.data)
                except ConnectionLost:
                    self.mod.error("RTMA Connection lost, attempting to reconnect")
                except (ClientError, OSError) as err:
                    # OSError covers connection failures that the client
                    # doesn't translate into its own exceptions yet.
                    self.mod.debug(
                        f"No connection to RTMA @ {self.server} ({err!r}); "
                        f"retrying in {delay:g} s"
                    )
                else:
                    continue
                if self._running:
                    delay = self._wait_to_retry(delay)
        except KeyboardInterrupt:
            self.mod.info("Keyboard Interrupt")
        finally:
            self.mod.disconnect()
            self.mod.info("Exiting")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse the command line.

    Args:
        argv: The arguments, without the program name. Defaults to
            ``sys.argv[1:]``.

    Returns:
        The options, with ``server`` as a ``host:port`` string and
        ``log_level`` as a ``logging`` level number.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-a",
        "--addr",
        dest="addr",
        type=str,
        default="127.0.0.1",
        help="MessageManager server IP address as a string. Default is 127.0.0.1",
    )
    parser.add_argument(
        "-p",
        "--port",
        dest="port",
        type=int,
        default=7111,
        help="Listener port. Default is 7111.",
    )
    parser.add_argument(
        "-l",
        "--log-level",
        dest="log_level",
        choices=list(LOG_LEVELS),
        default="INFO",
        help="Logging Level",
    )

    args = parser.parse_args(argv)
    args.server = f"{args.addr}:{args.port}"
    args.log_level = LOG_LEVELS[args.log_level]
    return args


def main(argv: Optional[Sequence[str]] = None) -> None:
    """Run the unified console log from the command line.

    Args:
        argv: The arguments, without the program name. Defaults to
            ``sys.argv[1:]``.
    """
    args = parse_args(argv)
    RL = RTMA_UnifiedLog(log_level=args.log_level, server=args.server)
    RL.start()


if __name__ == "__main__":
    main()
