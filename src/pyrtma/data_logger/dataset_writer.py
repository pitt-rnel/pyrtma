"""DataSet class used internally by data_logger"""

import contextlib
import pathlib
import io
import math
import time
import threading
import pyrtma

import pyrtma.core_defs as cd
from ..client_logging import TRUNCATED_MARKER, _ascii_field, _field_size
from ..message import Message
from ..core_defs import ALL_MESSAGE_TYPES
from .data_formatter import get_formatter
from typing import Callable, Type, Optional, IO, Any, List

from .data_formatter import DataFormatter
from .exceptions import (
    DatasetError,
    InvalidFormatter,
    DatasetExistsError,
    DatasetInProgress,
    DatasetThreadError,
    DataLoggerError,
)


def error_message(dataset: str, exc_type: str, text: str) -> cd.MDF_DATA_LOGGER_ERROR:
    """Build a ``DATA_LOGGER_ERROR`` that always fits its fields.

    Characters that aren't ASCII, as in a localized system message, become
    "?", and text too long for its field is cut, so building the message
    never raises.

    Args:
        dataset: The dataset's name, or "" for the logger as a whole.
        exc_type: The exception's type name.
        text: What happened.

    Returns:
        The message.
    """
    error = cd.MDF_DATA_LOGGER_ERROR()
    error.dataset_name = _ascii_field(dataset, _field_size(error, "dataset_name"))
    error.exc_type = _ascii_field(exc_type, _field_size(error, "exc_type"))
    error.msg = _ascii_field(text, _field_size(error, "msg"), marker=TRUNCATED_MARKER)
    return error


def _exclusive_mode(mode: str) -> str:
    """Turn a formatter's file mode into one that refuses an existing file.

    Args:
        mode: The formatter's mode, such as ``"wt"`` or ``"wb"``.

    Returns:
        The mode with ``w`` replaced by ``x``, so opening fails with
        ``FileExistsError`` instead of truncating another dataset's file.
    """
    return mode.replace("w", "x")


