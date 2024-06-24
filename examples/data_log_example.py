import time
import json
import pyrtma
import pyrtma.core_defs as cd


def main(trial_num: int, count: int):
    mod = pyrtma.Client()
    mod.connect()

    mod.send_signal(cd.MT_DATA_LOGGER_RESET)

    # Add a DataCollection with a DataSet
    msg = cd.MDF_ADD_DATA_COLLECTION()
    msg.collection.name = "test"
    msg.collection.base_path = f"$(env:USERPROFILE)\\Desktop"
    msg.collection.dir_fmt = "test_$(date)"
    msg.collection.num_data_sets = 1
    msg.collection.data_sets[0].name = "QL.Data"
    msg.collection.data_sets[0].sub_dir_fmt = "trial_$(trial_num:04d)/QL"
    msg.collection.data_sets[0].file_name_fmt = f"QL.Data_trial_$(trial_num:04d)"
    msg.collection.data_sets[0].formatter = "quicklogger"
    msg.collection.data_sets[0].msg_types[0] = cd.ALL_MESSAGE_TYPES
    msg.collection.data_sets[0].subdivide_interval = 30
    mod.send_message(msg)

    # Add/Update DataSets to an existing DataCollection

    # JSONFormatter
    msg = cd.MDF_ADD_DATA_SET()
    msg.collection_name = "test"
    msg.data_set.name = "json"
    msg.data_set.sub_dir_fmt = "trial_$(trial_num:04d)/json"
    msg.data_set.file_name_fmt = f"json_trial_$(trial_num:04d)"
    msg.data_set.formatter = "json"
    msg.data_set.msg_types[0] = cd.MT_DATA_LOG_TEST_2048
    msg.data_set.subdivide_interval = 0
    mod.send_message(msg)

    # MsgHeaderFormatter
    msg = cd.MDF_ADD_DATA_SET()
    msg.collection_name = "test"
    msg.data_set.name = "headers"
    msg.data_set.sub_dir_fmt = "trial_$(trial_num:04d)/msg_headers"
    msg.data_set.file_name_fmt = f"msg_headers_trial_$(trial_num:04d)"
    msg.data_set.formatter = "msg_header"
    msg.data_set.msg_types[0] = cd.MT_DATA_LOG_TEST_2048
    msg.data_set.subdivide_interval = 0
    mod.send_message(msg)

    # RawFormatter
    msg = cd.MDF_ADD_DATA_SET()
    msg.collection_name = "test"
    msg.data_set.name = "raw"
    msg.data_set.sub_dir_fmt = "trial_$(trial_num:04d)/raw"
    msg.data_set.file_name_fmt = f"raw_trial_$(trial_num:04d)"
    msg.data_set.formatter = "raw"
    msg.data_set.msg_types[0] = cd.MT_DATA_LOG_TEST_2048
    mod.send_message(msg)

    # Send the metadata for trial_num
    msg = cd.MDF_DATA_LOGGER_METADATA_UPDATE()
    meta = dict(trial_num=trial_num)
    msg.json = json.dumps(meta, separators=(",", ":"))
    mod.send_message(msg)

    mod.send_signal(cd.MT_DATA_LOGGER_START)
    input("Hit enter to start sending packets...")
    msg = cd.MDF_DATA_LOG_TEST_2048.from_random()
    n = 0
    try:
        if count > 0:
            print(f"Sending {count} packets...")
            for _ in range(count):
                mod.send_message(msg)
                n += 1

                tic = time.perf_counter()
                while (time.perf_counter() - tic) < 0.002:
                    pass
        else:
            while True:
                mod.send_message(msg)
                n += 1

                tic = time.perf_counter()
                while (time.perf_counter() - tic) < 0.002:
                    pass
    except KeyboardInterrupt:
        pass
    finally:
        print(f"Sent {n} packets.")
        if mod.connected:
            mod.send_signal(cd.MT_DATA_LOGGER_STOP)

    print("Done")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: data_logger_example [trial_num] [num_packets]")
        sys.exit(1)

    trial_num = int(sys.argv[1])
    count = int(sys.argv[2])  # -1: Continuous

    main(trial_num, count)
