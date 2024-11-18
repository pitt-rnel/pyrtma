import pyrtma
import pyrtma.core_defs as cd
import json

from pyrtma.core_defs import ALL_MESSAGE_TYPES


def add_data_set(mod: pyrtma.Client):
    msg = cd.MDF_DATA_SET_ADD()
    msg.data_set.name = input("(data-set)->name: ")
    msg.data_set.save_path = input("(data-set)->save_path: ")
    msg.data_set.filename = input("(data-set)->filename: ")
    msg.data_set.formatter = input("(data-set)->formatter: ")

    raw = input("(data-set)->msg_type: ")
    msg_types = list(map(int, raw.split()))

    msg.data_set.msg_types[: len(msg_types)] = msg_types
    mod.send_message(msg)


def rm_data_set(mod: pyrtma.Client):
    msg = cd.MDF_DATA_SET_REMOVE()
    msg.name = input("(remove)->name: ")
    mod.send_message(msg)


def main():
    import sys

    if len(sys.argv) > 1:
        server = sys.argv[1]
    else:
        server = "127.0.0.1:7111"

    mod = pyrtma.Client()
    mod.connect(server)
    mod.subscribe(
        [
            cd.MT_DATA_SET_STATUS,
            cd.MT_DATA_LOGGER_CONFIG,
            cd.MT_DATA_LOGGER_ERROR,
        ]
    )

    metadata = {}

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
                msg = cd.MDF_DATA_SET_PAUSE()
                msg.name = args[1]
                mod.send_message(msg)
            elif cmd == "resume":
                msg = cd.MDF_DATA_SET_RESUME()
                msg.name = args[1]
                mod.send_message(msg)
            elif cmd == "start":
                msg = cd.MDF_DATA_SET_START()
                msg.name = args[1]
                mod.send_message(msg)
            elif cmd == "stop":
                msg = cd.MDF_DATA_SET_STOP()
                msg.name = args[1]
                mod.send_message(msg)
            elif cmd == "status":
                msg = cd.MDF_DATA_SET_STATUS_REQUEST()
                msg.name = args[1]
                mod.send_message(msg)
            elif cmd == "config":
                mod.send_signal(cd.MT_DATA_LOGGER_CONFIG_REQUEST)
            elif cmd == "reset":
                mod.send_signal(cd.MT_DATA_LOGGER_RESET)
            elif cmd == "help":
                help()
            elif cmd == "exit":
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
                        d = msg.data.to_dict()
                        for ds in d["data_sets"]:
                            names = []
                            for msg_type in ds["msg_types"]:
                                if msg_type < 1:
                                    continue
                                if msg_type == ALL_MESSAGE_TYPES:
                                    names.append("ALL_MESSAGE_TYPES")
                                else:
                                    names.append(pyrtma.get_msg_cls(msg_type).type_name)
                            ds["msg_types"] = names
                        d["data_sets"] = d["data_sets"][: d["num_data_sets"]]
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
    print("  * exit - close application.")
    print()


if __name__ == "__main__":
    main()