class DatasetWriter:
    MIN_INTERVAL = 30
    MAX_INTERVAL = 600
    CONTINUOUS = math.inf
    WRITE_PERIOD = 15.0

    def __init__(
        self,
        name: str,
        save_path: str,
        filename: str,
        formatter: str,
        subdivide_interval: int,
        msg_types: List[int],
        *,
        clock: Callable[[], float] = time.monotonic,
    ):
        """Set up a dataset; nothing is recorded until :py:meth:`start`.

        Args:
            name: The dataset's name.
            save_path: The folder to save to; it is created if needed.
            filename: The file name, without the formatter's extension.
            formatter: The name of a registered formatter.
            subdivide_interval: Seconds of recording per file, clamped to
                ``MIN_INTERVAL`` to ``MAX_INTERVAL``; 0 or less records one
                continuous file.
            msg_types: The message types to record; ``ALL_MESSAGE_TYPES``
                records every type.
            clock: Seconds from a monotonic clock, for the write and
                subdivide schedule and the elapsed time. Injectable for tests.

        Raises:
            InvalidFormatter: No formatter has that name.
            DatasetError: The save path can't be created.
            DatasetExistsError: The file already exists.
        """
        self._dead = False
        self._recording = False
        self._paused = False
        self._close = False
        self._elapsed_time = 0.0
        self._clock = clock
        self._started = False
        self._failed = False
        # Guards _failed, so only the first failure is reported.
        self._state_lock = threading.Lock()
        # When the writer fell behind, or None while it keeps up.
        self._behind_since: Optional[float] = None
        # A subdivision that fell due while the writer was busy.
        self._subdivide_due = False

        self.name = name

        self.client = pyrtma.Client(
            0, name=f"dataset.{name}", definitions=cd.get_message_definitions()
        )
        # Note: We don't connect. Just want to use the RTMALogger
        # self.client.connect(mm_ip)
        self.logger = self.client.logger

        self.save_path = pathlib.Path(save_path)

        self.formatter_name = formatter
        formatter_cls: Optional[Type[DataFormatter]] = get_formatter(formatter)
        if formatter_cls is None:
            raise InvalidFormatter(
                self.name, f"No DataFormatter class named {formatter}"
            )
        else:
            self.formatter_cls = formatter_cls

        # Append the formatter extension
        self.filename = filename + self.formatter_cls.ext
        self.base_file_name = filename

        if subdivide_interval <= 0:
            self.subdivide_interval = DatasetWriter.CONTINUOUS
        elif subdivide_interval < DatasetWriter.MIN_INTERVAL:
            self.subdivide_interval = DatasetWriter.MIN_INTERVAL
        elif subdivide_interval > DatasetWriter.MAX_INTERVAL:
            self.subdivide_interval = DatasetWriter.MAX_INTERVAL
        else:
            self.subdivide_interval = subdivide_interval

        # Placeholder for type checking purposes
        if "b" in self.formatter_cls.mode:
            self.formatter = self.formatter_cls(io.BytesIO())
        else:
            self.formatter = self.formatter_cls(io.StringIO())

        self.rbuf: List[Message] = []
        self.wbuf: List[Message] = []

        self.fd: Optional[IO[Any]] = None

        self.write_to_disk = threading.Event()
        self.write_finished = threading.Event()

        self.stop_flag = threading.Event()

        self.use_thread = True
        self.write_thread = threading.Thread(target=self.write)

        self.msg_types = [m for m in msg_types if m > 0]
        if ALL_MESSAGE_TYPES in msg_types:
            self.all_sub = True
        else:
            self.all_sub = False

        self.ref_time = -1.0
        self.start_time = -1.0

        self.subdivide_flag = False
        self.next_subdivide = math.inf
        self.sub_index = 0

        self.error_event = threading.Event()
        self.error = cd.MDF_DATA_LOGGER_ERROR()

        # Save location
        try:
            self.save_path.mkdir(parents=True, exist_ok=True)
        except FileNotFoundError as e:
            raise DatasetError(self.name, f"Save path not found: {self.save_path}")
        except PermissionError as e:
            raise DatasetError(self.name, f"File Permission Error: Access is denied.")
        except OSError as e:
            raise DatasetError(
                self.name, f"Can't create save path {self.save_path}: {e}"
            ) from e

        self.file_path = self.save_path / self.filename

        # List of all the files saved
        self.saved_files: list[pathlib.Path] = []
        self.file_saved = threading.Event()
        self.save_msg = cd.MDF_DATASET_SAVED()

        if self.file_path.exists():
            raise DatasetExistsError(self.name, f"{self.file_path} already exists.")

    def __del__(self):
        if self._dead:
            return
        else:
            if self.recording:
                self.stop()

    def pause(self) -> bool:
        """Stop recording messages until :py:meth:`resume`.

        Returns:
            True if the dataset was recording and is now paused. False if it
            wasn't recording or was already paused; nothing changes then.
        """
        if not self._recording or self._paused:
            return False
        self._elapsed_time = self.elapsed_time
        self._paused = True
        return True

    def resume(self) -> bool:
        """Record messages again after :py:meth:`pause`.

        Returns:
            True if the dataset was paused and is now recording. False if it
            wasn't paused; nothing changes then, so its elapsed time and
            subdivide schedule carry on.
        """
        if not self._recording or not self._paused:
            return False
        self._paused = False
        self.ref_time = self._clock()
        return True

    @property
    def elapsed_time(self) -> float:
        if self.stopped:
            return 0

        if self.paused:
            return self._elapsed_time

        return self._elapsed_time + (self._clock() - self.ref_time)

    @property
    def total_elapsed_time(self) -> float:
        return self._clock() - self.start_time

    @property
    def paused(self) -> bool:
        return self._paused

    @property
    def recording(self) -> bool:
        return self._recording

    @property
    def stopped(self) -> bool:
        return not self._recording

    @property
    def dead(self) -> bool:
        return self._dead

    @property
    def started(self) -> bool:
        """True once :py:meth:`start` has succeeded, including after it stops."""
        return self._started

    @property
    def failed(self) -> bool:
        """True once writing failed and the dataset stopped recording.

        The failure is in :py:attr:`error`, and :py:attr:`error_event` is set
        before the dataset is marked :py:attr:`dead`.
        """
        return self._failed

    def _open(self, path: pathlib.Path) -> tuple[IO[Any], DataFormatter]:
        """Create a dataset file and its formatter.

        Args:
            path: The file to create. It must not exist yet.

        Raises:
            DatasetExistsError: The file exists, for example because another
                dataset writes to it.
            DatasetError: The file can't be created, or the formatter can't
                start it. A file that was created is removed again.

        Returns:
            The open file and a formatter writing to it.
        """
        mode = _exclusive_mode(self.formatter_cls.mode)
        try:
            if "b" in mode:
                fd: IO[Any] = open(path, mode)
            else:
                fd = open(path, mode, encoding="utf-8")
        except FileExistsError as e:
            raise DatasetExistsError(self.name, f"{path} already exists.") from e
        except OSError as e:
            raise DatasetError(self.name, f"Can't create {path}: {e}") from e

        try:
            formatter = self.formatter_cls(fd)
        except Exception as e:
            # The file was created above, so it holds nothing of anyone's.
            with contextlib.suppress(OSError):
                fd.close()
            with contextlib.suppress(OSError):
                path.unlink()
            raise DatasetError(
                self.name, f"Can't start {path}: {type(e).__name__}: {e}"
            ) from e
        return fd, formatter

    def start(self):
        """Create the dataset's file and start recording.

        Raises:
            DatasetInProgress: The dataset was already started. A dataset
                records once; add it again to record again.
            DatasetExistsError: The file exists.
            DatasetError: The file can't be created or started. No thread is
                left running and the dataset isn't recording.
        """
        if self._started:
            raise DatasetInProgress(
                self.name, f"Dataset '{self.name}' has already been started."
            )

        # Open the file first, so a failure leaves no write thread running.
        self.fd, self.formatter = self._open(self.file_path)
        self._started = True

        # Reset some tracking vars
        self.sub_index = 0
        self.subdivide_flag = False
        self._subdivide_due = False
        self.next_subdivide = self.subdivide_interval

        self.start_time = self._clock()
        self.ref_time = self.start_time

        self.next_write = DatasetWriter.WRITE_PERIOD
        self._recording = True
        self._paused = False

        # Start the write thread
        self.write_thread.start()

    def update(self, msg: Optional[Message]):
        """Buffer a message, and hand the buffer to the writer when it's due.

        Never raises for a failed or slow writer: a failed one has stopped
        recording, and a slow one keeps the messages buffered until it is
        free, with a warning when it falls behind.

        Args:
            msg: A received message, or None to only check the schedule.
        """
        if self._paused or not self._recording:
            return

        if not self.write_thread.is_alive():
            # The thread records its own failures, so this is only a thread
            # that ended in some other way.
            self._fail(
                DatasetThreadError.__name__,
                "Data collection write thread is no longer active.",
            )
            return

        if msg:
            if self.all_sub or msg.type_id in self.msg_types:
                self.rbuf.append(msg)

        elapsed = self.elapsed_time
        if elapsed > self.next_subdivide:
            self.next_subdivide = elapsed + self.subdivide_interval
            self._subdivide_due = True

        if not (self._subdivide_due or elapsed > self.next_write):
            return

        if self.write_to_disk.is_set():
            # The last write hasn't finished. Keep buffering; the write and
            # any subdivision stay due until the writer is free, so messages
            # still go to the file they arrived for.
            if self._behind_since is None:
                self._behind_since = self._clock()
                self.logger.warning(
                    f"Dataset '{self.name}' is behind: the last write hasn't "
                    f"finished. Buffering {len(self.rbuf)} messages until it does."
                )
            return

        if self._behind_since is not None:
            behind = self._clock() - self._behind_since
            self.logger.info(
                f"Dataset '{self.name}' caught up after {behind:.1f} s; "
                f"writing {len(self.rbuf)} buffered messages."
            )
            self._behind_since = None

        self.next_write = elapsed + DatasetWriter.WRITE_PERIOD
        # Set while the writer is idle, so it applies to this batch only.
        self.subdivide_flag = self._subdivide_due
        self._subdivide_due = False
        self.stage_for_write()

    def store_saved(self):
        if not self.file_saved.is_set():
            self.save_msg = cd.MDF_DATASET_SAVED()
            self.save_msg.name = self.name
            self.save_msg.filepath = str(self.file_path)
            self.file_saved.set()
        self.saved_files.append(self.file_path)
        self.last_saved = self.file_path

    def subdivide(self):
        self.sub_index += 1
        self.formatter.finalize(self.wbuf)

        if self.fd:
            self.fd.close()
            self.store_saved()
            self.fd = None

        new_filename = (
            f"{self.base_file_name}_{self.sub_index:04d}{self.formatter_cls.ext}"
        )
        self.file_path = self.file_path.parent / new_filename

        self.logger.debug(f"Sub-dividing dataset: {self.file_path}")

        self.fd, self.formatter = self._open(self.file_path)

    def stop(self):
        if self.recording:
            self.stop_flag.set()
            self.start_time = -1
            self.ref_time = -1
            self._recording = False
            self._paused = False
            self.next_write = -1.0

    def send_error(self, exc: DataLoggerError):
        """Record a failure for the data logger to report.

        Args:
            exc: The failure. Its dataset defaults to this dataset.
        """
        self._set_error(type(exc).__name__, exc.dataset or self.name, exc.msg)

    def _set_error(self, exc_type: str, dataset: str, text: str) -> None:
        """Store an error message for the data logger to send.

        Text that isn't ASCII, such as a localized system message, has those
        characters replaced, and text too long for its field is cut, so the
        message can always be built.

        Args:
            exc_type: The exception's type name.
            dataset: The dataset's name.
            text: What happened.
        """
        # A new object, so the main thread never sends one being filled in.
        self.error = error_message(dataset, exc_type, text)
        self.error_event.set()

    def _fail(self, exc_type: str, text: str) -> None:
        """Stop recording after a failure and record it, once.

        Args:
            exc_type: The exception's type name.
            text: What happened.
        """
        with self._state_lock:
            if self._failed:
                return
            self._failed = True
            self._set_error(exc_type, self.name, text)
            self._recording = False
            self._paused = False
            self.rbuf = []

    def stage_for_write(self):
        """Set the write buffer data for the data collection write thread"""
        self.wbuf = self.rbuf
        self.rbuf = []

        self.write_finished.clear()
        self.write_to_disk.set()

        self.logger.debug("Writing dataset buffers to disk.")

    def write(self):
        """Write Threads main function

        Any exception stops the dataset: it is recorded with
        :py:meth:`_fail`, the file is closed without being finalized, and
        the thread ends. Files already finished are kept and reported.
        """
        try:
            while True:
                if self.write_to_disk.wait(0.5):
                    self.formatter.write(self.wbuf)
                    self.wbuf.clear()

                    if not self.stopped and self.subdivide_flag:
                        self.subdivide_flag = False
                        self.subdivide()

                    self.write_to_disk.clear()
                    self.write_finished.set()
                elif self.stop_flag.is_set():
                    self.stage_for_write()
                    self.formatter.finalize(self.wbuf)
                    if self.fd is not None:
                        self.fd.close()
                        self.store_saved()
                    break
        except DataLoggerError as e:
            self.logger.error(e.msg)
            self._fail(type(e).__name__, e.msg)
        except Exception as e:
            # A failed write leaves the file inconsistent, so it isn't
            # finalized; a QuickLogger file would claim data it doesn't hold.
            text = (
                f"Writing {self.file_path} failed: {type(e).__name__}: {e}. "
                "Messages not yet written were lost."
            )
            self.logger.exception(text)
            self._fail(type(e).__name__, text)
        finally:
            if self._failed and self.fd is not None:
                with contextlib.suppress(Exception):
                    self.fd.close()
            self.wbuf = []
            self._dead = True
            self.logger.debug("Collection write thread exited.")

    def blocking_write(self):
        """Blocking write without bg thread"""
        if self.write_to_disk.wait(0.5):
            self.write()
            self.write_to_disk.clear()
            self.write_finished.set()
