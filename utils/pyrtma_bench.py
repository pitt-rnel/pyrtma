import sys
import time
import multiprocessing
import pyrtma
from typing import Type

# Import message defs to add to pyrtma.msg_defs map
sys.path.append("../tests/")
import test_msg_defs.test_defs as td


def get_test_msg(size: int) -> Type[pyrtma.MessageData]:
    if size == 128:
        return td.MDF_TEST_MSG_128
    elif size == 256:
        return td.MDF_TEST_MSG_256
    elif size == 512:
        return td.MDF_TEST_MSG_512
    elif size == 1024:
        return td.MDF_TEST_MSG_1024
    elif size == 2048:
        return td.MDF_TEST_MSG_2048
    elif size == 4096:
        return td.MDF_TEST_MSG_4096
    elif size == 8192:
        return td.MDF_TEST_MSG_8192
    else:
        raise RuntimeError(f"Invalid size value of {size} for TEST_MSG.")


def publisher_loop(
    pub_id=0, num_msgs=10000, msg_size=128, num_subscribers=1, server="127.0.0.1:7111"
):
    # Setup Client
    mod = pyrtma.Client()
    mod.connect(server_name=server)
    mod.send_module_ready()
    mod.subscribe([td.MT_SUBSCRIBER_READY])

    # Signal that publisher is ready
    mod.send_signal(td.MT_PUBLISHER_READY)

    print(f"Publisher [{pub_id}] waiting for subscribers ")

    # Wait for the subscribers to be ready
    num_subscribers_ready = 0
    while num_subscribers_ready < num_subscribers:
        msg = mod.read_message(timeout=-1)
        if msg is not None:
            if msg.data.type_name == "SUBSCRIBER_READY":
                num_subscribers_ready += 1

    # Create TEST message with dummy data
    test_msg_cls = get_test_msg(msg_size)
    test_msg = test_msg_cls.from_random()

    print(f"Publisher [{pub_id}] starting send loop ")

    # Send loop
    tic = time.perf_counter()
    for _ in range(num_msgs):
        mod.send_message(test_msg)
    toc = time.perf_counter()

    mod.send_signal(td.MT_PUBLISHER_DONE)

    # Stats
    dur = toc - tic
    if num_msgs > 0:
        data_rate = (
            (mod.header_cls().size + test_msg_cls.type_size) * num_msgs / 1e6 / dur
        )
        print(
            f"Publisher [{pub_id}] -> {num_msgs} messages | {int(num_msgs/dur)} messages/sec | {data_rate:0.1f} MB/sec | {dur:0.6f} sec "
        )
    else:
        print(
            f"Publisher [{pub_id}] -> {num_msgs} messages | 0 messages/sec | 0 MB/sec | {dur:0.6f} sec "
        )
    mod.disconnect()


def subscriber_loop(sub_id=0, num_msgs=100000, msg_size=128, server="127.0.0.1:7111"):
    # Setup Client
    mod = pyrtma.Client()
    mod.connect(server_name=server)
    mod.send_module_ready()

    test_msg_cls = get_test_msg(msg_size)
    mod.subscribe([test_msg_cls.type_id, td.MT_EXIT])

    print(f"Subscriber [{sub_id:d}] Ready")
    mod.send_signal(td.MT_SUBSCRIBER_READY)

    # Read Loop (Start clock after first TEST msg received)
    msg_count = 0
    tic = 0
    toc = 0.0
    test_msg_size = test_msg_cls.type_size + mod.header_cls().size
    while msg_count < num_msgs:
        msg = mod.read_message(timeout=0.100)
        if msg is not None:
            if msg.name == test_msg_cls.type_name:
                if msg_count == 0:
                    # test_msg_size = msg.msg_size
                    tic = time.perf_counter()
                toc = time.perf_counter()
                msg_count += 1
            elif msg.name == "EXIT":
                break
        if tic and (time.perf_counter() - toc) > 1:
            print(f"Subscriber [{sub_id:d}] breaking early.")
            break

    mod.send_signal(td.MT_SUBSCRIBER_DONE)

    # Stats
    dur = toc - tic
    if num_msgs > 0:
        data_rate = (test_msg_size * num_msgs) / 1e6 / dur
        if msg_count == num_msgs:
            print(
                f"Subscriber [{sub_id:d}] -> {msg_count} messages | {int((msg_count-1)/dur)} messages/sec | {data_rate:0.1f} MB/sec | {dur:0.6f} sec "
            )
        else:
            print(
                f"Subscriber [{sub_id:d}] -> {msg_count} ({int(msg_count/num_msgs *100):0d}%) messages | {int((msg_count-1)/dur)} messages/sec | {data_rate:0.1f} MB/sec | {dur:0.6f} sec "
            )
    else:
        print(
            f"Subscriber [{sub_id:d}] -> {msg_count} messages | 0 messages/sec | 0 MB/sec | {dur:0.6f} sec "
        )
    mod.disconnect()


