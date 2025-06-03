import pyrtma
import pyrtma.core_defs as cd
import json

from pyrtma.core_defs import ALL_MESSAGE_TYPES
from pyrtma.data_logger.data_logger_client import DataLoggerClient, DataSetConfig


def add_data_set(mod: DataLoggerClient):
    name = input("(data-set)->name: ")
    save_path = input("(data-set)->save_path: ")
    filename = input("(data-set)->filename: ")
    formatter = input("(data-set)->formatter: ")

    raw = input("(data-set)->msg_type: ")
    msg_types = list(map(int, raw.split()))

    config = DataSetConfig(
        name=name,
        save_path=save_path,
        filename=filename,
        formatter=formatter,
        msg_types=msg_types,
    )
    config.add(mod)


def rm_data_set(mod: DataLoggerClient):
    mod.rm_data_set(input("(remove)->name: "))


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
            cmd = args[0]
            if cmd == "add":
                add_data_set(mod)
            elif cmd == "remove":
                rm_data_set(mod)
            elif cmd == "pause":
                mod.pause_data_set(args[1])
            elif cmd == "pause-all":
                mod.pause_all_data_sets()
            elif cmd == "resume":
                mod.resume_data_set(args[1])
            elif cmd == "resume-all":
                mod.resume_all_data_sets()
            elif cmd == "start":
                mod.start_data_set(args[1])
            elif cmd == "start-all":
                mod.start_all_data_sets()
            elif cmd == "stop":
                mod.stop_data_set(args[1])
            elif cmd == "stop-all":
                mod.stop_all_data_sets()
            elif cmd == "status":
                mod.request_data_set_status(args[1])
            elif cmd == "status-all":
                mod.request_all_data_set_status()
            elif cmd == "config":
                mod.request_data_logger_config()
            elif cmd == "reset":
                mod.reset_data_logger()
            elif cmd in ("help", "?", "h"):
                help()
            elif cmd in ("exit", "quit", "q"):
                break
            else:
                print(f"Unknown command: {cmd}")
                help()

            while True:
                msg = mod.read_message(0.200)
                if msg:
                    if isinstance(msg.data, cd.MDF_DATA_LOGGER_ERROR):
                        print(msg.data.msg)
                    elif isinstance(msg.data, cd.MDF_DATA_SET_STATUS):
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
    print("  * add - Add a data set.")
    print("  * remove - Remove a data set")
    print("  * start")
    print("  * stop")
    print("  * pause")
    print("  * resume")
    print("  * reset")
    print("  * status")
    print("  * config")
    print("  * help/h/? - print this help")
    print("  * exit/quit/q - close application.")
    print()


if __name__ == "__main__":
    main()
