"""pyrtma.data_logger.cli - Command Line Interface for pyrtma data logger control

Run with python -m pyrtma.data_logger.cli [MM_SERVER_ADDRESS]
"""

import json
import sys

import rich
import pyrtma
import pyrtma.core_defs as cd

from rich.prompt import Prompt
from rich.markup import escape

from pyrtma.client_logging import _field_size
from pyrtma.data_logger.dataset import Dataset
from pyrtma.exceptions import MessageManagerNotFound

# The longest dataset message types list, from DATASET.msg_types.
_MAX_MSG_TYPES = 64


def _ask_text(label: str, field: str) -> str:
    """Ask for a dataset text field until the answer fits it.

    Args:
        label: The prompt.
        field: The ``DATASET`` field it fills, for its size.

    Returns:
        A non-empty ASCII answer short enough for the field.
    """
    longest = _field_size(cd.DATASET(), field) - 1
    while True:
        value = Prompt.ask(f"[bold](dataset)->[blue]{label}")
        if not value:
            continue
        if not value.isascii():
            rich.print(f"[red]{label} must be ASCII.")
        elif len(value) > longest:
            rich.print(f"[red]{label} must be at most {longest} characters.")
        else:
            return value


def parse_msg_types(raw: str) -> list[int]:
    """Parse message types as the CLI takes them.

    Args:
        raw: ``all`` or ``*``, or message type IDs separated by spaces or
            commas.

    Raises:
        ValueError: Nothing was given, an ID isn't a positive integer, or
            there are more than the 64 a dataset holds.

    Returns:
        The message type IDs.
    """
    if raw.strip().lower() in ("all", "*"):
        return [cd.ALL_MESSAGE_TYPES]
    parts = raw.replace(",", " ").split()
    if not parts:
        raise ValueError("give message type IDs, or all.")
    msg_types = []
    for part in parts:
        try:
            msg_type = int(part)
        except ValueError:
            raise ValueError(f"{part!r} isn't a message type ID.") from None
        if msg_type <= 0:
            raise ValueError(f"{msg_type} isn't a message type ID.")
        msg_types.append(msg_type)
    if len(msg_types) > _MAX_MSG_TYPES:
        raise ValueError(f"a dataset holds at most {_MAX_MSG_TYPES} message types.")
    return msg_types


def _ask_msg_types() -> list[int]:
    """Ask for the message types until they parse."""
    while True:
        raw = Prompt.ask(
            "[bold](dataset)->[blue]msg_type", default=None, show_default=False
        )
        if raw is None:
            continue
        try:
            return parse_msg_types(raw)
        except ValueError as e:
            rich.print(f"[red]msg_type: {e}")


def _ask_max_size_mb() -> int:
    """Ask for the file size limit until it is in range."""
    while True:
        raw = Prompt.ask(
            "[bold](dataset)->[blue]max_size_mb",
            default=str(cd.DATASET_MAX_SIZE_MB),
        )
        try:
            size = int(raw)
        except ValueError:
            size = 0
        if 1 <= size <= cd.DATASET_MAX_SIZE_MB:
            return size
        rich.print(f"[red]max_size_mb must be from 1 to {cd.DATASET_MAX_SIZE_MB}.")


def add_dataset(client: pyrtma.Client | None = None) -> Dataset:
    """Prompt for a dataset's configuration and add it to the data logger.

    Each answer is checked as it is given, and asked again if it won't do.

    Args:
        client: The connected client to send with, as ``main()`` passes. If
            None, the dataset connects a client of its own to the default
            server, as before.

    Returns:
        The dataset.
    """
    Prompt.prompt_suffix = ": "
    name = _ask_text("name", "name")
    save_path = _ask_text("save_path", "save_path")
    filename = _ask_text("filename", "filename")
    formatter = _ask_text("formatter", "formatter")
    msg_types = _ask_msg_types()
    max_size_mb = _ask_max_size_mb()

    ds = Dataset(
        name=name,
        save_path=save_path,
        filename=filename,
        formatter=formatter,
        msg_types=msg_types,
        create_client=client is None,
        max_size_mb=max_size_mb,
    )
    if client is not None:
        ds.register_client(client)

    ds.add()
    return ds


