"""pyrtma.compile Message Type Compiler"""

import pathlib
import re
import sys

from .parser import Parser, ParserError, FileFormatError
from pyrtma.compilers.python import PyDefCompiler
from pyrtma.compilers.javascript import JSDefCompiler
from pyrtma.compilers.matlab import MatlabDefCompiler
from pyrtma.compilers.c99 import CDefCompiler
from pyrtma.compilers.yaml import YAMLCompiler
from pyrtma.compilers.info import InfoCompiler


def compile(
    defs_files: list[str],
    out_dir: str,
    out_name: str,
    python: bool = False,
    javascript: bool = False,
    matlab: bool = False,
    c_lang: bool = False,
    info: bool = False,
    combined: bool = False,
    debug: bool = False,
):
    """compile message defs

    Args:
        defs_files (list[str]): A list holding the root YAML message
            definition file to parse. C header (.h) files are no longer
            accepted.
        out_dir (str): Output directory for compiled files.
        out_name (str): Base name of the output files.
        python (bool, optional): Output python .py file. Defaults to False.
        javascript (bool, optional): Output javascript .js file. Defaults to False.
        matlab (bool, optional): Output matlab .m file. Defaults to False.
        c_lang (bool, optional): Output C .h file. Defaults to False.
        info (bool, optional): Output info .txt file. Defaults to False.
        combined (bool, optional): Output combined YAML file, and a compiler
            index for it, ``<name>_combined.defs``. Defaults to False.
        debug (bool, optional): Debug mode. Defaults to False.


    Raises:
        FileFormatError: Issue with input file format, including a C header
            (.h) file, which only the removed v1 compiler took.
        FileExistsError: The output location exists and is not a directory.
        FileNotFoundError: The output directory's parent doesn't exist.
        RuntimeError: Invalid output filename
    """
    file1_ext = pathlib.Path(defs_files[0]).suffix.lower()
    if file1_ext == ".h":
        raise FileFormatError(
            "C header (.h) message definitions are no longer supported; only the "
            "removed v1 compiler read them. Write the definitions in YAML and "
            "compile the .yaml or .defs file."
        )
    elif file1_ext.endswith((".defs", ".yml", ".yaml")):
        if len(defs_files) > 1:
            raise FileFormatError("defs_file must be a single .defs file")
    else:
        raise FileFormatError(
            "Unexpected file type. Compiler defs_file must be a (.defs, .yaml, .yml) file."
        )

    defs_file = defs_files[0]
    parser = Parser(
        debug=debug,
    )
    parser.parse(pathlib.Path(defs_file))

    if debug:
        with open("parser.json", "w") as f:
            f.write(parser.to_json())

    # Use the same directory and filename as the message defs file by default
    if out_dir == "":
        outpath = pathlib.Path(defs_file).parent.resolve().absolute()
    else:
        outpath = pathlib.Path(out_dir)

    # Make the final output directory, but nothing above it.
    try:
        outpath.mkdir(parents=False, exist_ok=True)
    except FileExistsError:
        raise FileExistsError(
            f"The output location must be a directory: {outpath}"
        ) from None

    if out_name == "":
        filename = pathlib.Path(defs_file).stem
    else:
        filename = out_name

    # Check for any invalid names
    if re.search(r"[^a-zA-Z0-9_-]", filename):
        raise RuntimeError(f"Invalid out filename: {filename}")

    compiler: (
        PyDefCompiler
        | JSDefCompiler
        | MatlabDefCompiler
        | CDefCompiler
        | YAMLCompiler
        | InfoCompiler
    )
    if python:
        print("Building python message definitions...")

        compiler = PyDefCompiler(parser, debug=debug)
        ext = ".py"
        output = outpath / (filename + ext)
        compiler.generate(output)

    if javascript:
        print("Building javascript message definitions...")

        compiler = JSDefCompiler(parser, debug=debug)
        ext = ".js"
        output = outpath / (filename + ext)
        compiler.generate(output)

    if matlab:
        print("Building matlab message definitions...")

        compiler = MatlabDefCompiler(parser, debug=debug)
        ext = ".m"
        output = outpath / (filename + ext)
        compiler.generate(output)

    if c_lang:
        print("Building C/C++ message definitions...")

        compiler = CDefCompiler(parser, filename=filename, debug=debug)
        ext = ".h"
        output = outpath / (filename + ext)
        compiler.generate(output)

    if combined:
        print("Building combined yaml file...")

        compiler = YAMLCompiler(parser, filename=filename, debug=debug)
        ext = ".yaml"
        output = outpath / (filename + "_combined" + ext)
        compiler.generate(output)

    if info:
        print("Building info file...")

        compiler = InfoCompiler(parser, filename=filename, debug=debug)
        ext = ".txt"
        output = outpath / (filename + ext)
        compiler.generate(output)

    print("DONE.")


def main() -> None:
    import argparse

    from rich.traceback import install

    # Only the command line replaces the exception hook, not an import.
    install(word_wrap=True, show_locals=True)

    # subparser for include file, to parse compiler options first
    argparser1 = argparse.ArgumentParser(
        description="pyrtma Message Definition Compiler.",
        add_help=False,
    )

    argparser1.add_argument(
        "-i",
        "-I",
        "--defs",
        # Still nargs="*", so command lines that parsed before still parse;
        # compile() accepts one file.
        nargs="*",
        dest="defs_files",
        help="Compiler YAML file to parse.",
    )

    # full arg parser
    argparser = argparse.ArgumentParser(
        parents=[argparser1],
        conflict_handler="resolve",
        add_help=True,
    )

    argparser.add_argument(
        "--c",
        "--c_lang",
        dest="c_lang",
        action="store_true",
        help="Output C .h file",
    )

    argparser.add_argument(
        "--python",
        "--py",
        dest="python",
        action="store_true",
        help="Output python .py file",
    )

    argparser.add_argument(
        "--javascript",
        "--js",
        dest="javascript",
        action="store_true",
        help="Output javascript .js file",
    )

    argparser.add_argument(
        "--matlab",
        "--mat",
        "--ml",
        dest="matlab",
        action="store_true",
        help="Output matlab .m file",
    )

    argparser.add_argument(
        "--info",
        dest="info",
        action="store_true",
        help="Output info .txt file",
    )

    argparser.add_argument(
        "--combined",
        dest="combined",
        action="store_true",
        help="Output combined yaml file",
    )

    argparser.add_argument(
        "-o",
        "--out",
        default="",
        dest="out_dir",
        help="Output directory for compiled files.",
    )

    argparser.add_argument(
        "-n",
        "--name",
        default="",
        dest="out_name",
        help="Output file(s) base name.",
    )

    argparser.add_argument(
        "--debug",
        dest="debug",
        action="store_true",
        help="Debug compiler",
    )

    # parse all options
    args = argparser.parse_args()

    try:
        # run compiler
        compile(**vars(args))
    except (ParserError, FileNotFoundError) as e:
        print()
        msg = " ".join(str(arg) for arg in e.args)
        print(f"{e.__class__.__name__}: {msg}")
        print()
        if e.__cause__:
            print("Details:")
            msg = " ".join(str(arg) for arg in e.__cause__.args)
            print(f"\t{e.__cause__.__class__.__name__}: {msg}")
        sys.exit(1)
    except Exception:
        raise

    sys.exit(0)


if __name__ == "__main__":
    main()
