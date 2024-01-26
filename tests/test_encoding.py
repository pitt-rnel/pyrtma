import unittest
import random
import threading
import time
import logging

import pyrtma
import pyrtma.message

from pyrtma.client import Client, client_context
import pyrtma.manager
from pyrtma.manager import MessageManager

# Import message defs to add to pyrtma.msg_defs map
from .test_msg_defs.test_defs import *


class TestEncoding(unittest.TestCase):
    """Test sending messages through MessageManager."""

    def setUp(self):
        self.port = random.randint(1000, 10000)  # random port
        self.addr = f"127.0.0.1:{self.port}"

        pyrtma.manager.LOG_LEVEL = logging.ERROR
        self.manager = MessageManager(
            ip_address="127.0.0.1",
            port=self.port,
            timecode=False,
            debug=False,
            send_msg_timing=True,
        )
        self.manager_thread = threading.Thread(
            target=self.manager.run,
        )
        self.manager_thread.start()
        time.sleep(0.250)

    def tearDown(self):
        self.manager.close()
        self.manager_thread.join()

    def test_message_encoding(self):
        with client_context(server_name=self.addr) as publisher:
            with client_context(server_name=self.addr) as subscriber:
                time.sleep(0.250)

                for mdf in pyrtma.message.get_msg_defs().values():
                    if mdf.type_id > 1000:
                        # Subscribe from message type
                        with subscriber.subscription_context([mdf.type_id]):
                            time.sleep(0.01)

                            # Publish a random message of the subscribed type
                            in_msg = mdf.from_random()
                            publisher.send_message(in_msg)

                            # Wait for the message and compare for equality of the data segment
                            out_msg = subscriber.read_message(timeout=0.020)
                            if out_msg is None:
                                self.fail("Subscriber did not receive packet.")
                            else:
                                self.assertEqual(in_msg, out_msg.data)

        time.sleep(0.5)