if __name__ == "__main__":
    import argparse

    # Configuration flags for bench utility
    parser = argparse.ArgumentParser(description="RtmaClient bench test utility")
    parser.add_argument(
        "-ms",
        default=128,
        choices=[128, 256, 512, 1024, 2048, 4096, 8192],
        type=int,
        dest="msg_size",
        help="Message size in bytes.",
    )
    parser.add_argument(
        "-n", default=100000, type=int, dest="num_msgs", help="Number of messages."
    )
    parser.add_argument(
        "-np",
        default=1,
        type=int,
        dest="num_publishers",
        help="Number of concurrent publishers.",
    )
    parser.add_argument(
        "-ns",
        default=1,
        type=int,
        dest="num_subscribers",
        help="Number of concurrent subscribers.",
    )
    parser.add_argument(
        "-s",
        default="127.0.0.1:7111",
        dest="server",
        help="RTMA message manager ip address (default: 127.0.0.1:7111)",
    )
    args = parser.parse_args()

    # Main Thread RTMA client
    mod = pyrtma.Client()
    mod.connect(server_name=args.server)
    mod.send_module_ready()

    test_msg_cls = get_test_msg(args.msg_size)

    mod.subscribe(
        [
            td.MT_PUBLISHER_READY,
            td.MT_PUBLISHER_DONE,
            td.MT_SUBSCRIBER_READY,
            td.MT_SUBSCRIBER_DONE,
        ]
    )

    sys.stdout.write(f"Packet size: {args.msg_size} bytes\n")
    sys.stdout.write(f"Sending {args.num_msgs} messages...\n")
    sys.stdout.flush()

    # print("Initializing publisher processses...")
    publishers = []
    for n in range(args.num_publishers):
        publishers.append(
            multiprocessing.Process(
                target=publisher_loop,
                kwargs={
                    "pub_id": n + 1,
                    "num_msgs": int(args.num_msgs / args.num_publishers),
                    "msg_size": args.msg_size,
                    "num_subscribers": args.num_subscribers,
                    "server": args.server,
                },
            )
        )
        publishers[n].start()

    # Wait for publisher processes to be established
    publishers_ready = 0
    while publishers_ready < args.num_publishers:
        msg = mod.read_message(timeout=-1)
        if msg is not None:
            if msg.name == "PUBLISHER_READY":
                publishers_ready += 1

    # print('Waiting for subscriber processes...')
    subscribers = []
    for n in range(args.num_subscribers):
        subscribers.append(
            multiprocessing.Process(
                target=subscriber_loop,
                kwargs={
                    "sub_id": n + 1,
                    "num_msgs": args.num_msgs,
                    "msg_size": args.msg_size,
                    "server": args.server,
                },
            )
        )
        subscribers[n].start()

    # print("Starting Test...")

    # Wait for subscribers to finish
    abort_timeout = 120  # seconds
    abort_start = time.perf_counter()

    subscribers_done = 0
    publishers_done = 0
    while (subscribers_done < args.num_subscribers) or (
        publishers_done < args.num_publishers
    ):
        msg = mod.read_message(timeout=0.100)
        if msg is not None:
            if msg.name == "SUBSCRIBER_DONE":
                subscribers_done += 1
            elif msg.name == "PUBLISHER_DONE":
                publishers_done += 1

        if (time.perf_counter() - abort_start) > abort_timeout:
            mod.send_signal(td.MT_EXIT)
            sys.stdout.write("Test Timeout! Sending Exit Signal...\n")
            sys.stdout.flush()

    for publisher in publishers:
        publisher.join()

    for subscriber in subscribers:
        subscriber.join()

    mod.disconnect()
    # print('Done!')
