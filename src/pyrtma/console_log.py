import pyrtma
import pyrtma.core_defs as cd
import logging
from pyrtma.exceptions import MessageManagerNotFound


def color(COLOR: str):
    return "\033[0;" + COLOR + "m"


def bold(COLOR: str):
    return "\033[1;" + COLOR + "m"


BLACK = color("30")
RED = color("31")
GREEN = color("32")
YELLOW = color("33")
BLUE = color("34")
PURPLE = color("35")
CYAN = color("36")
WHITE = color("37")
RESET = "\033[0m"


def add_color(color: str, text: str) -> str:
    color = color.lower()
    if color == "black":
        return BLACK + text + RESET
    elif color == "red":
        return RED + text + RESET
    elif color == "green":
        return GREEN + text + RESET
    elif color == "yellow":
        return YELLOW + text + RESET
    elif color == "blue":
        return BLUE + text + RESET
    elif color == "purple":
        return PURPLE + text + RESET
    elif color == "cyan":
        return CYAN + text + RESET
    elif color == "white":
        return WHITE + text + RESET
    else:
        return text


def main(server: str, log_level: int):
    level_map = dict(TRACE=0, DEBUG=10, INFO=20, WARNING=30, ERROR=40, CRITICAL=50)
    level_name = {v: k for k, v in level_map.items()}
    color_map = dict(
        TRACE="WHITE",
        DEBUG="GREEN",
        INFO="WHITE",
        WARNING="YELLOW",
        ERROR="RED",
        CRITICAL="PURPLE",
    )

    try:
        while True:
            try:
                with pyrtma.client_context(
                    0, server_name=server, name="log_console", allow_multiple=True
                ) as c:
                    c.logger.enable_console = False
                    c.logger.enable_rtma = False

                    msg_list = []

                    if log_level <= logging.DEBUG:
                        msg_list.append(cd.MT_RTMA_LOG_DEBUG)

                    if log_level <= logging.INFO:
                        msg_list.append(cd.MT_RTMA_LOG_INFO)

                    if log_level <= logging.WARNING:
                        msg_list.append(cd.MT_RTMA_LOG_WARNING)

                    if log_level <= logging.ERROR:
                        msg_list.append(cd.MT_RTMA_LOG_ERROR)

                    if log_level <= logging.CRITICAL:
                        msg_list.append(cd.MT_RTMA_LOG_CRITICAL)

                    c.subscribe(msg_list)

                    while True:
                        msg = c.read_message(timeout=0.100)
                        if msg and msg.type_id in msg_list:
                            level = level_name.get(msg.data.level) or f"LEVEL({level})"
                            level_color = color_map[level]
                            print(
                                add_color(
                                    level_color,
                                    f"{level:<8} - {msg.data.time:.3f} - {msg.data.name:<16} - {msg.data.message}",
                                )
                            )
            except MessageManagerNotFound:
                continue

    except KeyboardInterrupt:
        pass


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
        choices=["DEBUG", "INFO", "WARN", "ERROR"],
        default="INFO",
        help="Logging Level",
    )

    args = parser.parse_args()

    server_name = f"{args.addr}:{args.port}"
    log_level = logging.getLevelNamesMapping().get(args.log_level) or logging.INFO
    main(server_name, log_level)
