import json

import pyrtma.core_defs as cd
from pyrtma.data_logger.data_logger_client import DataLoggerClient, DataSetConfig


def add_dataset(mod: DataLoggerClient):
    name = input("(dataset)->name: ")
    save_path = input("(dataset)->save_path: ")
    filename = input("(dataset)->filename: ")
    formatter = input("(dataset)->formatter: ")

    raw = input("(dataset)->msg_type: ")
    if raw.lower() in ("all", "*"):
        msg_types = [cd.ALL_MESSAGE_TYPES]
    else:
        msg_types = list(map(int, raw.split()))

    config = DataSetConfig(
        name=name,
        save_path=save_path,
        filename=filename,
        formatter=formatter,
        msg_types=msg_types,
    )
    config.add(mod)


def main():
    import sys

    if len(sys.argv) > 1:
        server = sys.argv[1]
    else:
        server = "127.0.0.1:7111"

    mod = DataLoggerClient()
    mod.connect(server)

    try:
        while True:
            cmd_str = input("(data_log)>> ")
            args = cmd_str.split()
            nargs = len(args)
            cmd = args[0].lower()
            if cmd in ("add", "a") and nargs == 1:
                add_dataset(mod)
            elif cmd in ("remove", "d") and nargs == 2:
                mod.rm_dataset(args[1])
            elif cmd in ("start", "s") and nargs == 2:
                mod.start_dataset(args[1])
            elif cmd in ("start-all", "sa") and nargs == 1:
                mod.start_all_datasets()
            elif cmd in ("stop", "x") and nargs == 2:
                mod.stop_dataset(args[1])
            elif cmd in ("stop-all", "xa") and nargs == 1:
                mod.stop_all_datasets()
            elif cmd in ("pause", "p") and nargs == 2:
                mod.pause_dataset(args[1])
            elif cmd in ("pause-all", "pa") and nargs == 1:
                mod.pause_all_datasets()
            elif cmd in ("resume", "r") and nargs == 2:
                mod.resume_dataset(args[1])
            elif cmd in ("resume-all", "ra") and nargs == 1:
                mod.resume_all_datasets()
            elif cmd in ("status", "=") and nargs == 2:
                mod.request_dataset_status(args[1])
            elif cmd in ("status-all", "=a") and nargs == 1:
                mod.request_all_dataset_status()
            elif cmd in ("config", "c") and nargs == 1:
                mod.request_data_logger_config()
            elif cmd in ("reset", "<") and nargs == 1:
                mod.reset_data_logger()
            elif cmd in ("kill", "k") and nargs == 1:
                mod.send_signal(cd.MT_LM_EXIT)
            elif cmd in ("exit", "quit", "q"):
                break
            elif cmd in ("help", "?", "h"):
                help()
            else:
                print(f"Unknown command: {cmd_str}")
                help()

            while True:
                msg = mod.read_message(0.200)
                if msg:
                    if isinstance(msg.data, cd.MDF_DATA_LOGGER_ERROR):
                        print(msg.data.msg)
                    elif isinstance(msg.data, cd.MDF_DATASET_STATUS):
                        print(msg.data.to_json())
                    elif isinstance(msg.data, cd.MDF_DATA_LOGGER_CONFIG):
                        d = mod.process_data_logger_config_msg(msg.data)
                        print(json.dumps(d, indent=2))
                else:
                    break

    except KeyboardInterrupt:
        pass

    print("Goodbye")


def help():
    print("data_logger_control:")
    print("  * add/a - Add a dataset.")
    print("  * remove/d NAME - Remove dataset NAME")
    print("  * start/s NAME - Start dataset NAME")
    print("  * start-all/sa - Start all datasets")
    print("  * stop/x NAME - Stop dataset NAME")
    print("  * stop-all/xa - Stop all datasets")
    print("  * pause/p NAME - Pause dataset NAME")
    print("  * pause-all/pa - Pause all datasets")
    print("  * resume/r NAME - Resume dataset NAME")
    print("  * resume-all/ra - Resume all datasets")
    print("  * status/= NAME - Get status of dataset NAME")
    print("  * status-all/=a - Get status of all datasets")
    print("  * config/c - Get data_logger config")
    print("  * reset/< - Reset data_logger")
    print("  * kill/k - Close data_logger")
    print("  * help/h/? - print this help")
    print("  * exit/quit/q - close application.")
    print()


if __name__ == "__main__":
    main()
