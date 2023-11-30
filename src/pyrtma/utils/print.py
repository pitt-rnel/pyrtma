import ctypes


def print_ctype_array(arr: ctypes.Array):
    """Expand and print ctype arrays to string

    Args:
        arr (ctypes.Array): ctype array

    Returns:
        str: string representation of ctype array
    """
    """expand and print ctype arrays"""
    max_len = 20
    arr_len = len(arr)
    str = "["
    for i in range(0, min(arr_len, max_len)):
        str += f"{arr[i]}, "
    if arr_len > max_len:
        str += "...]"
    else:
        str = str[:-2] + "]"
    return str


def hexdump(src: bytes, length=16, sep=" "):
    """Dump bytes as hex

    Args:
        src (bytes): bytes to hexdump
        length (int, optional): Row length. Defaults to 16.
        sep (str, optional): Separator for non-printable characters. Defaults to " ".
    """
    FILTER = "".join([(len(repr(chr(x))) == 3) and chr(x) or sep for x in range(256)])
    for c in range(0, len(src), length):
        chars = src[c : c + length]
        hex_ = " ".join(["{:02x}".format(x) for x in chars])
        if len(hex_) > 24:
            hex_ = "{} {}".format(hex_[:24], hex_[24:])
        printable = "".join(
            ["{}".format((x <= 127 and FILTER[x]) or sep) for x in chars]
        )
        print(
            "{0:08x}  {1:{2}s} |{3:{4}s}|".format(
                c, hex_, length * 3, printable, length
            )
        )
