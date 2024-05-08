import pyrtma
import time
from logging import DEBUG


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
            except Exception:
                pass
            raise RuntimeError(f"This error should be logged")
    except Exception:
        pass  # let our test continue, catching outside of of with: logs the last error


if __name__ == "__main__":
    try:
        client = pyrtma.Client()

        # enable log file (console and RTMA logs enabled by default)
        client.logger.log_filename = "client_log_test.log"
        client.logger.enable_file = True

        client.info("Initialized logger, have not connected to RTMA yet")
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
            raise RuntimeError(f"But this last error will crash it all")
    finally:
        client.disconnect()
