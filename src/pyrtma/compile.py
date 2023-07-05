"""pyrtma.compile Message Type Compiler """

import pathlib
from .parser import Parser


def compile(
    defs_file: str,
    out_filepath: str,
    python: bool = False,
    javascript: bool = False,
    matlab: bool = False,
    debug: bool = False,
):
    parser = Parser(debug=debug)
    parser.parse(pathlib.Path(defs_file))

    if debug:
        print(parser.to_json())
        with open("parser.json", "w") as f:
            f.write(parser.to_json())

    if python:
        print("Building python message definitions...")
        from pyrtma.compilers.python import PyDefCompiler

        compiler = PyDefCompiler(parser, debug=debug)
        ext = ".py"
        p = pathlib.Path(out_filepath)
        out = p.stem + ext
        compiler.generate(str(p.parent.absolute() / out))

    if javascript:
        print("Building javascript message definitions...")
        from pyrtma.compilers.javascript import JSDefCompiler

        compiler = JSDefCompiler(parser, debug=debug)
        ext = ".js"
        p = pathlib.Path(out_filepath)
        out = p.stem + ext
        compiler.generate(str(p.parent / out))

    if matlab:
        print("Building matlab message definitions...")
        from pyrtma.compilers.matlab import MatlabDefCompiler

        compiler = MatlabDefCompiler(parser, debug=debug)
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
        "--defs",
        dest="defs_file",
        help="File to parse",
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
