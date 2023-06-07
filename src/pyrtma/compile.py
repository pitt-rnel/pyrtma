"""pyrtma.compile Message Type Compiler """

import pathlib
import os
from .parser import Parser, Processor
from typing import List


def compile(
    defs_files: List[str],
    out_filepath: str,
    python: bool = False,
    javascript: bool = False,
    debug: bool = False,
):

    if python:
        print("Building python message definitions...")
        from pyrtma.compilers.python import PyDefCompiler

        tokens = []
        for f in defs_files:
            tokens.extend(Parser.parse(f))

            if debug:
                print(Parser.to_json(f))

        processor = Processor(tokens)
        compiler = PyDefCompiler(processor)
        ext = ".py"
        p = pathlib.Path(out_filepath)
        out = p.stem + ".py"

        compiler.generate(str(p.parent / out))

    if javascript:
        print("Building javascript message definitions...")
        from pyrtma.compilers.javascript import JSDefCompiler

        pkg_dir = pathlib.Path(os.path.realpath(__file__)).parent
        core_defs_h = pkg_dir / "core_defs/core_defs.h"
        defs_files.insert(0, str(core_defs_h))

        tokens = []
        for f in defs_files:
            tokens.extend(Parser.parse(f))

            if debug:
                print(Parser.to_json(j))

        processor = Processor(tokens)
        compiler = JSDefCompiler(processor)
        ext = ".js"
        p = pathlib.Path(out_filepath)
        out = p.stem + ".js"
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
