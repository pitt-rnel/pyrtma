"""data_logger CLI main entry point"""


def main():
    """Main function for starting base Data Logger"""
    import argparse
    import sys
    import logging
    import pyrtma
    from ..exceptions import ConnectionLost, MessageManagerNotFound
    from .data_logger import DataLogger
    from .dataset_writer import DatasetWriter, check_write_period

    def write_period(text: str) -> float:
        try:
            return check_write_period(float(text))
        except ValueError as e:
            raise argparse.ArgumentTypeError(
                f"expected seconds greater than 0, not {text!r}"
            ) from e

    parser = argparse.ArgumentParser(description="Packet Data Logger")

    parser.add_argument(
        "-m",
        "--mm-ip",
        default="127.0.0.1:7111",
        dest="mm_ip",
        type=str,
        help="IP address of Message Manager. Defaults to 127.0.0.1:7111.",
    )

    parser.add_argument(
        "-d",
        "--defs",
        dest="defs_file",
        type=str,
        required=True,
        help="Path to python message definitions file. Required argument.",
    )

    parser.add_argument(
        "--log-level",
        dest="log_level",
        choices=["DEBUG", "INFO", "WARN", "ERROR"],
        default="INFO",
        help="Logging Level (defaults to INFO)",
    )

    parser.add_argument(
        "--fsync",
        action="store_true",
        help=(
            "Flush and fsync each dataset file after every write and before "
            "closing it, so a power loss costs at most one write period. By "
            "default the operating system decides when to write its buffers "
            "to disk."
        ),
    )

    parser.add_argument(
        "--write-period",
        dest="write_period",
        type=write_period,
        default=DatasetWriter.WRITE_PERIOD,
        metavar="SECONDS",
        help=(
            "Seconds between each dataset's writes to its file (default "
            f"{DatasetWriter.WRITE_PERIOD:g}). Messages received since the last "
            "write are lost if the logger dies or the power fails; a shorter "
            "period loses less and writes more often."
        ),
    )

    args = parser.parse_args()

    if args.log_level == "DEBUG":
        level = logging.DEBUG
    elif args.log_level == "INFO":
        level = logging.INFO
    elif args.log_level == "WARN":
        level = logging.WARN
    elif args.log_level == "ERROR":
        level = logging.ERROR
    else:
        print("Unknown log level. Using INFO instead")
        level = logging.INFO

    definitions = pyrtma.load_message_definitions(args.defs_file)

    try:
        d = DataLogger(
            args.mm_ip,
            log_level=level,
            definitions=definitions,
            fsync=args.fsync,
            write_period=args.write_period,
        )
    except MessageManagerNotFound as e:
        print(f"MessageManagerNotFound: {e}", file=sys.stderr)
        sys.exit(1)

    try:
        d.run()
    except MessageManagerNotFound as e:
        d.client.error(f"MessageManagerNotFound: {e.args[0]}")
        sys.exit(1)
    except ConnectionLost as e:
        d.client.error(f"ConnectionLost: Connection to MessageManager is broken.")
        sys.exit(1)


if __name__ == "__main__":
    main()
