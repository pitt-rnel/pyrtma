"""
Compile User Message Defintions first:

$ python -m pyrtma.compile -i ../testing/mjvr_types.h ../testing/climber_config.h > ./examples/rnel_msg_defs.py

After compiling, import your definitions:
from rnel_msg_defs import *
"""

import sys
import time

sys.path.append("../")

import pyrtma
from rnel_msg_defs import *


def publisher(server="127.0.0.1:7111", timecode=False):
    # Setup Client
    mod = pyrtma.Client(timecode=timecode)
    mod.connect(server_name=server)

    for msg_type, msg_cls in pyrtma.msg_defs.items():
        if msg_type < 1000:
            continue

        print(msg_cls.type_name)
        mod.send_message(msg_cls())
        time.sleep(0.100)

    mod.send_signal(pyrtma.MT_EXIT)
    print("Goodbye")


def subscriber(server="127.0.0.1:7111", timecode=False):
    # Setup Client
    mod = pyrtma.Client(timecode=timecode)
    mod.connect(server_name=server)

    # Select the messages to receive
    mod.subscribe([msg_type for msg_type in pyrtma.msg_defs.keys() if msg_type > 1000])
    mod.subscribe([pyrtma.MT_EXIT])

    print("Waiting for packets...")
    while True:
        try:
            msg = mod.read_message(timeout=0.200)

            if msg is not None:
                if msg.name == "ACKNOWLEDGE":
                    pass
                elif msg.name == "EXIT":
                    print("Goodbye.")
                    break
                else:
                    print(msg.name)

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
