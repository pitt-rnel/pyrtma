"""pyrtma.data_logger.cli - Command Line Interface for pyrtma data logger control

Run with python -m pyrtma.data_logger.cli [MM_SERVER_ADDRESS]
"""

import json
import rich
from rich.prompt import Prompt
from rich.markup import escape

import pyrtma.core_defs as cd
from pyrtma.data_logger.data_logger_client import DataLoggerClient, DataSetConfig


def add_dataset(mod: DataLoggerClient):
    """Prompts for dataset configuration and adds it to the data logger"""
    name = save_path = filename = formatter = raw = None
    Prompt.prompt_suffix = ": "
    while not name:
        name = Prompt.ask("[bold](dataset)->[blue]name")
    while not save_path:
        save_path = Prompt.ask("[bold](dataset)->[blue]save_path")
    while not filename:
        filename = Prompt.ask("[bold](dataset)->[blue]filename")
    while not formatter:
        formatter = Prompt.ask("[bold](dataset)->[blue]formatter")

    while raw is None:
        raw = Prompt.ask(
            "[bold](dataset)->[blue]msg_type", default=None, show_default=False
        )
    if raw.lower() in ("all", "*"):
        msg_types = [cd.ALL_MESSAGE_TYPES]
    else:
        msg_types = list(map(int, raw.split()))

    config = DataSetConfig(
        name=name,
        save_path=save_path,
        filename=filename,
        formatter=formatter,
        msg_types=msg_types,
    )
    config.add(mod)


def main():
    """Main function for the data_logger control CLI."""
    import sys

    if len(sys.argv) > 1:
        server = sys.argv[1]
    else:
        server = "127.0.0.1:7111"

    mod = DataLoggerClient()
    mod.connect(server)

    try:
        while True:
            Prompt.prompt_suffix = ">> "
            cmd_str = Prompt.ask("[bold](data_log)", default=None, show_default=False)
            if not cmd_str:
                help()
                continue
            args = cmd_str.split()
            nargs = len(args)
            cmd = args[0].lower()
            if cmd in ("add", "a") and nargs == 1:
                add_dataset(mod)
            elif cmd in ("remove", "d") and nargs == 2:
                mod.rm_dataset(args[1])
            elif cmd in ("start", "s") and nargs == 2:
                mod.start_dataset(args[1])
            elif cmd in ("start-all", "sa") and nargs == 1:
                mod.start_all_datasets()
            elif cmd in ("stop", "x") and nargs == 2:
                mod.stop_dataset(args[1])
            elif cmd in ("stop-all", "xa") and nargs == 1:
                mod.stop_all_datasets()
            elif cmd in ("pause", "p") and nargs == 2:
                mod.pause_dataset(args[1])
            elif cmd in ("pause-all", "pa") and nargs == 1:
                mod.pause_all_datasets()
            elif cmd in ("resume", "r") and nargs == 2:
                mod.resume_dataset(args[1])
            elif cmd in ("resume-all", "ra") and nargs == 1:
                mod.resume_all_datasets()
            elif cmd in ("status", "=") and nargs == 2:
                mod.request_dataset_status(args[1])
            elif cmd in ("status-all", "=a") and nargs == 1:
                mod.request_all_dataset_status()
            elif cmd in ("config", "c") and nargs == 1:
                mod.request_data_logger_config()
            elif cmd in ("reset", "<") and nargs == 1:
                mod.reset_data_logger()
            elif cmd in ("kill", "k") and nargs == 1:
                mod.send_signal(cd.MT_LM_EXIT)
            elif cmd in ("exit", "quit", "q"):
                break
            elif cmd in ("help", "?", "h"):
                help()
            else:
                rich.print(f"Unknown command: {cmd_str}")
                help()

            while True:
                msg = mod.read_message(0.200)
                if msg:
                    if isinstance(msg.data, cd.MDF_DATA_LOGGER_ERROR):
                        rich.print(msg.data.msg)
                    elif isinstance(msg.data, cd.MDF_DATASET_STATUS):
                        rich.print(msg.data.to_json())
                    elif isinstance(msg.data, cd.MDF_DATA_LOGGER_CONFIG):
                        d = mod.process_data_logger_config_msg(msg.data)
                        rich.print(json.dumps(d, indent=2))
                else:
                    break

    except KeyboardInterrupt:
        pass

    rich.print("Goodbye")


def help():
    """Prints the help message for the data_logger control CLI."""
    name = escape("[NAME]")
    g = "[green]"
    b = "[blue]"

    rich.print(f"\n[u]data_logger control:")
    rich.print(f"  * {g}add[/]/{g}a[/] - Add a dataset.")
    rich.print(f"  * {g}remove[/]/{g}d[/] {b}{name}[/] - Remove dataset NAME")
    rich.print(f"  * {g}start[/]/{g}s[/] {b}{name}[/] - Start dataset NAME")
    rich.print(f"  * {g}start-all[/]/{g}sa[/] - Start all datasets")
    rich.print(f"  * {g}stop[/]/{g}x[/] {b}{name}[/] - Stop dataset NAME")
    rich.print(f"  * {g}stop-all[/]/{g}xa[/] - Stop all datasets")
    rich.print(f"  * {g}pause[/]/{g}p[/] {b}{name}[/] - Pause dataset NAME")
    rich.print(f"  * {g}pause-all[/]/{g}pa[/] - Pause all datasets")
    rich.print(f"  * {g}resume[/]/{g}r[/] {b}{name}[/] - Resume dataset NAME")
    rich.print(f"  * {g}resume-all[/]/{g}ra[/] - Resume all datasets")
    rich.print(f"  * {g}status[/]/{g}=[/] {b}{name}[/] - Get status of dataset NAME")
    rich.print(f"  * {g}status-all[/]/{g}=a[/] - Get status of all datasets")
    rich.print(f"  * {g}config[/]/{g}c[/] - Get data_logger config")
    rich.print(f"  * {g}reset[/]/{g}<[/] - Reset data_logger")
    rich.print(f"  * {g}kill[/]/{g}k[/] - Close data_logger")
    rich.print(f"  * {g}help[/]/{g}h[/]/{g}?[/] - rich.print this help")
    rich.print(f"  * {g}exit[/]/{g}quit[/]/{g}q[/] - close application.\n")


if __name__ == "__main__":
    main()
