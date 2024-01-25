import pyrtma
from pyrtma.message import get_msg_defs
import timeit
import statistics


# Import message defs to add to pyrtma.msg_defs map
from .test_msg_defs.test_defs import *


def convert_to_json(n=1000):
    stats = {}
    for mdf in get_msg_defs().values():
        # Fill the message with random data
        hdr = pyrtma.MessageHeader()
        hdr.msg_type = mdf.type_id
        data = mdf.from_random()
        msg = pyrtma.Message(hdr, data)

        # Convert to json string
        stats[mdf.type_name] = timeit.timeit(
            "json_msg = msg.to_json(minify=True)",
            number=n,
            globals={"pyrtma": pyrtma, "msg": msg},
        )

    return stats


def convert_from_json(n=1000):
    stats = {}
    for mdf in get_msg_defs().values():
        # Fill the message with random data
        hdr = pyrtma.MessageHeader()
        hdr.msg_type = mdf.type_id
        data = mdf.from_random()
        msg = pyrtma.Message(hdr, data)
        json_msg = msg.to_json(minify=True)

        # Convert to json string
        stats[mdf.type_name] = timeit.timeit(
            "msg = pyrtma.Message.from_json(json_msg)",
            number=n,
            globals={"pyrtma": pyrtma, "json_msg": json_msg},
        )

    return stats


def print_results(n, stats):
    for name, value in sorted(stats.items(), key=lambda x: x[1]):
        print(f"{name:<42}: {value/n*1000:0.3f} ms")

    vals = [v / n * 1000 for v in stats.values()]
    print(
        f"Average: {statistics.mean(vals):0.3f} +/- {statistics.stdev(vals):03f} [{min(vals):0.3f} to {max(vals):0.3f}] ms"
    )


n = 500
print("TO JSON:")
print_results(n, convert_to_json(n))
print()
print("FROM JSON:")
print_results(n, convert_from_json(n))
