import datetime
import json
import re
import os

from .exceptions import MissingMetadata, InvalidMetadata
from typing import Union


class LoggingMetadata:
    def __init__(self):
        self._metadata: dict[str, Union[str, float, int]] = {}

    def update(self, json_str: str):
        try:
            new_data = json.loads(json_str)
        except json.JSONDecodeError:
            raise InvalidMetadata("The metadata provided was not formatted as json.")

        if not all(isinstance(v, (str, float, int)) for v in new_data.values()):
            raise InvalidMetadata("Metadata can only contain str, float, or ints.")

        self._metadata.clear()
        self._metadata.update(**new_data)
        self._update_buitlins()

    def to_json(self):
        return json.dumps(self._metadata, separators=(",", ":"))

    def clear(self):
        self._metadata.clear()

    def _update_buitlins(self):
        now = datetime.datetime.now()

        # Builtin Time metadata
        self._metadata.update(
            date=now.strftime("%Y_%m_%d"),
            isodate=now.strftime("%Y-%m-%d"),
            timestamp=now.strftime("%H%M%S"),
            timestamp_ms=now.strftime("%H%M%S%f"),
        )

    def expand_format(self, s: str) -> str:
        self._update_buitlins()

        def repl(m: re.Match) -> str:
            d = m.groupdict()
            key = d["key"]
            fmt = d["fmt"] or ""

            if d["scope"] == "env":
                try:
                    value = os.environ[key]
                except KeyError:
                    raise MissingMetadata(
                        f"No value found in env for {key} in metadata format string: {s}"
                    )
            else:
                try:
                    value = self._metadata[key]
                except KeyError:
                    raise MissingMetadata(
                        f"No value found in metadata for {key} in metadata format string: {s}"
                    )

            return value.__format__(fmt)

        pattern = r"\$\(((?P<scope>env):)?(?P<key>\w+)(:(?P<fmt>\w*))?\)"
        s = re.sub(pattern, repl, s)

        if s.find("$") != -1:
            raise MissingMetadata(
                f"Failed to fully expand format string with metadata: {s}"
            )

        return s
