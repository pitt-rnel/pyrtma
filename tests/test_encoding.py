import unittest
import random
import threading
import time
import logging

import pyrtma
import pyrtma.manager
from .test_msg_defs import test_defs as td

from pyrtma.client import client_context
from pyrtma.manager import MessageManager


class TestEncoding(unittest.TestCase):
    """Test sending messages through MessageManager."""

    def setUp(self):
        self.port = random.randint(1000, 10000)  # random port
        self.addr = f"127.0.0.1:{self.port}"

        self.manager = MessageManager(
            ip_address="127.0.0.1",
            port=self.port,
            timecode=False,
            debug=False,
            log_level=logging.ERROR,
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
        defs = td.get_message_definitions()
        with client_context(server_name=self.addr, definitions=defs) as publisher:
            with client_context(server_name=self.addr, definitions=defs) as subscriber:
                time.sleep(0.250)

                for mdf in defs.MDF.values():
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
