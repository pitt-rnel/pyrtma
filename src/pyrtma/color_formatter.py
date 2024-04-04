import logging


class ColorFormatter(logging.Formatter):
    def __init__(self, template: str, *args, **kwargs):
        BLACK = "30"
        RED = "31"
        GREEN = "32"
        YELLOW = "33"
        BLUE = "34"
        PURPLE = "35"
        CYAN = "36"
        WHITE = "37"

        RESET = "\033[0m"

        def color(COLOR: str):
            return "\033[0;" + COLOR + "m"

        def bold(COLOR: str):
            return "\033[1;" + COLOR + "m"

        self.template = template
        self.FORMATS = {
            logging.DEBUG: color(GREEN) + template + RESET,
            logging.INFO: color(WHITE) + template + RESET,
            logging.WARNING: color(YELLOW) + template + RESET,
            logging.ERROR: color(RED) + template + RESET,
            logging.CRITICAL: color(PURPLE) + template + RESET,
        }
        super().__init__(*args, **kwargs)

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt or self.template, style="%")
        return formatter.format(record)
