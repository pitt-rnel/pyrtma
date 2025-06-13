def main():
    """Main function for starting base Data Logger"""
    import argparse
    import pathlib
    import sys
    import importlib
    import logging
    from ..exceptions import ConnectionLost, MessageManagerNotFound
    from .data_logger import DataLogger

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
        help="Path to python message definitions file. Required argument.",
    )

    parser.add_argument(
        "--log-level",
        dest="log_level",
        choices=["DEBUG", "INFO", "WARN", "ERROR"],
        default="INFO",
        help="Logging Level (defaults to INFO)",
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

    if args.defs_file:
        base = pathlib.Path(args.defs_file).absolute().parent
        fname = pathlib.Path(args.defs_file).stem

        sys.path.insert(0, (str(base.absolute())))
        importlib.import_module(fname)

    d = DataLogger(args.mm_ip, log_level=level)

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
