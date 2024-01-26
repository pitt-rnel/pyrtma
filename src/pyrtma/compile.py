"""pyrtma.compile Message Type Compiler """

import pathlib
import re
import sys
from typing import List, Union

from .parser import Parser, ParserError, FileFormatError
from rich.traceback import install
import warnings
from pyrtma.compilers.python import PyDefCompiler
from pyrtma.compilers.javascript import JSDefCompiler
from pyrtma.compilers.matlab import MatlabDefCompiler
from pyrtma.compilers.c99 import CDefCompiler
from pyrtma.compilers.yaml import YAMLCompiler
from pyrtma.compilers.info import InfoCompiler

install(word_wrap=True, show_locals=True)


def compile(
    defs_files: List[str],  # str, # change back to str after removing v1 compiler
    out_dir: str,
    out_name: str,
    python: bool = False,
    javascript: bool = False,
    matlab: bool = False,
    c_lang: bool = False,
    info: bool = False,
    combined: bool = False,
    debug: bool = False,
    validate_alignment: bool = True,
    auto_pad: bool = True,
):
    """compile message defs

    Args:
        defs_files (List[str]): Root YAML message defintion file to parse. List of C header file(s) will use v1 python compiler (deprecated)
        out_name (str): Output directory for compiled files. For v1 compiler (deprecated), full output filename.
        python (bool, optional): Output python .py file. Defaults to False.
        javascript (bool, optional): Output javascript .js file. Defaults to False.
        matlab (bool, optional): Output matlab .m file. Defaults to False.
        c_lang (bool, optional): Output C .h file. Defaults to False.
        info (bool, optional): Output info .txt file. Defaults to False.
        combined (bool, optional): Output combined YAML file. Defaults to False.
        debug (bool, optional): Debug mode. Defaults to False.
        validate_alignment(bool, optional): Validate message 64-bit alignment. Defaults to True.
        auto_pad(bool, optional): Automatically pad messages failing 64-bit alignment validation. Defaults to True. Has no effect if validate_alignment is False.


    Raises:
        FileFormatError: Issue with input file format
        FileExistsError: Output file is not a directory
        RuntimeError: Invalid output filename
    """
    # determine if using v1 or v2 compiler
    file1_ext = pathlib.Path(defs_files[0]).suffix
    if file1_ext.lower() == ".h":
        compiler_version = 1
        warnings.warn(
            "V1 message def .h compiler is deprecated and has been replaced by the V2 yaml compiler.",
            FutureWarning,
        )
    elif file1_ext.lower() in [".yaml", ".yml"]:
        compiler_version = 2
        if len(defs_files) > 1:
            raise FileFormatError("defs_file must be a single .yaml file")
    else:
        raise FileFormatError("Unexpected file type. defs_file must be a .yaml file.")

    if compiler_version == 1:
        from pyrtma.compilers.python_v1 import python_v1_compile

        print("Building V1 python message definitions...")
        python_v1_compile(include_files=defs_files, out_filename=out_dir)
        print("DONE.")
        return
    # else continue with compiler V2

    defs_file = defs_files[0]
    parser = Parser(
        debug=debug, validate_alignment=validate_alignment, auto_pad=auto_pad
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

    compiler: Union[
        PyDefCompiler,
        JSDefCompiler,
        MatlabDefCompiler,
        CDefCompiler,
        YAMLCompiler,
        InfoCompiler,
    ]
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


def main():
    import argparse

    parser = argparse.ArgumentParser(description="pyrtma Message Definition Compiler.")

    parser.add_argument(
        "-i",
        "-I",
        "--defs",
        nargs="*",  # for backwards compatibility with v1 compiler. Remove in future version along with v1 compiler.
        dest="defs_files",
        help="YAML message defintion file to parse. C header file(s) will use v1 python compiler (deprecated)",
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
        help="Output javascript .js file",
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
        "--info",
        dest="info",
        action="store_true",
        help="Output info .txt file",
    )

    parser.add_argument(
        "--combined",
        dest="combined",
        action="store_true",
        help="Output combined yaml file",
    )

    parser.add_argument(
        "-o",
        "--out",
        default="",
        dest="out_dir",
        help="Output directory for compiled files. For v1 compiler (deprecated), full output filename.",
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

    parser.add_argument(
        "--no_val_align",
        dest="validate_alignment",
        action="store_false",
        help="Disable 64-bit alignment validation",
    )

    parser.add_argument(
        "--no_auto_pad",
        dest="auto_pad",
        action="store_false",
        help="Disable 64-bit alignment auto-padding",
    )

    args = parser.parse_args()
    try:
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
