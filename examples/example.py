import sys
import pathlib

sys.path.append(str(pathlib.Path(__file__).parent))

import pyrtma

# Import the users compiled message defintions
import msg_defs.message as md

from typing import cast


def publisher(server="127.0.0.1:7111", timecode=False):
    # Setup Client
    mod = pyrtma.Client(timecode=timecode)
    mod.connect(server_name=server)

    # Build a packet to send
    msg = md.MDF_PERSON_MESSAGE()
    msg.name = "Alice"
    msg.age = 37

    while True:
        c = input("Hit enter to publish a message. (Q)uit.")

        if c not in ["Q", "q"]:
            msg.age += 1
            mod.send_message(msg)
            print("Sent:")
            print(msg.to_json())
        else:
            mod.send_signal(md.MT_EXIT)
            print("Goodbye")
            break


def subscriber(server="127.0.0.1:7111", timecode=False):
    # Setup Client
    mod = pyrtma.Client(timecode=timecode)
    mod.connect(server_name=server)

    # Select the messages to receive
    mod.subscribe([md.MT_PERSON_MESSAGE, md.MT_EXIT])

    print("Waiting for packets...")
    while True:
        try:
            msg = mod.read_message(timeout=0.200)

            if msg is not None:
                if msg.type_id == md.MT_PERSON_MESSAGE:
                    # optional cast for better type hinting
                    msg.data = cast(md.MDF_PERSON_MESSAGE, msg)
                    print("Recv:")
                    print(msg.data.to_json())
                elif msg.type_id == md.MT_EXIT:
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
