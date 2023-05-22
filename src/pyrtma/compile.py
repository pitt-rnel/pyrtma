"""pyrtma.compile Message Type Compiler """

import pathlib
from .parser import Parser
from typing import List


def compile(include_files: List, out_filepath: str, python: bool, javascript: bool):

    parser = Parser()
    parser.parse(include_files)

    if python:
        from pyrtma.compilers.python import PyDefCompiler

        compiler = PyDefCompiler(parser)
        ext = ".py"
        p = pathlib.Path(out_filepath)
        out = p.stem + ".py"

        compiler.generate(out)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="pyrtma Message Definition Compiler.")

    parser.add_argument(
        "-i",
        "-I",
        "--include",
        nargs="*",
        dest="include_files",
        help="Files to parse",
    )
    parser.add_argument(
        "--python",
        "--py",
        dest="python",
        action="store_true",
        help="Output python file",
    )

    parser.add_argument(
        "--javascript",
        "--js",
        dest="javascript",
        action="store_true",
        help="Output json file",
    )

    parser.add_argument(
        "-o",
        "--out",
        dest="out_filepath",
        help="Output file",
    )
    args = parser.parse_args()
    compile(**vars(args))
