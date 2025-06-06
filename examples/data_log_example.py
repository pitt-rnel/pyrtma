import time
import pyrtma
import pathlib
import pyrtma.core_defs as cd
from pyrtma.data_logger.dataset import Dataset


def main(trial_num: int, count: int):
    # Reset the DataLogger for a clean start
    mod = pyrtma.Client()
    mod.connect()
    mod.send_signal(cd.MT_DATA_LOGGER_RESET)

    # Add Datasets to the DataLogger
    base_path = pathlib.Path.home() / "data_logger"

    datasets: list[Dataset] = list()

    # JSONFormatter
    jsonf_ds = Dataset(
        name="json",
        save_path=base_path / f"trial_{trial_num:04d}" / "json",
        filename=f"trial_{trial_num:04d}",
        formatter="json",
        msg_types=[cd.MT_DATA_LOG_TEST_2048],
        subdivide_interval=30,
    )
    datasets.append(jsonf_ds)

    # MsgHeaderFormatter
    headersf_ds = Dataset(
        name="headers",
        save_path=str(base_path / f"trial_{trial_num:04d}" / "headers"),
        filename=f"trial_{trial_num:04d}",
        formatter="msg_header",
        msg_types=[cd.MT_DATA_LOG_TEST_2048],
        subdivide_interval=0,
    )
    datasets.append(headersf_ds)

    # QLFormatter
    qlf_ds = Dataset(
        name="quicklogger",
        save_path=str(base_path / f"trial_{trial_num:04d}" / "quicklogger"),
        filename=f"trial_{trial_num:04d}",
        formatter="quicklogger",
        msg_types=[cd.MT_DATA_LOG_TEST_2048],
    )
    datasets.append(qlf_ds)

    # RawFormatter (Alternative binary format [Header->Data->Header->Data])
    # rawf_ds = Dataset(
    #     name="raw",
    #     save_path=str(base_path / f"trial_{trial_num:04d}" / "raw"),
    #     filename=f"trial_{trial_num:04d}",
    #     formatter="raw",
    #     msg_types=[cd.MT_DATA_LOG_TEST_2048]
    # )
    # datasets.append(raw_ds)

    # Start all the data sets
    input("Hit enter to start the data sets...")
    for ds in datasets:
        ds.start()

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
        for ds in datasets:
            ds.stop()

    print("Done")


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Usage: data_logger_example [trial_num] [num_packets]")
        sys.exit(1)

    trial_num = int(sys.argv[1])
    count = int(sys.argv[2])  # -1: Continuous

    main(trial_num, count)
