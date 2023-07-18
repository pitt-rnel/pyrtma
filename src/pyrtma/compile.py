"""pyrtma.compile Message Type Compiler """
import pathlib
import re

from .parser import Parser
from rich.traceback import install
install(word_wrap=True, show_locals=True)


def compile(
    defs_file: str,
    out_dir: str,
    out_name: str,
    python: bool = False,
    javascript: bool = False,
    matlab: bool = False,
    c_lang: bool = False,
    debug: bool = False,
):
    parser = Parser(debug=debug)
    parser.parse(pathlib.Path(defs_file))

    if debug:
        print(parser.to_json())
        with open("parser.json", "w") as f:
            f.write(parser.to_json())

    # Use the same directory and filename as the message defs file by default
    if out_dir == "":
        outpath = pathlib.Path(defs_file).parent.resolve().absolute()
    else:
        outpath = pathlib.Path(out_dir)

    if not outpath.is_dir():
        raise FileExistsError(f"The output location must be a directory.")

    # Make the final output directory, but no anything above it.
    outpath.mkdir(parents=False, exist_ok=True)

    if out_name == "":
        filename = pathlib.Path(defs_file).stem
    else:
        filename = out_name

    # Check for any invalid names
    if re.search(r"[^a-zA-Z0-9_-]", filename):
        raise RuntimeError(f"Invalid out filename: {filename}")

    if python:
        print("Building python message definitions...")
        from pyrtma.compilers.python import PyDefCompiler

        compiler = PyDefCompiler(parser, debug=debug)
        ext = ".py"
        output = outpath / (filename + ext)
        compiler.generate(output)

    if javascript:
        print("Building javascript message definitions...")
        from pyrtma.compilers.javascript import JSDefCompiler

        compiler = JSDefCompiler(parser, debug=debug)
        ext = ".js"
        output = outpath / (filename + ext)
        compiler.generate(output)

    if matlab:
        print("Building matlab message definitions...")
        from pyrtma.compilers.matlab import MatlabDefCompiler

        compiler = MatlabDefCompiler(parser, debug=debug)
        # Over-ride name
        matlab_filename = "generate_RTMA_config"
        ext = ".m"
        output = outpath / (matlab_filename + ext)
        compiler.generate(output)

    if c_lang:
        print("Building C/C++ message definitions...")
        from pyrtma.compilers.c99 import CDefCompiler

        compiler = CDefCompiler(parser, filename=filename, debug=debug)
        ext = ".h"
        output = outpath / (filename + ext)
        compiler.generate(output)

    print("DONE.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="pyrtma Message Definition Compiler.")

    parser.add_argument(
        "-i",
        "-I",
        "--defs",
        dest="defs_file",
        help="YAML message defintion file to parse",
    )

    parser.add_argument(
        "--c",
        "--c_lang",
        dest="c_lang",
        action="store_true",
        help="Output C .h file",
    )

    parser.add_argument(
        "--python",
        "--py",
        dest="python",
        action="store_true",
        help="Output python .py file",
    )

    parser.add_argument(
        "--javascript",
        "--js",
        dest="javascript",
        action="store_true",
        help="Output javascrip .js file",
    )

    parser.add_argument(
        "--matlab",
        "--mat",
        "--ml",
        dest="matlab",
        action="store_true",
        help="Output matlab .m file",
    )

    parser.add_argument(
        "-o",
        "--out",
        default="",
        dest="out_dir",
        help="Output directory for compiled files.",
    )

    parser.add_argument(
        "-n",
        "--name",
        default="",
        dest="out_name",
        help="Output file(s) base name.",
    )

    parser.add_argument(
        "--debug",
        dest="debug",
        action="store_true",
        help="Debug compiler",
    )

    args = parser.parse_args()
    compile(**vars(args))
