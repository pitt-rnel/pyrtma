def main():
    """Main function for starting base Data Logger"""
    import argparse
    import pathlib
    import sys
    import importlib
    import logging
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
        "--debug",
        dest="debug",
        action="store_true",
        help="Set to debug logging mode",
    )

    args = parser.parse_args()

    if args.debug:
        DataLogger.LOG_LEVEL = logging.DEBUG
    else:
        DataLogger.LOG_LEVEL = logging.INFO

    if args.defs_file:
        base = pathlib.Path(args.defs_file).absolute().parent
        fname = pathlib.Path(args.defs_file).stem

        sys.path.insert(0, (str(base.absolute())))
        importlib.import_module(fname)

    d = DataLogger(args.mm_ip)
    d.run()


if __name__ == "__main__":
    main()
