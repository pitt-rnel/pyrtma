import sys
import ctypes

sys.path.append("../")

from pylsb import *

# Create a user defined message from a ctypes.Structure or basic ctypes
class USER_MESSAGE(ctypes.Structure):
    _fields_ = [
        ("str", ctypes.c_byte * 64),
        ("val", ctypes.c_double),
        ("arr", ctypes.c_int * 8),
    ]


# Choose a unique message type id number
MT_USER_MESSAGE = 1234

# Add the message definition to pylsb.core module internal dictionary
pylsb.internal_types.AddMessage(
    msg_name="USER_MESSAGE", msg_type=MT_USER_MESSAGE, msg_def=USER_MESSAGE
)


def publisher(server="127.0.0.1:7111", timecode=False):
    # Setup Client
    mod = Client(timecode=timecode)
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
            mod.send_signal("Exit")
            print("Goodbye")
            break


def subscriber(server="127.0.0.1:7111", timecode=False):
    # Setup Client
    mod = Client(timecode=timecode)
    mod.connect(server_name=server)

    # Select the messages to receive
    mod.subscribe(["USER_MESSAGE", "Exit"])

    print("Waiting for packets...")
    while True:
        try:
            msg = mod.read_message(timeout=0.200)

            if msg is not None:
                if msg.name == "USER_MESSAGE":
                    msg.hexdump()
                    print(msg)
                elif msg.name == "Exit":
                    print("Goodbye.")
                    break
        except KeyboardInterrupt:
            break


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--server", default="127.0.0.1:7111", help="LSB Message Manager ip address."
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
        print("pylsb Publisher")
        publisher(args.server, timecode=args.timecode)
    elif args.sub:
        print("pylsb Subscriber")
        subscriber(args.server, timecode=args.timecode)
    else:
        print("Unknown input")
