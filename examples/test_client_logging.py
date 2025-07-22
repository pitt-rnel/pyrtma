import pyrtma
import time
from logging import DEBUG, INFO, WARNING
from pyrtma.exceptions import LoggingConfigurationError


def warning_test_subfun(client: pyrtma.Client):
    client.warning("do not be alarmed, we are going to test logging errors")


def error_test_subfun(client: pyrtma.Client):
    client.error("this is just a test")


def final_subsubfun_test(client: pyrtma.Client):
    client.info("phew we got past that round of tests and our sub-subfunction works")


def critical_test_subfun(client: pyrtma.Client):
    client.critical("This is just a test, or else things would be very bad now")
    time.sleep(1.5)
    final_subsubfun_test(client)


def exception_test(client: pyrtma.Client):
    try:
        with client.logger.exception_logging_context():
            try:
                raise RuntimeError("This error is caught and should not be logged")
            except RuntimeError:
                pass
            raise RuntimeError(
                f"This error should be logged but, tests should continue"
            )
    except Exception:
        pass  # let our test continue, catching outside of with: logs the last error


if __name__ == "__main__":
    with pyrtma.client_context(name="logging_test") as client:

        client.info(f"Initial log level is: {client.logger.level}")
        client.logger.set_all_levels(WARNING)
        client.warning(
            f"After setting all levels to WARNING ({WARNING}) log level is {client.logger.level}"
        )
        client.logger.rtma_level = INFO
        client.logger.console_level = INFO
        client.info(
            f"After setting rtma and console handlers to INFO ({INFO}) log level is {client.logger.level}"
        )

        # enable log file (console and RTMA logs enabled by default), set to DEBUG
        client.logger.log_filename = "client_log_test.log"
        client.logger.file_level = DEBUG
        client.logger.enable_file = True
        client.logger.info(
            f"After setting file handler level to DEBUG {DEBUG} log level is {client.logger.level}"
        )

        client.info("Initialized logger, have not connected to RTMA yet")

        try:
            client.logger.log_filename = "bogus.log"
        except LoggingConfigurationError:
            client.warning("You cannot change the log filename after initializing it")

        time.sleep(1)

        client.connect()
        client.info(f"Connected to MMM @ {client.server}")

        client.send_module_ready()
        client.debug("sent module ready")

        client.info("starting tests of different levels within subfunctions")
        time.sleep(1)

        warning_test_subfun(client)
        time.sleep(1.5)

        error_test_subfun(client)
        time.sleep(1.5)

        critical_test_subfun(client)
        time.sleep(1)

        client.debug("all tests successful so far")

        exception_test(client)

        client.info("success, we passed all tests")
        time.sleep(0.5)

        with client.logger.exception_logging_context():
            raise RuntimeError(
                f"This last error should be logged before crashing it all"
            )