def main():
    """Main function for the data_logger control CLI."""
    if len(sys.argv) > 1:
        server = sys.argv[1]
    else:
        server = "127.0.0.1:7111"

    # Only data logger messages, which are core messages, are used.
    mod = pyrtma.Client(definitions=cd.get_message_definitions())
    try:
        mod.connect(server)
    except MessageManagerNotFound as e:
        print(f"MessageManagerNotFound: {e}", file=sys.stderr)
        sys.exit(1)
    mod.subscribe(Dataset.DATALOGGER_TYPES)

    datasets = []
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
            try:
                if dispatch(mod, cmd, args, nargs, cmd_str, datasets):
                    break
            except (ValueError, TypeError) as e:
                # A dataset name that is too long or isn't ASCII.
                rich.print(f"[red]Invalid name: {escape(str(e))}")

            read_replies(mod)

    except KeyboardInterrupt:
        pass

    rich.print("Goodbye")


def dispatch(
    mod: pyrtma.Client,
    cmd: str,
    args: list[str],
    nargs: int,
    cmd_str: str,
    datasets: list[Dataset],
) -> bool:
    """Run one command.

    Returns:
        True to exit.

    Raises:
        ValueError: A dataset name is too long.
        TypeError: A dataset name isn't ASCII.
    """
    if cmd in ("add", "a") and nargs == 1:
        datasets.append(add_dataset(mod))
    elif cmd in ("remove", "d") and nargs == 2:
        msg = cd.MDF_DATASET_REMOVE()
        msg.name = args[1]
        mod.send_message(msg)
    elif cmd in ("start", "s") and nargs == 2:
        msg = cd.MDF_DATASET_START()
        msg.name = args[1]
        mod.send_message(msg)
    elif cmd in ("start-all", "sa") and nargs == 1:
        msg = cd.MDF_DATASET_START()
        msg.name = "*"
        mod.send_message(msg)
    elif cmd in ("stop", "x") and nargs == 2:
        msg = cd.MDF_DATASET_STOP()
        msg.name = args[1]
        mod.send_message(msg)
    elif cmd in ("stop-all", "xa") and nargs == 1:
        msg = cd.MDF_DATASET_STOP()
        msg.name = "*"
        mod.send_message(msg)
    elif cmd in ("pause", "p") and nargs == 2:
        msg = cd.MDF_DATASET_PAUSE()
        msg.name = args[1]
        mod.send_message(msg)
    elif cmd in ("pause-all", "pa") and nargs == 1:
        msg = cd.MDF_DATASET_PAUSE()
        msg.name = "*"
        mod.send_message(msg)
    elif cmd in ("resume", "r") and nargs == 2:
        msg = cd.MDF_DATASET_RESUME()
        msg.name = args[1]
        mod.send_message(msg)
    elif cmd in ("resume-all", "ra") and nargs == 1:
        msg = cd.MDF_DATASET_RESUME()
        msg.name = "*"
        mod.send_message(msg)
    elif cmd in ("status", "=") and nargs == 2:
        msg = cd.MDF_DATASET_STATUS_REQUEST()
        msg.name = args[1]
        mod.send_message(msg)
    elif cmd in ("status-all", "=a") and nargs == 1:
        msg = cd.MDF_DATASET_STATUS_REQUEST()
        msg.name = "*"
        mod.send_message(msg)
    elif cmd in ("config", "c") and nargs == 1:
        mod.send_signal(cd.MT_DATA_LOGGER_CONFIG_REQUEST)
    elif cmd in ("reset", "<") and nargs == 1:
        mod.send_signal(cd.MT_DATA_LOGGER_RESET)
    elif cmd in ("kill", "k") and nargs == 1:
        mod.send_signal(cd.MT_LM_EXIT)
    elif cmd in ("exit", "quit", "q"):
        return True
    elif cmd in ("help", "?", "h"):
        help()
    else:
        rich.print(f"Unknown command: {escape(cmd_str)}")
        help()
    return False


def read_replies(mod: pyrtma.Client) -> None:
    """Print the data logger's replies until none arrives for 0.2 s."""
    while True:
        msg = mod.read_message(0.200)
        if msg:
            if isinstance(
                msg.data,
                (
                    cd.MDF_DATA_LOGGER_ERROR,
                    cd.MDF_DATASET_STATUS,
                    cd.MDF_DATASET_ADDED,
                    cd.MDF_DATASET_STARTED,
                    cd.MDF_DATASET_STOPPED,
                    cd.MDF_DATASET_REMOVED,
                    cd.MDF_DATASET_SAVED,
                ),
            ):
                rich.print(f"{msg.data.type_name}:")
                rich.print(msg.data.to_json())
            elif isinstance(msg.data, cd.MDF_DATA_LOGGER_CONFIG):
                rich.print(f"{msg.data.type_name}:")
                rich.print(json.dumps(msg.data.to_dict(), indent=2))
        else:
            break


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
