"""DataLogger class

Run with python -m pyrtma.data_logger
"""

import os
import pathlib
import threading
import time

import pyrtma
import pyrtma.core_defs as cd

from pyrtma.definitions import MessageDefinitions
from pyrtma.exceptions import (
    ConnectionLost,
    InvalidMessageDefinition,
    NotConnectedError,
    RTMAMessageError,
    UnknownMessageType,
)

from .data_formatter import UndecodedMessage, get_formatter
from .dataset_writer import DatasetWriter, check_write_period, error_message
from .exceptions import (
    DataLoggerError,
    DataLoggerFullError,
    DatasetExistsError,
    DatasetInProgress,
    DatasetNotFound,
)

from typing import Callable, cast


def _file_key(path: pathlib.Path) -> str:
    """Return a key that is equal for two spellings of the same file path.

    Args:
        path: The path.

    Returns:
        The absolute path, case-folded where the platform ignores case.
    """
    return os.path.normcase(os.path.abspath(path))


class DataLogger:
    MAX_DATASETS = 6
    ALL_SETS = ("*", "all")
    #: Seconds to wait at exit for the datasets' files to be finished.
    EXIT_TIMEOUT = 60.0

    def __init__(
        self,
        rtma_server_ip: str,
        log_level: int,
        definitions: MessageDefinitions,
        *,
        clock: Callable[[], float] = time.monotonic,
        fsync: bool = False,
        write_period: float = DatasetWriter.WRITE_PERIOD,
    ):
        """Connect to the message manager as the data logger.

        Args:
            rtma_server_ip: The manager's ``host:port``.
            log_level: The level for the logger's console and RTMA logging.
            definitions: The message definitions to decode and record with.
            clock: The datasets' clock, for their write and subdivide
                schedules. Injectable for tests.
            fsync: Make every dataset flush and ``os.fsync()`` its file after
                each write and before closing it; see ``DatasetWriter``. By
                default the operating system decides when to write its
                buffers to disk.
            write_period: Seconds between each dataset's writes of its
                buffered messages; see ``DatasetWriter``.

        Raises:
            ValueError: ``write_period`` isn't a number greater than 0.
            MessageManagerNotFound: The manager can't be reached.
        """
        self.mm_ip = rtma_server_ip
        self.definitions = definitions
        self._clock = clock
        self.fsync = fsync
        self.write_period = check_write_period(write_period)
        self._stop_requested = threading.Event()
        # Message types that couldn't be decoded and that no dataset was
        # recording, by type and error, so each is warned about once.
        self._unrecorded_warned: set[tuple[int, str]] = set()
        # Datasets to remove once their writer has finished the file, and the
        # module to send their DATASET_REMOVED to.
        self._removing: dict[str, int] = {}
        # How many of each dataset's saved files have been reported.
        self._saves_reported: dict[str, int] = {}
        # Datasets whose DATASET_STOPPED has been sent.
        self._stop_reported: set[str] = set()

        self.client = pyrtma.Client(
            module_id=cd.MID_DATA_LOGGER,
            name="data_logger",
            definitions=definitions,
        )
        self.client.logger.set_all_levels(log_level)
        self.client.connect(rtma_server_ip, logger_status=True)
        self.logger = self.client.logger
        self.ctrl_msg_types = [
            cd.MT_DATASET_START,
            cd.MT_DATASET_STOP,
            cd.MT_DATASET_PAUSE,
            cd.MT_DATASET_RESUME,
            cd.MT_DATASET_ADD,
            cd.MT_DATASET_REMOVE,
            cd.MT_DATASET_STATUS_REQUEST,
            cd.MT_DATA_LOGGER_CONFIG_REQUEST,
            cd.MT_DATA_LOGGER_RESET,
            cd.MT_EXIT,
            cd.MT_LM_EXIT,
        ]

        # self.client.subscribe(self.ctrl_msg_types)
        self.client.subscribe([cd.ALL_MESSAGE_TYPES])

        self.client.send_module_ready()

        self.client.info("DataLogger connected and waiting for configuration.")

        self.datasets: dict[str, DatasetWriter] = {}

    def stop(self) -> None:
        """Make :py:meth:`run` return; safe to call from any thread.

        It returns after its current read, within about 0.1 s, and after the
        datasets' files have been finished.
        """
        self._stop_requested.set()

    def update(self, msg: pyrtma.Message | None):
        """Pass a message to every dataset, and report what the datasets did.

        Errors, saved files and stopped datasets are reported, and datasets
        whose writer has finished are removed. A dataset that fails here in
        an unexpected way is logged, reported and dropped; the others carry
        on.

        Args:
            msg: A received message, or None to only update the datasets.

        Raises:
            ConnectionLost: The connection to the manager failed.
        """
        for name, ds in list(self.datasets.items()):
            try:
                if not ds.dead:
                    ds.update(msg)
                self._report(ds)
                if ds.dead:
                    self._finish(name)
            except (ConnectionLost, NotConnectedError):
                raise
            except Exception as e:
                # Dropped at once, so a fault in reporting can't repeat on
                # every pass. Its writer still finishes the file.
                self.logger.exception(f"Dataset '{name}' failed; dropping it.")
                ds.stop()
                self._forget(name)
                self._send_error(
                    name, type(e).__name__, f"Dataset '{name}' was dropped: {e}"
                )

    def _report(self, ds: DatasetWriter) -> None:
        """Send a dataset's error and saved files that haven't been reported.

        A dataset whose writer failed has stopped by itself, so its
        ``DATASET_STOPPED`` follows its error.

        Args:
            ds: The dataset.
        """
        if ds.error_event.is_set():
            ds.error_event.clear()
            self.client.send_message(ds.error)
            self.logger.error(f"Dataset '{ds.name}': {ds.error.msg}")
        if ds.failed:
            self._report_stopped(ds.name)

        ds.file_saved.clear()
        reported = self._saves_reported.get(ds.name, 0)
        for path in ds.saved_files[reported:]:
            saved = cd.MDF_DATASET_SAVED()
            saved.name = ds.name
            saved.filepath = str(path)
            self.client.send_message(saved)
            self.logger.info(f"Saved file: {path}")
            reported += 1
        self._saves_reported[ds.name] = reported

    def _report_stopped(self, name: str) -> None:
        """Send a dataset's ``DATASET_STOPPED``, once.

        Args:
            name: The dataset's name.
        """
        if name in self._stop_reported:
            return
        self._stop_reported.add(name)
        stop_msg = cd.MDF_DATASET_STOPPED()
        stop_msg.name = name
        self.client.send_message(stop_msg)

    def _finish(self, name: str) -> None:
        """Remove a dataset whose writer has finished.

        Args:
            name: The dataset's name.
        """
        dest_mod_id = self._removing.pop(name, 0)
        self._remove(name, dest_mod_id)

    def _forget(self, name: str) -> None:
        """Drop a dataset and what is tracked about it.

        Args:
            name: The dataset's name.
        """
        self.datasets.pop(name, None)
        self._removing.pop(name, None)
        self._saves_reported.pop(name, None)
        self._stop_reported.discard(name)

    def _remove(self, name: str, dest_mod_id: int) -> None:
        """Drop a dataset and send its ``DATASET_REMOVED``.

        Args:
            name: The dataset's name.
            dest_mod_id: The module to send the reply to; 0 broadcasts it.
        """
        self._forget(name)
        reply = cd.MDF_DATASET_REMOVED()
        reply.name = name
        self.client.send_message(reply, dest_mod_id=dest_mod_id)
        self.logger.info(f"Removed dataset: '{name}'")

    def rm_dataset(self, name: str, dest_mod_id: int = 0):
        """Remove a dataset that isn't recording.

        A dataset that has recorded is removed once its writer has finished
        the file, after its ``DATASET_SAVED``.

        Args:
            name: The dataset's name.
            dest_mod_id: The module to send ``DATASET_REMOVED`` to; 0
                broadcasts it.

        Raises:
            DatasetNotFound: There is no such dataset.
            DatasetInProgress: The dataset is recording.
        """
        ds = self.datasets.get(name)

        if ds is None:
            raise DatasetNotFound(name, f"Dataset named '{name}' not found.")

        if ds.recording:
            raise DatasetInProgress(
                name, f"Recording in progresss for dataset '{ds.name}'"
            )

        if ds.started:
            # update() removes it once its writer is done and its saved files
            # are reported.
            self._removing[name] = dest_mod_id
            return

        self._remove(name, dest_mod_id)

    def send_status(self, name: str = "all", dest_mod_id: int = 0):
        msg = cd.MDF_DATASET_STATUS()
        msg.timestamp = time.time()

        if name in DataLogger.ALL_SETS:
            for ds in self.datasets.values():
                msg.name = ds.name
                msg.elapsed_time = ds.elapsed_time
                msg.is_recording = ds.recording
                msg.is_paused = ds.paused
                self.client.send_message(msg, dest_mod_id=dest_mod_id)
        else:
            ds = self.datasets.get(name)
            if ds is None:
                raise DatasetNotFound(name, f"Dataset named '{name}' not found.")

            msg.name = ds.name
            msg.elapsed_time = ds.elapsed_time
            msg.is_recording = ds.recording
            msg.is_paused = ds.paused
            self.client.send_message(msg, dest_mod_id=dest_mod_id)

    def send_config(self, dest_mod_id: int = 0):
        msg = cd.MDF_DATA_LOGGER_CONFIG()

        msg.num_datasets = len(self.datasets)

        for i, ds in enumerate(self.datasets.values()):
            d = msg.datasets[i]

            d.name = ds.name
            d.save_path = str(ds.save_path)
            d.filename = ds.filename
            d.formatter = ds.formatter_cls.name
            d.msg_types[: len(ds.msg_types)] = ds.msg_types
            d.max_size_mb = ds.max_size_mb

        self.client.send_message(msg, dest_mod_id=dest_mod_id)

    def _start(self, ds: DatasetWriter) -> None:
        """Start one dataset and announce it.

        Args:
            ds: The dataset.

        Raises:
            DataLoggerError: The dataset couldn't start.
        """
        ds.start()
        self._stop_reported.discard(ds.name)
        self.logger.info(f"Starting dataset: '{ds.name}'")
        self.logger.info(f"Saving Dataset:{ds.name} to {ds.file_path}")
        start_msg = cd.MDF_DATASET_STARTED()
        start_msg.name = ds.name
        self.client.send_message(start_msg)

    def start_logging(self, name: str, dest_mod_id: int = 0):
        """Start one dataset, or every dataset that hasn't started.

        Starting all skips datasets that are recording or have already
        recorded, with a warning, and reports a dataset that fails to start
        without stopping the others.

        Args:
            name: The dataset's name, or one of ``ALL_SETS``.
            dest_mod_id: The module to send the status to; 0 broadcasts it.

        Raises:
            DatasetNotFound: There is no dataset with that name.
            DatasetInProgress: The named dataset is recording or has recorded.
            DatasetError: The named dataset couldn't start.
        """
        if name in DataLogger.ALL_SETS:
            for ds in list(self.datasets.values()):
                if ds.recording:
                    self.logger.warning(f"Dataset {ds.name} is already recording")
                    continue
                if ds.started:
                    self.logger.warning(f"Dataset {ds.name} has already recorded")
                    continue
                try:
                    self._start(ds)
                except DataLoggerError as e:
                    self.client.error(e.msg)
                    self.send_error(e)
        else:
            ds = self.datasets.get(name)
            if ds is None:
                raise DatasetNotFound(name, f"Dataset named '{name}' not found.")

            if ds.recording:
                raise DatasetInProgress(
                    name, f"Recording in progresss for dataset '{ds.name}'"
                )

            self._start(ds)

        self.send_status(dest_mod_id=dest_mod_id)

    def stop_logging(self, name: str, dest_mod_id: int = 0):
        if name in DataLogger.ALL_SETS:
            for ds in self.datasets.values():
                if not ds.recording:
                    self.logger.warning(f"Dataset {ds.name} is not recording")
                    continue
                ds.stop()
                self.logger.info(f"Stopping dataset: '{ds.name}'")
                self._report_stopped(ds.name)
        else:
            ds = self.datasets.get(name)
            if ds is None:
                raise DatasetNotFound(name, f"Dataset named '{name}' not found.")

            if not ds.recording:
                self.logger.warning(f"Dataset {ds.name} is not recording")
                return

            ds.stop()
            self.logger.info(f"Stopping dataset: '{ds.name}'")
            self._report_stopped(ds.name)

        self.send_status(dest_mod_id=dest_mod_id)

    def pause_logging(self, name: str, dest_mod_id: int = 0):
        if name in DataLogger.ALL_SETS:
            for ds in self.datasets.values():
                if ds.pause():
                    self.logger.info(f"Pausing dataset: '{ds.name}'")
        else:
            ds = self.datasets.get(name)
            if ds is None:
                raise DatasetNotFound(name, f"Dataset named '{name}' not found.")

            if not ds.pause():
                state = "already paused" if ds.paused else "not recording"
                self.logger.warning(f"Dataset {ds.name} is {state}")
                return

            self.logger.info(f"Pausing dataset: '{ds.name}'")

        self.send_status(dest_mod_id=dest_mod_id)

    def resume_logging(self, name: str, dest_mod_id: int = 0):
        if name in DataLogger.ALL_SETS:
            for ds in self.datasets.values():
                if ds.resume():
                    self.logger.info(f"Resuming dataset: {ds.name}")
        else:
            ds = self.datasets.get(name)
            if ds is None:
                raise DatasetNotFound(name, f"Dataset named '{name}' not found.")

            if not ds.resume():
                self.logger.warning(f"Dataset {ds.name} is not paused")
                return

            self.logger.info(f"Resuming dataset: {ds.name}")

        self.send_status(dest_mod_id=dest_mod_id)

    def _check_target(self, name: str, dataset: cd.DATASET) -> None:
        """Refuse a dataset that would write to another dataset's file.

        Args:
            name: The new dataset's name.
            dataset: Its configuration.

        Raises:
            DatasetExistsError: Another dataset writes to the same file.
        """
        formatter_cls = get_formatter(dataset.formatter)
        if formatter_cls is None:
            return  # DatasetWriter reports the unknown formatter.
        target = pathlib.Path(dataset.save_path) / (
            dataset.filename + formatter_cls.ext
        )
        for other in self.datasets.values():
            existing = other.save_path / other.filename
            if _file_key(existing) == _file_key(target):
                raise DatasetExistsError(
                    name, f"Dataset '{other.name}' already records to {existing}"
                )

    def _max_size_mb(self, name: str, requested: int) -> int:
        """Return the file size limit to use for a dataset.

        A value outside 1 to ``DATASET_MAX_SIZE_MB`` is replaced by
        ``DATASET_MAX_SIZE_MB``, with a warning, rather than refused. A client
        compiled before ``max_size_mb`` replaced ``subdivide_interval`` sends
        the same bytes, most often 0 for one continuous file, so refusing
        would stop it recording.

        Args:
            name: The dataset's name.
            requested: The ``max_size_mb`` in the request.

        Returns:
            The limit in MB.
        """
        if 1 <= requested <= cd.DATASET_MAX_SIZE_MB:
            return requested
        self.logger.warning(
            f"Dataset '{name}': max_size_mb {requested} is outside 1 to "
            f"{cd.DATASET_MAX_SIZE_MB}; using {cd.DATASET_MAX_SIZE_MB}. A client "
            "built before max_size_mb replaced subdivide_interval sends its "
            "interval here; rebuild it."
        )
        return cd.DATASET_MAX_SIZE_MB

    def add_dataset(self, msg: cd.MDF_DATASET_ADD, dest_mod_id: int = 0):
        """Add a dataset.

        Every check is made before the dataset is built, so a refused
        dataset creates no folders.

        Args:
            msg: The request.
            dest_mod_id: The module to send ``DATASET_ADDED`` to; 0
                broadcasts it.

        Raises:
            DataLoggerFullError: ``MAX_DATASETS`` datasets are configured.
            DatasetExistsError: A dataset has that name or writes to that file.
            DatasetError: The dataset is invalid or its folder can't be made.
        """
        name = msg.dataset.name
        if len(self.datasets) >= DataLogger.MAX_DATASETS:
            raise DataLoggerFullError(
                name, "Logger has maximum allowed datasets configured."
            )

        if name in self.datasets.keys():
            text = f"A dataset with name '{name}' already exists"
            if name in self._removing:
                text += "; it is being removed"
            raise DatasetExistsError(name, text)

        self._check_target(name, msg.dataset)

        dataset = DatasetWriter(
            name=name,
            save_path=msg.dataset.save_path,
            filename=msg.dataset.filename,
            msg_types=msg.dataset.msg_types[:],
            formatter=msg.dataset.formatter,
            subdivide_interval=0,
            max_size_mb=self._max_size_mb(name, msg.dataset.max_size_mb),
            clock=self._clock,
            fsync=self.fsync,
            write_period=self.write_period,
            definitions=self.definitions,
        )

        self.datasets[dataset.name] = dataset
        reply = cd.MDF_DATASET_ADDED()
        reply.name = dataset.name
        self.client.send_message(reply, dest_mod_id=dest_mod_id)

        self.logger.info(f"Added dataset: '{dataset.name}'")

    def reset(self, dest_mod_id: int = 0):
        """Stop and remove every dataset.

        Datasets that recorded are removed once their files are finished,
        after their ``DATASET_SAVED``.

        Args:
            dest_mod_id: The module to send ``DATASET_REMOVED`` to; 0
                broadcasts it.
        """
        self.client.info(f"Reset DataLogger. All Datasets will be cleared")
        for name, ds in list(self.datasets.items()):
            if ds.recording:
                ds.stop()
                self._report_stopped(name)
            self.rm_dataset(name, dest_mod_id=dest_mod_id)

    def send_error(self, exc: DataLoggerError):
        """Broadcast a ``DATA_LOGGER_ERROR`` for an exception.

        Args:
            exc: The exception.
        """
        self._send_error(exc.dataset, type(exc).__name__, exc.msg)

    def _send_error(self, dataset: str, exc_type: str, text: str) -> None:
        """Broadcast a ``DATA_LOGGER_ERROR``, made to fit its fields.

        Args:
            dataset: The dataset's name, or "" for the logger as a whole.
            exc_type: The exception's type name.
            text: What happened.
        """
        self.client.send_message(error_message(dataset, exc_type, text))

    def _type_label(self, msg_type: int | None) -> str:
        """Describe a message type by number, and name where it is known.

        Args:
            msg_type: The type, or None if it isn't known.

        Returns:
            Text such as ``"6001 (TEST_START)"``.
        """
        if msg_type is None:
            return "of unknown type"
        try:
            name = self.definitions.get_msg_cls(msg_type).type_name
        except UnknownMessageType:
            return str(msg_type)
        return f"{msg_type} ({name})"

    def _undecodable(self, exc: RTMAMessageError) -> None:
        """Handle a received message that the definitions can't decode.

        A dataset whose formatter accepts undecoded messages, as ``raw`` does,
        records it as received and keeps recording; the first such message
        of each type and error is reported for that dataset. Every other
        dataset that would have recorded it is stopped and reported: its
        recording is missing data until the definitions are fixed. The file
        keeps what was recorded until then. When no dataset records the type,
        it is warned about once per type and error.

        Args:
            exc: The client's error. Its ``header`` names the message type.
        """
        header = exc.header
        msg_type: int | None = header.msg_type if header is not None else None
        label = self._type_label(msg_type)
        reason = type(exc).__name__
        detail = str(exc.args[0]) if exc.args else str(exc)

        affected = [
            ds
            for ds in self.datasets.values()
            if ds.recording
            and not ds.paused
            and (ds.all_sub or (msg_type is not None and msg_type in ds.msg_types))
        ]
        if not affected:
            key = (-1 if msg_type is None else msg_type, reason)
            if key not in self._unrecorded_warned:
                self._unrecorded_warned.add(key)
                self.logger.warning(
                    f"A message {label} can't be decoded, so it isn't recorded: "
                    f"{detail} Later ones like it aren't reported."
                )
            return

        if header is not None and exc.payload is not None:
            undecoded = UndecodedMessage(header, exc.payload)
            keeping = [ds for ds in affected if ds.formatter_cls.accepts_undecoded]
            affected = [ds for ds in affected if ds not in keeping]
            for ds in keeping:
                ds.update(undecoded)
                key = (-1 if msg_type is None else msg_type, reason)
                if key in ds.undecoded_reported:
                    continue
                ds.undecoded_reported.add(key)
                text = (
                    f"Recording undecoded: a message {label} can't be decoded "
                    f"with the logger's definitions; it is recorded as received "
                    f"and marked undecoded. Later ones like it aren't reported. "
                    f"{detail}"
                )
                self.logger.warning(f"Dataset '{ds.name}': {text}")
                self._send_error(ds.name, reason, text)

        text = (
            f"Stopped recording: a message {label} can't be decoded with the "
            f"logger's definitions; update them to record it. {detail}"
        )
        for ds in affected:
            self.logger.error(f"Dataset '{ds.name}': {text}")
            self._send_error(ds.name, reason, text)
            ds.stop()
            self._report_stopped(ds.name)

    def _request_dataset(self, msg: pyrtma.Message) -> str:
        """Return the dataset a request names, or "" if it names none.

        Args:
            msg: The request.
        """
        try:
            if msg.type_id == cd.MT_DATASET_ADD:
                return cast(cd.MDF_DATASET_ADD, msg.data).dataset.name
            name = getattr(msg.data, "name", "")
            return name if isinstance(name, str) else ""
        except Exception:
            return ""

    def _handle_request(self, msg: pyrtma.Message) -> None:
        """Act on a control request meant for the logger.

        A request addressed to another module is ignored: the manager sends a
        logger module copies of every message. A broadcast request is
        answered with a broadcast; a request addressed to the logger is
        answered to its sender.

        Args:
            msg: A received message.

        Raises:
            DataLoggerError: The request failed.
        """
        if msg.type_id not in self.ctrl_msg_types:
            return
        dest = msg.header.dest_mod_id
        if dest not in (0, self.client.module_id):
            return
        reply_to = 0 if dest == 0 else msg.header.src_mod_id

        match (msg.data.type_id):
            case cd.MT_DATASET_START:
                self.start_logging(cast(str, msg.data.name), dest_mod_id=reply_to)
            case cd.MT_DATASET_STOP:
                self.stop_logging(cast(str, msg.data.name), dest_mod_id=reply_to)
            case cd.MT_DATASET_PAUSE:
                self.pause_logging(cast(str, msg.data.name), dest_mod_id=reply_to)
            case cd.MT_DATASET_RESUME:
                self.resume_logging(cast(str, msg.data.name), dest_mod_id=reply_to)
            case cd.MT_DATASET_ADD:
                self.add_dataset(
                    cast(cd.MDF_DATASET_ADD, msg.data), dest_mod_id=reply_to
                )
            case cd.MT_DATASET_REMOVE:
                self.rm_dataset(cast(str, msg.data.name), dest_mod_id=reply_to)
            case cd.MT_DATA_LOGGER_RESET:
                self.reset(dest_mod_id=0)
            case cd.MT_DATASET_STATUS_REQUEST:
                self.send_status(
                    cast(str, msg.data.name),
                    dest_mod_id=msg.header.src_mod_id,
                )
            case cd.MT_DATA_LOGGER_CONFIG_REQUEST:
                self.send_config(dest_mod_id=reply_to)
            case cd.MT_EXIT:
                if dest == self.client.module_id:
                    self._stop_requested.set()
                    self.client.info("Received EXIT request. Closing...")
            case cd.MT_LM_EXIT:
                self._stop_requested.set()
                self.client.info("Received LM_EXIT request. Closing...")

    def _handle(self, msg: pyrtma.Message) -> None:
        """Handle a request, reporting any failure instead of raising it.

        Args:
            msg: A received message.

        Raises:
            ConnectionLost: The connection to the manager failed.
        """
        try:
            self._handle_request(msg)
        except (ConnectionLost, NotConnectedError):
            raise
        except DataLoggerError as e:
            self.client.error(e.msg)
            self.send_error(e)
        except Exception as e:
            self.logger.exception(
                f"{msg.name} request from module {msg.header.src_mod_id} failed"
            )
            self._send_error(
                self._request_dataset(msg),
                type(e).__name__,
                f"{msg.name} request failed: {e}",
            )

    def _shutdown(self) -> None:
        """Stop every dataset, wait for its file, report, and disconnect."""
        recording = [ds.name for ds in self.datasets.values() if ds.recording]
        for ds in self.datasets.values():
            ds.stop()

        deadline = time.monotonic() + DataLogger.EXIT_TIMEOUT
        for ds in self.datasets.values():
            if ds.write_thread.ident is None:
                continue
            ds.write_thread.join(max(0.0, deadline - time.monotonic()))
            if ds.write_thread.is_alive():
                self.logger.warning(f"Dataset '{ds.name}' is still finishing its file.")

        if self.client.connected:
            try:
                for name in recording:
                    self._report_stopped(name)
                self.update(None)
            except Exception:
                self.logger.exception("Couldn't report the datasets at exit.")
            self.client.disconnect()

    def run(self):
        """Receive, record and handle requests until stopped.

        Ends on ``EXIT`` addressed to the logger, ``LM_EXIT``,
        :py:meth:`stop`, ``KeyboardInterrupt``, or a lost connection. A
        failing request or dataset is reported and doesn't end it.

        Raises:
            ConnectionLost: The connection to the manager failed. The
                datasets' files are finished first.
        """
        try:
            while not self._stop_requested.is_set():
                try:
                    msg = self.client.read_message(0.100)
                except (UnknownMessageType, InvalidMessageDefinition) as e:
                    self._undecodable(e)
                    msg = None

                if msg is not None:
                    self._handle(msg)

                self.update(msg)

        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown()
            self.client.info("DataLogger is exiting...")
