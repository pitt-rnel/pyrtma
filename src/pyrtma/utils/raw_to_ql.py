"""Convert raw data logger files (``.dat``) to QuickLogger files (``.bin``).

Each raw file becomes one QuickLogger version 1 file holding the same
messages, in the same order, with their headers as the logger received them,
so tools that read QuickLogger files, such as
:py:class:`pyrtma.utils.log_reader.LogReader`, can read raw recordings.

Records are decoded with the given message definitions, which QuickLogger
files need. A record that doesn't decode with them is left out and counted:
for a record the logger marked undecoded, pass the sending module's
definitions to keep it. Damaged records are skipped as
:py:class:`pyrtma.utils.raw_reader.RawFile` skips them, so a raw file cut
short by a crash converts up to where it ends.

Command line::

    python -m pyrtma.utils.raw_to_ql -d DEFS_FILE FILE.dat [FILE.dat ...]
        [-o OUTPUT_DIR] [--overwrite]
"""

from __future__ import annotations

import argparse
import collections
import os
import pathlib
import sys
from dataclasses import dataclass, field
from typing import Any, Optional

from pyrtma.data_logger.formatters.quicklogger import QLFormatter
from pyrtma.exceptions import (
    InvalidMessageDefinition,
    RawFormatError,
    UnknownMessageType,
)
from pyrtma.message import Message
from pyrtma.utils.raw_reader import RawFile

#: The most bytes a QuickLogger version 1 file can hold: its sizes are 32-bit.
QL_MAX_BYTES: int = 0xFFFFFFFF
#: Messages decoded before each write to the QuickLogger file.
BATCH_SIZE: int = 10_000
#: Added to the destination's name while it is being written.
PARTIAL_SUFFIX: str = ".partial"


@dataclass
class Conversion:
    """What converting one raw file did.

    Attributes:
        source: The raw file.
        destination: The QuickLogger file written.
        written: Messages written.
        skipped: Records left out because they don't decode with the
            definitions, by message type.
        damage: Damaged byte ranges skipped in the source, as
            ``(offset, length)``.
        source_complete: The source was closed normally and read intact.
    """

    source: pathlib.Path
    destination: pathlib.Path
    written: int = 0
    skipped: collections.Counter[int] = field(default_factory=collections.Counter)
    damage: list[tuple[int, int]] = field(default_factory=list)
    source_complete: bool = False

    @property
    def ok(self) -> bool:
        """Every record of a complete source was converted."""
        return self.source_complete and not self.skipped


def default_destination(
    source: pathlib.Path, output_dir: Optional[pathlib.Path] = None
) -> pathlib.Path:
    """The QuickLogger file a raw file converts to.

    Args:
        source: The raw file.
        output_dir: The folder to write to, or None for the source's folder.

    Returns:
        ``source`` with the ``.bin`` suffix, in ``output_dir`` if given.
    """
    folder = source.parent if output_dir is None else output_dir
    return folder / (source.stem + QLFormatter.ext)


def _write(formatter: QLFormatter, batch: list[Message], source: pathlib.Path) -> None:
    """Write a batch, all of which must fit in the file."""
    if batch and formatter.write(batch) != len(batch):
        raise OverflowError(
            f"{source} holds more than a QuickLogger version 1 file can: "
            f"{formatter.max_bytes} bytes."
        )


def convert(
    source: pathlib.Path | str,
    destination: pathlib.Path | str,
    definitions: Any,
    *,
    overwrite: bool = False,
) -> Conversion:
    """Convert one raw file to a QuickLogger file.

    The QuickLogger file is written under a temporary name beside the
    destination and renamed when it is finished, so a failed conversion
    leaves no partial file.

    Args:
        source: The raw file.
        destination: The QuickLogger file to write.
        definitions: Message definitions to decode with, such as from
            ``pyrtma.load_message_definitions()``.
        overwrite: Replace ``destination`` if it exists.

    Returns:
        What the conversion did.

    Raises:
        FileExistsError: ``destination`` exists and ``overwrite`` is False.
        RawFormatError: ``source`` isn't a raw file this pyrtma can read.
        OverflowError: The messages don't fit in one QuickLogger file.
        OSError: A file can't be read or written.
    """
    source = pathlib.Path(source)
    destination = pathlib.Path(destination)
    if destination.exists() and not overwrite:
        raise FileExistsError(f"{destination} already exists.")
    partial = destination.with_name(destination.name + PARTIAL_SUFFIX)
    result = Conversion(source, destination)
    try:
        with RawFile(source) as raw, open(partial, "wb") as fd:
            formatter = QLFormatter(fd)
            formatter.max_bytes = QL_MAX_BYTES
            try:
                batch: list[Message] = []
                for record in raw.records():
                    try:
                        batch.append(record.decode(definitions))
                    except (UnknownMessageType, InvalidMessageDefinition):
                        result.skipped[record.header.msg_type] += 1
                        continue
                    if len(batch) >= BATCH_SIZE:
                        _write(formatter, batch, source)
                        result.written += len(batch)
                        batch = []
                _write(formatter, batch, source)
                result.written += len(batch)
                formatter.finalize([])
            except BaseException:
                formatter.discard()
                raise
            result.damage = list(raw.damage)
            result.source_complete = raw.complete
        os.replace(partial, destination)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return result


def describe(result: Conversion) -> str:
    """One line, with any problems on more, about a conversion.

    Args:
        result: The conversion.

    Returns:
        The text, without a final newline.
    """
    lines = [f"{result.source.name} -> {result.destination}: {result.written} messages"]
    if result.skipped:
        types = ", ".join(f"{t}x{n}" for t, n in sorted(result.skipped.items()))
        lines.append(f"  left out, not decodable with these definitions: {types}")
    for offset, length in result.damage:
        lines.append(f"  damaged source: {length} bytes skipped at offset {offset}")
    if not result.source_complete and not result.damage:
        lines.append("  source cut short: no trailer")
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    """Convert raw files, printing what each conversion did.

    Args:
        argv: Command line arguments, or None for ``sys.argv``.

    Returns:
        0 if every file converted completely, otherwise 1.
    """
    import pyrtma

    parser = argparse.ArgumentParser(
        description="Convert raw data logger files (.dat) to QuickLogger files (.bin)."
    )
    parser.add_argument("files", nargs="+", type=pathlib.Path, help="raw files")
    parser.add_argument(
        "-d",
        "--defs",
        dest="defs_file",
        required=True,
        help="Python message definitions file to decode with. Required argument.",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=pathlib.Path,
        help="folder for the .bin files (default: beside each raw file)",
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="replace .bin files that exist"
    )
    args = parser.parse_args(argv)

    definitions = pyrtma.load_message_definitions(args.defs_file)
    if args.output_dir is not None:
        args.output_dir.mkdir(parents=True, exist_ok=True)
    status = 0
    for source in args.files:
        destination = default_destination(source, args.output_dir)
        try:
            result = convert(source, destination, definitions, overwrite=args.overwrite)
        except (FileExistsError, RawFormatError, OverflowError, OSError) as e:
            print(f"{source}: {e}", file=sys.stderr)
            status = 1
            continue
        print(describe(result))
        if not result.ok:
            status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
