"""Run with `python -m pyrtma.unified_console_logger [OPTIONS]` (use -h for help)"""

import logging
from .client import Client
from . import core_defs as cd
from .client_logging import RTMALogger
from typing import Optional, Union, cast
import os

RTMA_LOG_MSG = Union[
    cd.MDF_RTMA_LOG,
    cd.MDF_RTMA_LOG_DEBUG,
    cd.MDF_RTMA_LOG_INFO,
    cd.MDF_RTMA_LOG_WARNING,
    cd.MDF_RTMA_LOG_ERROR,
    cd.MDF_RTMA_LOG_CRITICAL,
]


class RTMA_UnifiedLog(object):

    def __init__(self, log_level: int = logging.INFO, server: Optional[str] = None):
        self.server = server
        self.log_level = log_level
        self._running = False

        self.mod = Client(name="UnifiedLog_Module")
        self.local_log = self.mod.logger
        self.mod.logger.enable_rtma = False
        self.mod.logger.set_all_levels(log_level)

        self.remote_log = RTMALogger(
            log_name="Remote", rtma_client=Client(), level=log_level
        )
        self.remote_log.enable_console = True
        self.remote_log.enable_rtma = False

    def init_rtma(self):
        if self.server is None:
            self.server = "127.0.0.1:7111"
        self.mod.info(f"Connecting to RTMA @ {self.server}")
        self.mod.connect(self.server)

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
        self.mod.info(f"Sucessfully connected to RTMA")

    def disconnect(self):
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

    def start(self):

        log_msg_ids = (
            cd.MT_RTMA_LOG,
            cd.MT_RTMA_LOG_DEBUG,
            cd.MT_RTMA_LOG_INFO,
            cd.MT_RTMA_LOG_WARNING,
            cd.MT_RTMA_LOG_ERROR,
            cd.MT_RTMA_LOG_CRITICAL,
        )

        self.init_rtma()
        self.mod.info("Starting main loop")
        self._running = True
        while self._running:
            msg = self.mod.read_message(1)
            if msg:
                if msg.type_id == cd.MT_EXIT:
                    self._running = False
                elif msg.type_id in log_msg_ids:
                    msg.data = cast(RTMA_LOG_MSG, msg.data)
                    self.process_log_msg(msg.data)
        self.mod.info("Exited main loop")
        self.disconnect()


if __name__ == "__main__":
    import argparse

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
    parser.add_argument("-d", "--debug", action="store_true", help="Debug mode")
    parser.add_argument(
        "--log-level",
        dest="log_level",
        choices=["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"],
        default="INFO",
        help="Logging Level",
    )

    args = parser.parse_args()

    server_name = f"{args.addr}:{args.port}"

    log_level = logging.INFO  # default
    if args.log_level:
        level = args.log_level.upper()
        if level == "DEBUG":
            log_level = logging.DEBUG
        elif level == "INFO":
            log_level = logging.INFO
        elif level in ("WARN", "WARNING"):
            log_level = logging.WARNING
        elif level == "ERROR":
            log_level = logging.ERROR
        elif level == "CRITICAL":
            log_level = logging.CRITICAL
        else:
            raise UserWarning("Unhandled log_level, defaulting to INFO")

    RL = RTMA_UnifiedLog(log_level=log_level, server=server_name)
    RL.start()
