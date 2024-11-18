import time
import pyrtma
import pathlib
import pyrtma.core_defs as cd


def main(trial_num: int, count: int):
    mod = pyrtma.Client()
    mod.connect()

    mod.send_signal(cd.MT_DATA_LOGGER_RESET)

    # Add DataSets to the DataLogger
    base_path = pathlib.Path.home() / "data_logger"

    # JSONFormatter
    msg = cd.MDF_DATA_SET_ADD()
    msg.data_set.name = "json"
    msg.data_set.save_path = str(base_path / f"trial_{trial_num:04d}" / "json")
    msg.data_set.filename = f"trial_{trial_num:04d}"
    msg.data_set.formatter = "json"
    msg.data_set.msg_types[0] = cd.MT_DATA_LOG_TEST_2048
    msg.data_set.subdivide_interval = 30
    mod.send_message(msg)

    # MsgHeaderFormatter
    msg = cd.MDF_DATA_SET_ADD()
    msg.data_set.name = "headers"
    msg.data_set.save_path = str(base_path / f"trial_{trial_num:04d}" / "headers")
    msg.data_set.filename = f"trial_{trial_num:04d}"
    msg.data_set.formatter = "msg_header"
    msg.data_set.msg_types[0] = cd.MT_DATA_LOG_TEST_2048
    msg.data_set.subdivide_interval = 0
    mod.send_message(msg)

    # QLFormatter
    msg = cd.MDF_DATA_SET_ADD()
    msg.data_set.name = "quicklogger"
    msg.data_set.save_path = str(base_path / f"trial_{trial_num:04d}" / "quicklogger")
    msg.data_set.filename = f"trial_{trial_num:04d}"
    msg.data_set.formatter = "quicklogger"
    msg.data_set.msg_types[0] = cd.MT_DATA_LOG_TEST_2048
    mod.send_message(msg)

    # RawFormatter (Alternative binary format [Header->Data->Header->Data])
    # msg = cd.MDF_DATA_SET_ADD()
    # msg.data_set.name = "raw"
    # msg.data_set.save_path = str(base_path / f"trial_{trial_num:04d}" / "raw")
    # msg.data_set.filename = f"trial_{trial_num:04d}"
    # msg.data_set.formatter = "raw"
    # msg.data_set.msg_types[0] = cd.MT_DATA_LOG_TEST_2048
    # mod.send_message(msg)

    # Start all the data sets
    input("Hit enter to start the data sets...")
    msg = cd.MDF_DATA_SET_START()
    msg.name = "*"  # Use a '*' or 'all' to signal all data sets
    mod.send_message(msg)

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
            msg = cd.MDF_DATA_SET_STOP()
            msg.name = "*"
            mod.send_message(msg)

    print("Done")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: data_logger_example [trial_num] [num_packets]")
        sys.exit(1)

    trial_num = int(sys.argv[1])
    count = int(sys.argv[2])  # -1: Continuous

    main(trial_num, count)
