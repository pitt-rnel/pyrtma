"""DataSet class used internally by data_logger"""

import contextlib
import os
import pathlib
import warnings
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

from .data_formatter import DataFormatter, FileContext, Recordable
from ..definitions import MessageDefinitions
from .exceptions import (
    DatasetError,
    InvalidFormatter,
    DatasetExistsError,
    DatasetInProgress,
    DatasetThreadError,
    DatasetWriterError,
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


def _fsync_dir(path: pathlib.Path) -> None:
    """Make the directory entries in ``path`` durable.

    ``fsync()`` of a new file doesn't cover its name in the directory, so
    after a power loss the file's data could be on disk but unreachable.
    POSIX only: NTFS keeps a created file's entry without this.
    """
    if os.name != "posix":
        return
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def check_write_period(seconds: float) -> float:
    """Check a write period.

    Args:
        seconds: Seconds between writes.

    Returns:
        ``seconds``, as a float.

    Raises:
        ValueError: It isn't a finite number greater than 0.
    """
    period = float(seconds)
    if not math.isfinite(period) or period <= 0:
        raise ValueError(f"The write period must be more than 0 s, not {seconds!r}.")
    return period


class DatasetWriter:
    # Deprecated: files are no longer split by time. Kept so existing
    # references still resolve.
    MIN_INTERVAL = 30
    MAX_INTERVAL = 600
    CONTINUOUS = math.inf
    #: The default seconds between writes; see ``write_period``.
    WRITE_PERIOD = 15.0
    #: Bytes in one MB of ``max_size_mb``.
    BYTES_PER_MB = 1_000_000

    def __init__(
        self,
        name: str,
        save_path: str,
        filename: str,
        formatter: str,
        subdivide_interval: int,
        msg_types: List[int],
        *,
        max_size_mb: int = cd.DATASET_MAX_SIZE_MB,
        clock: Callable[[], float] = time.monotonic,
        fsync: bool = False,
        definitions: Optional[MessageDefinitions] = None,
        write_period: float = WRITE_PERIOD,
    ):
        """Set up a dataset; nothing is recorded until :py:meth:`start`.

        Args:
            name: The dataset's name.
            save_path: The folder to save to; it is created if needed.
            filename: The file name, without the formatter's extension.
            formatter: The name of a registered formatter.
            subdivide_interval: Deprecated and ignored: files are split by
                size, with ``max_size_mb``. A nonzero value warns.
            msg_types: The message types to record; ``ALL_MESSAGE_TYPES``
                records every type.
            max_size_mb: The largest file, in MB of 1,000,000 bytes, from 1
                to ``DATASET_MAX_SIZE_MB``. A full file continues in a new one,
                numbered ``_0001``, ``_0002`` and so on. A formatter whose own
                ``max_bytes`` is lower keeps that.
            clock: Seconds from a monotonic clock, for the write schedule and
                the elapsed time. Injectable for tests.
            fsync: After every write and before closing a file, flush it and
                ``os.fsync()`` it, and sync its folder when a file is created,
                so a power loss costs at most one write period of messages. By
                default the operating system decides when to write its buffers
                to disk.
            definitions: The data logger's message definitions, passed to
                formatters that want a :py:class:`FileContext`.
            write_period: Seconds between writes of the buffered messages to
                the file. A shorter period loses less if the logger dies or the
                power fails, and makes more, smaller writes (and syncs, with
                ``fsync``). Writes are checked each time the logger reads, at
                least every 0.1 s.

        Raises:
            ValueError: ``write_period`` isn't a number greater than 0.
            InvalidFormatter: No formatter has that name.
            DatasetError: ``max_size_mb`` is out of range, or the save path
                can't be created.
            DatasetExistsError: The file already exists.
        """
        self._dead = False
        self._recording = False
        self._paused = False
        self._close = False
        self._elapsed_time = 0.0
        self._clock = clock
        self.fsync = fsync
        self.definitions = definitions
        self.write_period = check_write_period(write_period)
        #: (message type, error) pairs recorded undecoded and reported.
        self.undecoded_reported: set[tuple[int, str]] = set()
        self._started = False
        self._failed = False
        # Guards _failed, so only the first failure is reported.
        self._state_lock = threading.Lock()
        # When the writer fell behind, or None while it keeps up.
        self._behind_since: Optional[float] = None

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

        if subdivide_interval:
            warnings.warn(
                "subdivide_interval is deprecated and ignored; files are split "
                "by size, with max_size_mb.",
                DeprecationWarning,
                stacklevel=2,
            )
        # Deprecated: always continuous now.
        self.subdivide_interval = DatasetWriter.CONTINUOUS

        if not 1 <= max_size_mb <= cd.DATASET_MAX_SIZE_MB:
            raise DatasetError(
                self.name,
                f"max_size_mb must be from 1 to {cd.DATASET_MAX_SIZE_MB}, "
                f"not {max_size_mb}.",
            )
        self.max_size_mb = max_size_mb

        # Placeholder for type checking purposes
        placeholder = io.BytesIO() if "b" in self.formatter_cls.mode else io.StringIO()
        self.formatter = self._new_formatter(
            placeholder,
            pathlib.Path(save_path) / (filename + self.formatter_cls.ext),
            0,
        )

        self.rbuf: List[Recordable] = []
        self.wbuf: List[Recordable] = []

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
            write schedule carry on.
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

    def _new_formatter(
        self, fd: IO[Any], path: pathlib.Path, part: int
    ) -> DataFormatter:
        """Create the formatter for a file, with a context if it wants one.

        Args:
            fd: The open file.
            path: The file's path.
            part: The file's part number: 0, then 1, 2, ... after rollovers.

        Returns:
            The formatter.
        """
        if self.formatter_cls.wants_context:
            context = FileContext(self.name, path, part, self.definitions)
            return self.formatter_cls(fd, context=context)
        return self.formatter_cls(fd)

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
            if self.fsync:
                _fsync_dir(path.parent)
        except OSError as e:
            with contextlib.suppress(OSError):
                fd.close()
            with contextlib.suppress(OSError):
                path.unlink()
            raise DatasetError(self.name, f"Can't sync {path.parent}: {e}") from e

        try:
            formatter = self._new_formatter(fd, path, self.sub_index)
            # The dataset's limit, unless the formatter's own is lower.
            formatter.max_bytes = min(
                type(formatter).max_bytes,
                self.max_size_mb * DatasetWriter.BYTES_PER_MB,
            )
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

        self.start_time = self._clock()
        self.ref_time = self.start_time

        self.next_write = self.write_period
        self._recording = True
        self._paused = False

        # Start the write thread
        self.write_thread.start()

    def update(self, msg: Optional[Recordable]):
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
        if not elapsed > self.next_write:
            return

        if self.write_to_disk.is_set():
            # The last write hasn't finished. Keep buffering; the write
            # stays due until the writer is free.
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

        self.next_write = elapsed + self.write_period
        self.stage_for_write()

    def store_saved(self):
        if not self.file_saved.is_set():
            self.save_msg = cd.MDF_DATASET_SAVED()
            self.save_msg.name = self.name
            self.save_msg.filepath = str(self.file_path)
            self.file_saved.set()
        self.saved_files.append(self.file_path)
        self.last_saved = self.file_path

    def _write_batch(self, batch: List[Recordable]) -> None:
        """Write messages, continuing in new files when one is full.

        Args:
            batch: The messages, in order.
        """
        # The formatter sees every batch, even an empty one, as before.
        fresh = False
        while True:
            written = self.formatter.write(batch)
            if written is None or written >= len(batch):
                return
            if written == 0 and fresh:
                raise DatasetWriterError(
                    self.name,
                    f"Formatter '{self.formatter_name}' took no messages into a "
                    f"new file, {self.file_path}.",
                )
            batch = batch[written:]
            self.logger.info(
                f"Dataset '{self.name}': {self.file_path} reached its size limit "
                f"of {self.formatter.max_bytes} bytes; continuing in a new file."
            )
            self.subdivide()
            fresh = True

    def _sync(self) -> None:
        """With ``fsync``, push everything written so far through to the disk.

        Without it, nothing is done: the operating system writes its buffers
        when it decides to.
        """
        if self.fsync and self.fd is not None:
            self.fd.flush()
            os.fsync(self.fd.fileno())

    def subdivide(self):
        """Finish the current file and continue in the next one.

        Used when a file is full. The next file is numbered ``_0001``,
        ``_0002`` and so on.
        """
        self.sub_index += 1
        self.formatter.finalize([])
        self._sync()

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
                    self._write_batch(self.wbuf)
                    self._sync()
                    self.wbuf.clear()

                    self.write_to_disk.clear()
                    self.write_finished.set()
                elif self.stop_flag.is_set():
                    self.stage_for_write()
                    self._write_batch(self.wbuf)
                    self.formatter.finalize([])
                    self._sync()
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
            if self._failed:
                with contextlib.suppress(Exception):
                    self.formatter.discard()
                if self.fd is not None:
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
