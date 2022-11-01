import sys
import ctypes

sys.path.append("../")

import pyrtma

# Choose a unique message type id number
MT_USER_MESSAGE = 1234

# Create a user defined message from a ctypes.Structure or basic ctypes
@pyrtma.msg_def
class USER_MESSAGE(pyrtma.MessageData):
    _fields_ = [
        ("str", ctypes.c_byte * 64),
        ("val", ctypes.c_double),
        ("arr", ctypes.c_int * 8),
    ]

    type_id: int = MT_USER_MESSAGE
    type_name: str = "USER_MESSAGE"


def publisher(server="127.0.0.1:7111", timecode=False):
    # Setup Client
    mod = pyrtma.Client(timecode=timecode)
    mod.connect(server_name=server)

    # Build a packet to send
    msg = USER_MESSAGE()
    py_string = b"Hello World"
    msg.str[: len(py_string)] = py_string
    msg.val = 123.456
    msg.arr[:] = list(range(8))

    while True:
        c = input("Hit enter to publish a message. (Q)uit.")

        if c not in ["Q", "q"]:
            mod.send_message(msg)
            print("Sent a packet")
        else:
            mod.send_signal(pyrtma.MT_EXIT)
            print("Goodbye")
            break


def subscriber(server="127.0.0.1:7111", timecode=False):
    # Setup Client
    mod = pyrtma.Client(timecode=timecode)
    mod.connect(server_name=server)

    # Select the messages to receive
    mod.subscribe([MT_USER_MESSAGE, pyrtma.MT_EXIT])

    print("Waiting for packets...")
    while True:
        try:
            msg = mod.read_message(timeout=0.200)

            if msg is not None:
                if msg.name == "USER_MESSAGE":
                    msg.data.hexdump()
                    print("")
                    print(msg.pretty_print())
                elif msg.name == "EXIT":
                    print("Goodbye.")
                    break
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--server", default="127.0.0.1:7111", help="RTMA Message Manager ip address."
    )
    parser.add_argument(
        "-t", "--timecode", action="store_true", help="Use timecode in message header"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--pub", default=False, action="store_true", help="Run as publisher."
    )
    group.add_argument(
        "--sub", default=False, action="store_true", help="Run as subscriber."
    )

    args = parser.parse_args()

    if args.pub:
        print("pyrtma Publisher")
        publisher(args.server, timecode=args.timecode)
    elif args.sub:
        print("pyrtma Subscriber")
        subscriber(args.server, timecode=args.timecode)
    else:
        print("Unknown input")
