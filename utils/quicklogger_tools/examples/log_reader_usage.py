import pathlib
from quicklogger_tools import LogReader

if __name__ == "__main__":
    # User selects files from explorer window
    logs = LogReader.browse()

    # User loads files explicitly from paths with filtering
    base = pathlib.Path.home() / "desktop" / "ql_data"
    msgdefs = base / "message_defs.py"
    binfiles = list(base.glob("*.bin"))

    logs = LogReader.load(msgdefs, binfiles, include=["SPIKE_SNIPPET"])
