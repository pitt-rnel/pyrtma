"""pyrtma.compile Message Type Compiler """

import pathlib
import os
from .parser import Parser
from .processor import Processor
from typing import List


def compile(
    defs_files: List[str],
    out_filepath: str,
    python: bool = False,
    javascript: bool = False,
    debug: bool = False,
):

    # Add the core defintions
    # pkg_dir = pathlib.Path(os.path.realpath(__file__)).parent
    # core_defs_h = pkg_dir / "core_defs/core_defs.h"
    # defs_files.insert(0, str(core_defs_h))

    parser = Parser(debug=debug)
    for f in defs_files:
        parser.parse(f)

    if debug:
        print(parser.to_json())

    processor = Processor(parser.tokens, debug=debug)

    if python:
        print("Building python message definitions...")
        from pyrtma.compilers.python import PyDefCompiler

        compiler = PyDefCompiler(processor, debug=debug)
        ext = ".py"
        p = pathlib.Path(out_filepath)
        out = p.stem + ext
        compiler.generate(str(p.parent / out))

    if javascript:
        print("Building javascript message definitions...")
        from pyrtma.compilers.javascript import JSDefCompiler

        compiler = JSDefCompiler(processor, debug=debug)
        ext = ".js"
        p = pathlib.Path(out_filepath)
        out = p.stem + ext
        compiler.generate(str(p.parent / out))

    print("DONE.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="pyrtma Message Definition Compiler.")

    parser.add_argument(
        "-i",
        "-I",
        "--defs",
        nargs="*",
        dest="defs_files",
        help="Files to parse",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--python",
        "--py",
        dest="python",
        action="store_true",
        help="Output python file",
    )

    group.add_argument(
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

    parser.add_argument(
        "--debug",
        dest="debug",
        action="store_true",
        help="Debug compiler",
    )

    args = parser.parse_args()
    compile(**vars(args))
