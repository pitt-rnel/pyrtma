import time
from pyrtma.data_logger.data_logger_client import DataLoggerClient, DataSetConfig
import pathlib
import pyrtma.core_defs as cd


def main(trial_num: int, count: int):
    mod = DataLoggerClient()
    mod.connect()

    mod.send_signal(cd.MT_DATA_LOGGER_RESET)

    # Add DataSets to the DataLogger
    base_path = pathlib.Path.home() / "data_logger"

    # JSONFormatter
    jsonf_config = DataSetConfig(
        name="json",
        save_path=base_path / f"trial_{trial_num:04d}" / "json",
        filename=f"trial_{trial_num:04d}",
        formatter="json",
        msg_types=[cd.MT_DATA_LOG_TEST_2048],
        subdivide_interval=30,
    )
    # add via client interface
    mod.add_data_set(jsonf_config)

    # MsgHeaderFormatter
    headersf_config = DataSetConfig(
        name="headers",
        save_path=str(base_path / f"trial_{trial_num:04d}" / "headers"),
        filename=f"trial_{trial_num:04d}",
        formatter="msg_header",
        msg_types=[cd.MT_DATA_LOG_TEST_2048],
        subdivide_interval=0,
    )
    # add via DataSetConfig interface
    headersf_config.register_client(mod)
    headersf_config.add()

    # QLFormatter
    qlf_config = DataSetConfig(
        name="quicklogger",
        save_path=str(base_path / f"trial_{trial_num:04d}" / "quicklogger"),
        filename=f"trial_{trial_num:04d}",
        formatter="quicklogger",
        msg_types=[cd.MT_DATA_LOG_TEST_2048],
    )
    # add via DataSetConfig interface in 1 line
    qlf_config.add(client=mod)

    # RawFormatter (Alternative binary format [Header->Data->Header->Data])
    # rawf_config = DataSetConfig(
    #     name="raw",
    #     save_path=str(base_path / f"trial_{trial_num:04d}" / "raw"),
    #     filename=f"trial_{trial_num:04d}",
    #     formatter="raw",
    #     msg_types=[cd.MT_DATA_LOG_TEST_2048]
    # )
    # rawf_config.add(client=mod)

    # Start all the data sets
    input("Hit enter to start the data sets...")
    mod.start_all_data_sets()

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
            mod.stop_all_data_sets()

    print("Done")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: data_logger_example [trial_num] [num_packets]")
        sys.exit(1)

    trial_num = int(sys.argv[1])
    count = int(sys.argv[2])  # -1: Continuous

    main(trial_num, count)
