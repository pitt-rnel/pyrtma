import unittest
import random
import threading
import time
import logging

import pyrtma
from .test_msg_defs.test_defs import *

from pyrtma.client import Client
import pyrtma.manager
from pyrtma.manager import MessageManager


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
        for mod in self.manager.modules:
            mod.close()

    def test_message_encoding(self):
        publisher = Client()
        publisher.connect(self.addr)
        subscriber = Client()
        subscriber.connect(self.addr)
        time.sleep(0.250)

        for mdf in pyrtma.msg_defs.values():
            if mdf.type_id > 1000:
                # Subscribe from message type
                subscriber.subscribe([mdf.type_id])
                subscriber.wait_for_acknowledgement()

                # Publish a random message of the subscribed type
                in_msg = mdf.from_random()
                publisher.send_message(in_msg)

                # Wait for the message and compare for equality of the data segment
                out_msg = subscriber.read_message(timeout=0.020)
                if out_msg is None:
                    self.fail("Subscriber did not receive packet.")
                else:
                    self.assertEqual(in_msg, out_msg.data)

                # Unsubscribe from message type
                subscriber.unsubscribe([mdf.type_id])
                subscriber.wait_for_acknowledgement()
