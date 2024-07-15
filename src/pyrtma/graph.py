import subprocess as sp
import pathlib
import tempfile
import time


def main():
    input_file = pathlib.Path(tempfile.gettempdir()) / "rtma_graph/rtma_graph.gv"
    out_file = pathlib.Path(tempfile.gettempdir()) / "rtma_graph/rtma_graph.svg"
    interval = 1.0

    print("Rendering rtma_graph.svg every 5s")
    try:
        while True:
            sp.run(["dot", "-Tsvg", "-Kcirco", f"-o{out_file}", f"{input_file}"])
            time.sleep(interval)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
