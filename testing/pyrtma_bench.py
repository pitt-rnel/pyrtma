import sys
import ctypes
import time
import multiprocessing

sys.path.append("../")

from pyrtma import *


def publisher_loop(
    pub_id=0, num_msgs=10000, msg_size=128, num_subscribers=1, server="127.0.0.1:7111"
):
    # Register user defined message types
    if msg_size > 0:
        AddMessage(msg_name="TEST", msg_type=5000, msg_def=create_test_msg(msg_size))
    else:
        AddSignal(msg_name="TEST", msg_type=5000)

    AddSignal(msg_name="PUBLISHER_READY", msg_type=5001)
    AddSignal(msg_name="PUBLISHER_DONE", msg_type=5002)
    AddSignal(msg_name="SUBSCRIBER_READY", msg_type=5003)

    # Setup Client
    mod = Client()
    mod.connect(server_name=server)
    mod.send_module_ready()
    mod.subscribe("SUBSCRIBER_READY")

    # Signal that publisher is ready
    mod.send_signal("PUBLISHER_READY")

    print(f"Publisher [{pub_id}] waiting for subscribers ")

    # Wait for the subscribers to be ready
    num_subscribers_ready = 0
    while num_subscribers_ready < num_subscribers:
        msg = mod.read_message(timeout=-1)
        if msg is not None:
            if msg.msg_name == "SUBSCRIBER_READY":
                num_subscribers_ready += 1

    # Create TEST message with dummy data
    test_msg = create_test_msg(msg_size)()  # msg = pyrtma.Message("TEST")
    if msg_size > 0:
        test_msg.data[:] = list(range(msg_size))

    print(f"Publisher [{pub_id}] starting send loop ")

    # Send loop
    tic = time.perf_counter()
    for n in range(num_msgs):
        mod.send_message(test_msg)
    toc = time.perf_counter()

    mod.send_signal("PUBLISHER_DONE")

    # Stats
    dur = toc - tic
    if num_msgs > 0:
        data_rate = (
            ctypes.sizeof(mod.header_cls)
            + ctypes.sizeof(test_msg) * num_msgs / 1e6 / dur
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
    # Register user defined message types
    if msg_size > 0:
        AddMessage(msg_name="TEST", msg_type=5000, msg_def=create_test_msg(msg_size))
    else:
        AddSignal(msg_name="TEST", msg_type=5000)

    AddSignal(msg_name="SUBSCRIBER_READY", msg_type=5003)
    AddSignal(msg_name="SUBSCRIBER_DONE", msg_type=5004)

    # Setup Client
    mod = Client()
    mod.connect(server_name=server)
    mod.send_module_ready()
    mod.subscribe("TEST")
    mod.subscribe("Exit")
    print(f"Subscriber [{sub_id:d}] Ready")
    mod.send_signal("SUBSCRIBER_READY")

    # Read Loop (Start clock after first TEST msg received)
    msg_count = 0
    tic = 0
    toc = 0.0
    test_msg_size = msg_size + ctypes.sizeof(mod.header_cls)
    while msg_count < num_msgs:
        msg = mod.read_message(timeout=0.100)
        if msg is not None:
            if msg.name == "TEST":
                if msg_count == 0:
                    # test_msg_size = msg.msg_size
                    tic = time.perf_counter()
                toc = time.perf_counter()
                msg_count += 1
            elif msg.name == "Exit":
                break
        if tic and (time.perf_counter() - toc) > 1:
            print(f"Subscriber [{sub_id:d}] breaking early.")
            break

    mod.send_signal("SUBSCRIBER_DONE")

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


def create_test_msg(msg_size):
    class TEST(ctypes.Structure):
        _fields_ = [("data", ctypes.c_byte * msg_size)]

    return TEST


if __name__ == "__main__":
    import argparse

    # Configuration flags for bench utility
    parser = argparse.ArgumentParser(description="RtmaClient bench test utility")
    parser.add_argument(
        "-ms", default=128, type=int, dest="msg_size", help="Messge size in bytes."
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
    mod = Client()
    mod.connect(server_name=args.server)
    mod.send_module_ready()

    AddSignal(msg_name="PUBLISHER_READY", msg_type=5001)
    AddSignal(msg_name="PUBLISHER_DONE", msg_type=5002)
    AddSignal(msg_name="SUBSCRIBER_READY", msg_type=5003)
    AddSignal(msg_name="SUBSCRIBER_DONE", msg_type=5004)

    mod.subscribe("PUBLISHER_READY")
    mod.subscribe("PUBLISHER_DONE")
    mod.subscribe("SUBSCRIBER_READY")
    mod.subscribe("SUBSCRIBER_DONE")

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
            if msg.msg_name == "PUBLISHER_READY":
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
            if msg.msg_name == "SUBSCRIBER_DONE":
                subscribers_done += 1
            elif msg.msg_name == "PUBLISHER_DONE":
                publishers_done += 1

        if (time.perf_counter() - abort_start) > abort_timeout:
            mod.send_signal("Exit")
            sys.stdout.write("Test Timeout! Sending Exit Signal...\n")
            sys.stdout.flush()

    for publisher in publishers:
        publisher.join()

    for subscriber in subscribers:
        subscriber.join()

    mod.disconnect()
    # print('Done!')
