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
        "--log-level",
        dest="log_level",
        choices=["DEBUG", "INFO", "WARN", "ERROR"],
        default="INFO",
        help="Logging Level",
    )

    args = parser.parse_args()

    log_level = logging.getLevelNamesMapping().get(args.log_level) or logging.INFO

    if args.defs_file:
        base = pathlib.Path(args.defs_file).absolute().parent
        fname = pathlib.Path(args.defs_file).stem

        sys.path.insert(0, (str(base.absolute())))
        importlib.import_module(fname)

    d = DataLogger(args.mm_ip, log_level=log_level)
    d.run()


if __name__ == "__main__":
    main()
