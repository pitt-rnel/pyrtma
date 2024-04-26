import pyrtma
import pyrtma.core_defs as cd
import json

from pyrtma.core_defs import ALL_MESSAGE_TYPES


def add_collection(mod: pyrtma.Client):
    msg = cd.MDF_ADD_DATA_COLLECTION()
    msg.collection.name = input("(add-collection)->name: ")
    msg.collection.base_path = input("(add-collection)->base_path: ")
    msg.collection.dir_fmt = input("(add-collection)->dir_fmt: ")
    mod.send_message(msg)


def rm_collection(mod: pyrtma.Client):
    msg = cd.MDF_REMOVE_DATA_COLLECTION()
    msg.collection_name = input("(rm-collection)->name: ")
    mod.send_message(msg)


def add_data_set(mod: pyrtma.Client):
    msg = cd.MDF_ADD_DATA_SET()
    msg.collection_name = input("(add-data-set)->collection_name: ")
    msg.data_set.name = input("(add-data-set)->name: ")
    msg.data_set.sub_dir_fmt = input("(add-data-set)->sub_dir_fmt: ")
    msg.data_set.file_name_fmt = input("(add-data-set)->file_name_fmt: ")
    msg.data_set.formatter = input("(add-data-set)->formatter: ")

    ctx = cd.get_context()
    mt = []
    raw = input("(add-data-set)->msg_type: ")
    msg_types = list(map(int, raw.split()))

    for msg_type in msg_types:
        msg_type = ctx["mt"].get((raw))
        if msg_type:
            mt.append(msg_type)

    msg.data_set.msg_types[: len(mt)] = mt
    mod.send_message(msg)


def rm_data_set(mod: pyrtma.Client):
    msg = cd.MDF_REMOVE_DATA_SET()
    msg.collection_name = input("(rm-data-set)->collection_name: ")
    msg.name = input("(rm-data-set)->name: ")
    mod.send_message(msg)


def update_metadata(mod: pyrtma.Client, metadata):
    raw = input("(update-metadata)-> ")
    msg = cd.MDF_DATA_LOGGER_METADATA_UPDATE()
    msg.json = raw
    mod.send_message(msg)
    mod.send_signal(cd.MT_DATA_LOGGER_METADATA_REQUEST)


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
            cd.MT_DATA_LOGGER_STATUS,
            cd.MT_DATA_COLLECTION_CONFIG,
            cd.MT_DATA_LOGGER_METADATA,
            cd.MT_DATA_LOGGER_ERROR,
        ]
    )

    metadata = {}

    try:
        while True:
            cmd = input("(data_log)>> ")

            if cmd == "add-collection":
                add_collection(mod)
            elif cmd == "add-data-set":
                add_data_set(mod)
            elif cmd == "rm-collection":
                rm_collection(mod)
            elif cmd == "rm-data-set":
                rm_data_set(mod)
            elif cmd == "pause":
                mod.send_signal(cd.MT_DATA_LOGGER_PAUSE)
            elif cmd == "resume":
                mod.send_signal(cd.MT_DATA_LOGGER_RESUME)
            elif cmd == "reset":
                mod.send_signal(cd.MT_DATA_LOGGER_RESET)
            elif cmd == "start":
                mod.send_signal(cd.MT_DATA_LOGGER_START)
            elif cmd == "stop":
                mod.send_signal(cd.MT_DATA_LOGGER_STOP)
            elif cmd == "get-status":
                mod.send_signal(cd.MT_DATA_LOGGER_STATUS_REQUEST)
            elif cmd == "get-config":
                mod.send_signal(cd.MT_DATA_COLLECTION_CONFIG_REQUEST)
            elif cmd == "get-metadata":
                mod.send_signal(cd.MT_DATA_LOGGER_METADATA_REQUEST)
            elif cmd == "update-metadata":
                update_metadata(mod, metadata)
            elif cmd == "help":
                help()
            elif cmd == "exit":
                break
            else:
                print(f"Unknown command: {cmd}")
                help()

            msg = mod.read_message(0.200)
            if msg:
                if isinstance(msg.data, cd.MDF_DATA_LOGGER_ERROR):
                    print(msg.data.msg)
                elif isinstance(msg.data, cd.MDF_DATA_LOGGER_STATUS):
                    print(msg.data.to_json())
                elif isinstance(msg.data, cd.MDF_DATA_LOGGER_METADATA):
                    print(msg.data.json)
                    metadata = json.loads(msg.data.json)
                elif isinstance(msg.data, cd.MDF_DATA_COLLECTION_CONFIG):
                    d = msg.data.collection.to_dict()
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

    except KeyboardInterrupt:
        pass

    print("Goodbye")


def help():
    print("data_logger_control:")
    print("  * add-collection")
    print("  * add-data-set")
    print("  * rm-collection")
    print("  * rm-data-set")
    print("  * start")
    print("  * stop")
    print("  * pause")
    print("  * resume")
    print("  * reset")
    print("  * get-status")
    print("  * get-config")
    print("  * get-metadata")
    print("  * update-metadata")
    print("  * exit - close application.")
    print()


if __name__ == "__main__":
    main()
