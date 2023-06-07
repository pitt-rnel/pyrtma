"""pyrtma.compile Message Type Compiler """

import pathlib
import os
from .parser import Parser, Processor
from typing import List


def compile(
    include_files: List,
    out_filepath: str,
    python: bool = False,
    javascript: bool = False,
    matlab: bool = False,
    debug: bool = False,
):

    if python:
        print("Building python message definitions...")
        from pyrtma.compilers.python import PyDefCompiler

        parser = Parser()
        parser.parse(include_files)
        if debug:
            print(parser.to_json())

        processor = Processor(parser)
        compiler = PyDefCompiler(processor)
        ext = ".py"
        p = pathlib.Path(out_filepath)
        out = p.stem + ext

        compiler.generate(out)

    if javascript:
        print("Building javascript message definitions...")
        from pyrtma.compilers.javascript import JSDefCompiler

        parser = Parser()

        pkg_dir = pathlib.Path(os.path.realpath(__file__)).parent
        core_defs_h = pkg_dir / "core_defs/core_defs.h"

        include_files.insert(0, str(core_defs_h))
        parser.parse(include_files)
        if debug:
            print(parser.to_json())

        processor = Processor(parser)
        compiler = JSDefCompiler(processor)
        ext = ".js"
        p = pathlib.Path(out_filepath)
        out = p.stem + ext
        compiler.generate(out)

    if matlab:
        print("Building matlab message definitions...")
        from pyrtma.compilers.matlab import MatlabDefCompiler
        
        parser = Parser()

        pkg_dir = pathlib.Path(os.path.realpath(__file__)).parent
        core_defs_h = pkg_dir / "core_defs/core_defs.h"

        include_files.insert(0, str(core_defs_h))
        parser.parse(include_files)
        if debug:
            print(parser.to_json())

        processor = Processor(parser)
        compiler = MatlabDefCompiler(processor)
        name = "generate_RTMA_config.m"
        
        p = pathlib.Path(out_filepath)
        if p.is_dir():
            out = p / name
        else:
            out = p.parent / name
        compiler.generate(out)

    print("DONE.")


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

    group.add_argument(
        "--matlab",
        "--ml",
        dest="matlab",
        action="store_true",
        help="Output matlab .m file",
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
